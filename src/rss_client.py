"""Async RSS client for fetching curated financial news feeds.

Fetches articles from a curated list of RSS feeds defined in rss_feeds.yaml,
with TTL caching, sector-based feed selection, and article normalization.
"""

import asyncio
import logging
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, Any, List, Optional

import aiohttp
import feedparser
import yaml

from .news_source_tiers import get_source_tier

logger = logging.getLogger(__name__)

_FEEDS_PATH = Path(__file__).parent / "rss_feeds.yaml"


def _load_feeds() -> List[Dict[str, Any]]:
    """Load feed definitions from rss_feeds.yaml.

    Returns:
        List of feed dicts with keys: name, url, tier, sectors.
    """
    with open(_FEEDS_PATH, "r") as f:
        data = yaml.safe_load(f)
    return data.get("feeds", [])


def _normalize_entry(
    entry: Dict[str, Any],
    source_name: str,
    tier: int,
) -> Optional[Dict[str, Any]]:
    """Convert a feedparser entry dict into a normalized article dict.

    Args:
        entry: A dict-like feedparser entry with keys like title, link, summary.
        source_name: Human-readable feed name (e.g., "Reuters Business").
        tier: Source quality tier (1, 2, or 3).

    Returns:
        Normalized article dict, or None if title/link is missing.
    """
    title = entry.get("title", "").strip()
    link = entry.get("link", "").strip()

    if not title or not link:
        return None

    # Parse published date
    published_at = ""
    published_parsed = entry.get("published_parsed")
    if published_parsed:
        try:
            dt = datetime(*published_parsed[:6], tzinfo=timezone.utc)
            published_at = dt.isoformat()
        except Exception:
            published_at = entry.get("published", "")
    else:
        published_at = entry.get("published", "")

    return {
        "title": title,
        "url": link,
        "source": source_name,
        "source_tier": tier,
        "description": entry.get("summary", ""),
        "content": "",  # RSS feeds rarely provide full content
        "published_at": published_at,
        "author": entry.get("author", ""),
        "rss_source": True,
    }


class RSSClient:
    """Async RSS client with TTL caching and sector-based feed selection.

    Usage:
        client = RSSClient(cache_ttl=900)
        articles = await client.fetch_feeds(ticker="AAPL", sector="technology")
    """

    def __init__(self, cache_ttl: int = 900):
        """Initialize RSS client.

        Args:
            cache_ttl: Cache time-to-live in seconds (default 15 minutes).
        """
        self.cache_ttl = cache_ttl
        self._feeds = _load_feeds()
        # Per-URL cache: feed_url → (timestamp, list of normalized articles)
        self._cache: Dict[str, tuple[float, List[Dict[str, Any]]]] = {}
        # Aggregate results cache: cache_key → (timestamp, list of all articles)
        self._results_cache: Dict[str, tuple[float, List[Dict[str, Any]]]] = {}

    def _select_feeds(self, sector: Optional[str] = None) -> List[Dict[str, Any]]:
        """Select feeds matching the given sector.

        Returns all feeds with "all" in their sectors list, plus any
        feeds matching the specific sector.

        Args:
            sector: Sector name (e.g., "technology") or None for all-sector feeds only.

        Returns:
            List of matching feed definitions.
        """
        selected = []
        sector_lower = (sector or "").lower().strip()

        for feed in self._feeds:
            feed_sectors = [s.lower() for s in feed.get("sectors", [])]
            if "all" in feed_sectors:
                selected.append(feed)
            elif sector_lower and sector_lower in feed_sectors:
                selected.append(feed)

        return selected

    async def _fetch_single_feed(
        self,
        feed: Dict[str, Any],
        session: aiohttp.ClientSession,
        max_age_days: int = 7,
    ) -> List[Dict[str, Any]]:
        """Fetch and parse a single RSS feed with caching.

        Args:
            feed: Feed definition dict with name, url, tier.
            session: aiohttp session for HTTP requests.
            max_age_days: Only return entries published within this many days.

        Returns:
            List of normalized article dicts.
        """
        url = feed["url"]
        name = feed["name"]
        tier = feed["tier"]

        # Check cache
        if url in self._cache:
            cached_time, cached_entries = self._cache[url]
            if time.time() - cached_time < self.cache_ttl:
                logger.debug("RSS cache hit for %s", name)
                return cached_entries

        # Fetch feed
        try:
            async with session.get(
                url,
                timeout=aiohttp.ClientTimeout(total=15),
                headers={"User-Agent": "MarketResearch/1.0"},
            ) as resp:
                if resp.status != 200:
                    logger.warning("RSS fetch failed for %s: HTTP %d", name, resp.status)
                    return []
                raw = await resp.text()
        except Exception as e:
            logger.warning("RSS fetch error for %s: %s", name, e)
            return []

        # Parse feed
        parsed = await asyncio.to_thread(feedparser.parse, raw)
        if not parsed.entries:
            logger.debug("RSS feed %s returned 0 entries", name)
            self._cache[url] = (time.time(), [])
            return []

        # Normalize entries and filter by age
        cutoff = datetime.now(timezone.utc) - timedelta(days=max_age_days)
        articles = []

        for entry in parsed.entries:
            # Convert feedparser entry to plain dict for _normalize_entry
            entry_dict = {
                "title": getattr(entry, "title", ""),
                "link": getattr(entry, "link", ""),
                "summary": getattr(entry, "summary", ""),
                "published": getattr(entry, "published", ""),
                "published_parsed": getattr(entry, "published_parsed", None),
                "author": getattr(entry, "author", ""),
            }
            article = _normalize_entry(entry_dict, source_name=name, tier=tier)
            if not article:
                continue

            # Filter by recency
            if article["published_at"]:
                try:
                    pub_dt = datetime.fromisoformat(article["published_at"].replace("Z", "+00:00"))
                    if pub_dt < cutoff:
                        continue
                except (ValueError, TypeError):
                    pass  # Keep articles with unparseable dates

            articles.append(article)

        # Update cache
        self._cache[url] = (time.time(), articles)
        logger.info("RSS feed %s: %d articles (from %d entries)", name, len(articles), len(parsed.entries))

        return articles

    async def fetch_feeds(
        self,
        ticker: str,
        sector: Optional[str] = None,
        max_age_days: int = 7,
    ) -> List[Dict[str, Any]]:
        """Fetch articles from all relevant RSS feeds concurrently.

        Args:
            ticker: Stock ticker symbol (used for logging, not filtering —
                    relevance filtering happens in the news agent).
            sector: Optional sector for sector-specific feed selection.
            max_age_days: Only return entries published within this many days.

        Returns:
            List of normalized article dicts from all feeds.
        """
        feeds = self._select_feeds(sector)
        if not feeds:
            return []

        # Check aggregate results cache
        cache_key = f"{sector or 'all'}:{max_age_days}"
        if cache_key in self._results_cache:
            cached_time, cached_results = self._results_cache[cache_key]
            if time.time() - cached_time < self.cache_ttl:
                logger.debug("RSS results cache hit for %s (sector=%s)", ticker, sector or "all")
                return cached_results

        logger.info("Fetching %d RSS feeds for %s (sector=%s)", len(feeds), ticker, sector or "all")

        async with aiohttp.ClientSession() as session:
            tasks = [
                self._fetch_single_feed(feed, session, max_age_days)
                for feed in feeds
            ]
            results = await asyncio.gather(*tasks, return_exceptions=True)

        all_articles = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.warning("RSS feed %s failed: %s", feeds[i]["name"], result)
            elif isinstance(result, list):
                all_articles.extend(result)

        # Store aggregate results in cache
        self._results_cache[cache_key] = (time.time(), all_articles)

        logger.info("RSS total: %d articles from %d feeds for %s", len(all_articles), len(feeds), ticker)
        return all_articles
