"""News agent for gathering financial news articles with smart relevance filtering."""

import aiohttp
import asyncio
import yfinance as yf
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from .base_agent import BaseAgent
from ..tavily_client import get_tavily_client
from ..rss_client import RSSClient
from ..news_quality_filter import run_quality_filter


class NewsAgent(BaseAgent):
    """Agent for fetching financial news from various sources with relevance filtering.

    Data source priority:
        1. Tavily AI Search (primary - best relevance, full content, AI summary)
        2. OpenBB Platform (secondary - broad financial news coverage)

    Supplementary sources (always fetched when configured):
        - Twitter/X API v2 (search/recent with cashtag filtering)
    """

    RELEVANCE_THRESHOLD = 0.15  # Minimum score to keep an article (very permissive)
    TWITTER_API_BASE_URL = "https://api.twitter.com/2"

    # ──────────────────────────────────────────────
    # Tavily AI Search (Primary Source)
    # ──────────────────────────────────────────────

    async def _fetch_tavily_news(self) -> Optional[Dict[str, Any]]:
        """
        Fetch news from Tavily AI Search (primary source).
        
        Tavily provides:
        - Superior relevance scoring
        - Full article content extraction
        - AI-generated summaries
        - No rate limiting issues
        
        Returns:
            Dict with articles and AI summary, or None if disabled/failed
        """
        if not self.config.get("TAVILY_ENABLED", True):
            return None
        
        if not self.config.get("TAVILY_NEWS_ENABLED", True):
            return None
        
        tavily = get_tavily_client(self.config)
        if not tavily.is_available:
            self.logger.info(f"Tavily not available for {self.ticker}")
            return None
        
        # Get company info for better query
        company_info = await self._get_company_info()
        self._company_info = company_info
        
        # Build query with company name and ticker
        company_name = company_info.get("long_name") or company_info.get("short_name", "")
        query_parts = [f"${self.ticker}"]
        if company_name:
            query_parts.insert(0, company_name)
        query = f"{' '.join(query_parts)} stock news"
        
        max_results = self.config.get("TAVILY_MAX_RESULTS", 20)
        days = self.config.get("TAVILY_NEWS_DAYS", 7)
        search_depth = self.config.get("TAVILY_SEARCH_DEPTH", "advanced")
        
        self.logger.info(f"Fetching {self.ticker} news from Tavily (primary)")
        
        try:
            result = await tavily.search_news(
                query=query,
                max_results=max_results,
                days=days,
                include_answer=True,
                include_raw_content=True,
                search_depth=search_depth
            )
            
            if not result.get("success"):
                self.logger.warning(f"Tavily search failed: {result.get('error')}")
                return None
            
            articles = result.get("articles", [])
            if not articles:
                self.logger.info(f"Tavily returned no articles for {self.ticker}")
                return None
            
            # Mark source and add AI summary
            for article in articles:
                article["source"] = "tavily"
                # Tavily articles already have relevance_score
            
            self.logger.info(
                f"Tavily returned {len(articles)} articles for {self.ticker} "
                f"(AI summary: {'yes' if result.get('ai_summary') else 'no'})"
            )
            
            return {
                "articles": articles,
                "ai_summary": result.get("ai_summary"),
                "total_count": len(articles),
                "source": "tavily"
            }
            
        except Exception as e:
            self.logger.warning(f"Tavily news fetch failed for {self.ticker}: {e}")
            return None

    # ──────────────────────────────────────────────
    # Twitter/X API
    # ──────────────────────────────────────────────

    async def _fetch_twitter_posts(self) -> List[Dict[str, Any]]:
        """
        Fetch recent tweets mentioning the ticker's cashtag from Twitter/X API v2.

        Uses the search/recent endpoint with engagement filtering to surface
        quality financial discussion and filter out spam/bots.

        Returns:
            List of tweet dicts, or empty list on failure
        """
        bearer_token = self.config.get("TWITTER_BEARER_TOKEN", "")
        if not bearer_token:
            return []

        max_results = min(self.config.get("TWITTER_MAX_RESULTS", 20), 100)
        min_engagement = self.config.get("TWITTER_MIN_ENGAGEMENT", 2)

        query = f"${self.ticker} -is:retweet lang:en"
        url = f"{self.TWITTER_API_BASE_URL}/tweets/search/recent"
        params = {
            "query": query,
            "max_results": str(max(max_results, 10)),
            "tweet.fields": "created_at,public_metrics,author_id,context_annotations,conversation_id",
        }
        headers = {"Authorization": f"Bearer {bearer_token}"}

        try:
            session = getattr(self, '_shared_session', None)
            if session and not session.closed:
                tweets = await self._do_twitter_request(session, url, params, headers)
            else:
                async with aiohttp.ClientSession() as fallback_session:
                    tweets = await self._do_twitter_request(fallback_session, url, params, headers)

            if not tweets:
                return []

            # Filter by minimum engagement and format
            filtered = []
            for tweet in tweets:
                metrics = tweet.get("public_metrics", {})
                engagement = (
                    metrics.get("like_count", 0)
                    + metrics.get("retweet_count", 0)
                    + metrics.get("reply_count", 0)
                )
                if engagement >= min_engagement:
                    filtered.append({
                        "id": tweet.get("id", ""),
                        "text": tweet.get("text", ""),
                        "created_at": tweet.get("created_at", ""),
                        "author_id": tweet.get("author_id", ""),
                        "conversation_id": tweet.get("conversation_id", ""),
                        "metrics": {
                            "likes": metrics.get("like_count", 0),
                            "retweets": metrics.get("retweet_count", 0),
                            "replies": metrics.get("reply_count", 0),
                        },
                        "engagement": engagement,
                        "url": f"https://x.com/i/status/{tweet.get('id', '')}",
                    })

            # Sort by engagement descending
            filtered.sort(key=lambda t: t["engagement"], reverse=True)

            # Batch-resolve author metadata (username, verified, followers)
            if filtered:
                author_ids = list({t["author_id"] for t in filtered if t["author_id"]})
                author_map = await self._lookup_twitter_authors(
                    author_ids, bearer_token, session if (session and not session.closed) else None
                )
                for tweet in filtered:
                    author = author_map.get(tweet["author_id"], {})
                    tweet["author_username"] = author.get("username", "")
                    tweet["author_name"] = author.get("name", "")
                    tweet["author_verified"] = author.get("verified", False)
                    tweet["author_followers"] = author.get("followers_count", 0)

            self.logger.info(
                f"Twitter/X returned {len(tweets)} tweets for ${self.ticker}, "
                f"{len(filtered)} passed engagement filter (>={min_engagement})"
            )
            return filtered

        except Exception as e:
            self.logger.warning(f"Twitter/X fetch failed for {self.ticker}: {e}")
            return []

    async def _do_twitter_request(
        self,
        session: aiohttp.ClientSession,
        url: str,
        params: Dict[str, str],
        headers: Dict[str, str],
    ) -> Optional[List[Dict[str, Any]]]:
        """
        Execute the actual Twitter API HTTP request.

        Args:
            session: aiohttp session
            url: API endpoint URL
            params: Query parameters
            headers: Request headers with Bearer auth

        Returns:
            List of tweet dicts, or None on failure
        """
        async with session.get(
            url,
            params=params,
            headers=headers,
            timeout=aiohttp.ClientTimeout(total=10),
        ) as resp:
            if resp.status == 401:
                self.logger.warning("Twitter/X API: unauthorized (invalid bearer token)")
                return None
            if resp.status == 429:
                self.logger.warning("Twitter/X API: rate limited")
                return None
            if resp.status != 200:
                body = await resp.text()
                self.logger.warning(f"Twitter/X API returned status {resp.status}: {body[:200]}")
                return None

            data = await resp.json()
            return data.get("data", [])

    async def _lookup_twitter_authors(
        self,
        author_ids: List[str],
        bearer_token: str,
        session: Optional[aiohttp.ClientSession] = None,
    ) -> Dict[str, Dict[str, Any]]:
        """Batch-resolve Twitter author IDs to usernames and metadata.

        Args:
            author_ids: List of Twitter user IDs
            bearer_token: Twitter API bearer token
            session: Optional aiohttp session to reuse

        Returns:
            Dict mapping author_id to {username, name, verified, followers_count}
        """
        if not author_ids:
            return {}

        author_map = {}
        headers = {"Authorization": f"Bearer {bearer_token}"}
        # Twitter v2 /users endpoint accepts up to 100 IDs per request
        for i in range(0, len(author_ids), 100):
            batch = author_ids[i:i + 100]
            url = f"{self.TWITTER_API_BASE_URL}/users"
            params = {
                "ids": ",".join(batch),
                "user.fields": "username,name,verified,public_metrics,verified_type",
            }
            try:
                async def _do_lookup(s):
                    async with s.get(url, params=params, headers=headers,
                                     timeout=aiohttp.ClientTimeout(total=10)) as resp:
                        if resp.status != 200:
                            return []
                        data = await resp.json()
                        return data.get("data", [])

                if session and not session.closed:
                    users = await _do_lookup(session)
                else:
                    async with aiohttp.ClientSession() as fallback:
                        users = await _do_lookup(fallback)

                for user in users:
                    uid = user.get("id", "")
                    pub = user.get("public_metrics", {})
                    author_map[uid] = {
                        "username": user.get("username", ""),
                        "name": user.get("name", ""),
                        "verified": bool(user.get("verified") or user.get("verified_type")),
                        "followers_count": pub.get("followers_count", 0),
                    }
            except Exception as e:
                self.logger.debug(f"Twitter user lookup failed: {e}")

        return author_map

    # ──────────────────────────────────────────────
    # Company Info Lookup
    # ──────────────────────────────────────────────

    async def _get_company_info(self) -> Dict[str, str]:
        """
        Resolve ticker to company name, sector, and industry.

        Tries two sources in order:
        1. yfinance (rich data: long_name, short_name, sector, industry)
        2. SEC EDGAR company_tickers.json (fallback: just company title)

        Returns:
            Dict with long_name, short_name, sector, industry (empty strings on failure)
        """
        default = {"long_name": "", "short_name": "", "sector": "", "industry": ""}

        # Try yfinance first (richest data)
        info = await self._retry_fetch(
            lambda: yf.Ticker(self.ticker).info,
            label=f"{self.ticker} yfinance info"
        )

        if info and isinstance(info, dict) and info.get("longName"):
            return {
                "long_name": info.get("longName", "") or "",
                "short_name": info.get("shortName", "") or "",
                "sector": info.get("sector", "") or "",
                "industry": info.get("industry", "") or "",
            }

        # Fallback: SEC EDGAR company_tickers.json (free, no rate limit)
        self.logger.info(f"yfinance failed for {self.ticker}, trying SEC EDGAR fallback")
        try:
            sec_name = await self._get_company_name_from_sec()
            if sec_name:
                self.logger.info(f"SEC EDGAR resolved {self.ticker} → '{sec_name}'")
                return {
                    "long_name": sec_name,
                    "short_name": "",
                    "sector": "",
                    "industry": "",
                }
        except Exception as e:
            self.logger.warning(f"SEC EDGAR fallback failed for {self.ticker}: {e}")

        self.logger.warning(f"Could not resolve company info for {self.ticker}")
        return default

    async def _get_company_name_from_sec(self) -> Optional[str]:
        """
        Look up company name from SEC EDGAR company_tickers.json.

        This is a free, unthrottled endpoint that maps tickers to company names.

        Returns:
            Company title string, or None if not found
        """
        url = "https://www.sec.gov/files/company_tickers.json"
        user_agent = self.config.get(
            "SEC_EDGAR_USER_AGENT",
            "MarketResearch/1.0 (research@example.com)"
        )

        async with aiohttp.ClientSession() as session:
            headers = {"User-Agent": user_agent}
            async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    # Data structure: {"0": {"cik_str": 320193, "ticker": "AAPL", "title": "Apple Inc."}, ...}
                    for entry in data.values():
                        if entry.get("ticker", "").upper() == self.ticker:
                            return entry.get("title", "")
        return None

    @staticmethod
    def _extract_core_name(company_name: str) -> str:
        """
        Extract the core brand/company name by stripping common suffixes.

        'Apple Inc.' → 'Apple'
        'Bloom Energy Corporation' → 'Bloom Energy'
        'NVIDIA Corporation' → 'NVIDIA'
        'Microsoft Corp' → 'Microsoft'
        'Alphabet Inc. Class A' → 'Alphabet'

        Args:
            company_name: Full legal company name

        Returns:
            Core name stripped of suffixes, or empty string
        """
        if not company_name:
            return ""

        name = company_name.strip()

        # Remove common corporate suffixes (order matters — longest first)
        # Include comma variants (e.g., "Tesla, Inc." → "Tesla")
        suffixes = [
            ", Incorporated", ", Inc.", ", Inc", ", Limited", ", Ltd.", ", Ltd",
            " Corporation", " Corp.", " Corp", " Incorporated", " Inc.",
            " Inc", " Limited", " Ltd.", " Ltd", " Holdings",
            " Group", " & Co.", " & Co", " Co.", " Co",
            " PLC", " plc", " S.A.", " N.V.",
            " SE", " AG", " Class A", " Class B", " Class C",
        ]

        # Apply multiple passes to handle "Alphabet Inc. Class A" → "Alphabet"
        changed = True
        while changed:
            changed = False
            for suffix in suffixes:
                if name.endswith(suffix):
                    name = name[: -len(suffix)].strip()
                    changed = True
                    break  # Restart suffix loop after each strip

        # If the result is the same as input or very short (1-2 chars), not useful
        if len(name) <= 2:
            return ""

        return name

    def _build_news_query(self, company_info: Dict[str, str]) -> str:
        """
        Build a precise NewsAPI query using company name + financial identifiers.

        For BE (Bloom Energy):
            "Bloom Energy" OR "$BE" OR "BE stock"

        For NVDA (long ticker, less ambiguous):
            "NVIDIA Corporation" OR "NVIDIA" OR "$NVDA" OR "NVDA stock" OR NVDA

        Args:
            company_info: Dict from _get_company_info()

        Returns:
            NewsAPI query string with OR operators and quoted phrases
        """
        parts = []
        seen_lower = set()  # Avoid duplicate query parts

        long_name = company_info.get("long_name", "").strip()
        short_name = company_info.get("short_name", "").strip()
        core_name = self._extract_core_name(long_name)

        # Company long name in quotes (strongest signal)
        if long_name:
            parts.append(f'"{long_name}"')
            seen_lower.add(long_name.lower())

        # Core name in quotes (e.g., "Apple" from "Apple Inc.")
        if core_name and core_name.lower() not in seen_lower:
            parts.append(f'"{core_name}"')
            seen_lower.add(core_name.lower())

        # Company short name in quotes (if different from above)
        if short_name and short_name.lower() not in seen_lower:
            parts.append(f'"{short_name}"')
            seen_lower.add(short_name.lower())

        # Cashtag (always include — very precise)
        parts.append(f'"${self.ticker}"')

        # "TICKER stock" phrase (always include — disambiguates)
        parts.append(f'"{self.ticker} stock"')

        # Bare ticker only for 4+ character tickers (avoids false matches for short tickers like BE, A, C, F)
        if len(self.ticker) >= 4:
            parts.append(self.ticker)

        query = " OR ".join(parts)
        self.logger.info(f"Built news query for {self.ticker}: {query}")
        return query

    def _score_article_relevance(
        self,
        article: Dict[str, Any],
        company_info: Dict[str, str]
    ) -> float:
        """
        Score an article's relevance to the target company (0.0 to 1.0).

        Scoring signals:
            - Company long name in title:       +0.5
            - Company short name in title:      +0.4
            - Company name in description:      +0.2
            - Cashtag $TICKER anywhere:         +0.4
            - "TICKER stock/shares" anywhere:   +0.3
            - Bare ticker in title + financial context: +0.2
            - Sector/industry keyword:          +0.05

        Args:
            article: Article dictionary
            company_info: Dict from _get_company_info()

        Returns:
            Relevance score capped at 1.0
        """
        score = 0.0

        title = (article.get("title") or "").lower()
        description = (article.get("description") or "").lower()
        content_snippet = (article.get("content") or "").lower()
        all_text = f"{title} {description} {content_snippet}"

        long_name = (company_info.get("long_name") or "").lower().strip()
        short_name = (company_info.get("short_name") or "").lower().strip()
        core_name = self._extract_core_name(company_info.get("long_name", "")).lower().strip()
        sector = (company_info.get("sector") or "").lower().strip()
        industry = (company_info.get("industry") or "").lower().strip()
        ticker_lower = self.ticker.lower()

        # Financial context keywords (used for disambiguation of short/ambiguous names)
        financial_context = [
            "stock", "shares", "earnings", "revenue", "profit", "analyst",
            "market", "trading", "investor", "dividend", "quarterly", "eps",
            "forecast", "guidance", "upgrade", "downgrade", "target", "rating",
            "buy", "sell", "hold", "bullish", "bearish", "ipo", "valuation",
            "sec", "filing", "report", "growth", "decline", "surge", "rally",
            "plunge", "soar", "tumble", "beat", "miss", "outlook", "estimate"
        ]

        # Company long name in title (strongest signal)
        if long_name and long_name in title:
            score += 0.5
        # Company long name in description/content
        elif long_name and long_name in all_text:
            score += 0.2

        # Core name in title (e.g., "Apple" from "Apple Inc.")
        # For short core names (≤6 chars like "Apple"), require financial context to avoid
        # false positives like "apple recipes" or "best apple pie"
        if core_name and core_name != long_name and core_name in title:
            if len(core_name) > 6 or any(kw in all_text for kw in financial_context):
                score += 0.4
            else:
                score += 0.1  # Weak signal without financial context
        # Core name in description/content
        elif core_name and core_name != long_name and core_name in all_text:
            if len(core_name) > 6 or any(kw in all_text for kw in financial_context):
                score += 0.15
            else:
                score += 0.05

        # Company short name in title
        if short_name and short_name != long_name and short_name != core_name and short_name in title:
            score += 0.4
        # Company short name in description/content
        elif short_name and short_name != long_name and short_name != core_name and short_name in all_text:
            score += 0.2

        # Cashtag $TICKER anywhere (very precise signal)
        cashtag = f"${ticker_lower}"
        if cashtag in all_text:
            score += 0.4

        # "TICKER stock" or "TICKER shares" anywhere
        if f"{ticker_lower} stock" in all_text or f"{ticker_lower} shares" in all_text:
            score += 0.3

        # Bare ticker in title with financial context words
        # Skip for very short tickers (1-2 chars like BE, A, C, F) since they match
        # common English words. Only apply for 3+ char tickers.
        title_words = title.split()
        all_words = set(all_text.split())
        if len(self.ticker) >= 3 and ticker_lower in title_words:
            # Use word-boundary matching for financial context to avoid substring matches
            # (e.g., "eps" in "Epstein")
            if any(kw in all_words for kw in financial_context):
                score += 0.2

        # Sector/industry keyword (weak signal but adds up)
        if sector and sector in all_text:
            score += 0.05
        if industry and industry in all_text:
            score += 0.05

        return min(score, 1.0)

    async def fetch_data(self) -> Dict[str, Any]:
        """
        Fetch news articles from multiple sources concurrently.

        Sources (all concurrent):
            1. Tavily AI Search (primary)
            2. RSS feeds (supplementary)
            3. Twitter/X posts (supplementary)

        Fallback: OpenBB Platform if Tavily + RSS both return nothing.

        Returns:
            Dictionary with news articles, twitter posts, and company info
        """
        articles = []
        twitter_posts = []
        sources = []
        tavily_summary = None

        max_articles = self.config.get("MAX_NEWS_ARTICLES", 20)
        rss_enabled = self.config.get("RSS_ENABLED", True)

        # ── Resolve company info first (needed for RSS sector matching) ──
        company_info = await self._get_company_info()
        self._company_info = company_info
        sector = company_info.get("sector", "")

        # ── Launch concurrent fetches ──
        twitter_task = asyncio.create_task(self._fetch_twitter_posts())
        tavily_task = asyncio.create_task(self._fetch_tavily_news())

        rss_task = None
        if rss_enabled:
            rss_client = RSSClient(cache_ttl=self.config.get("RSS_CACHE_TTL", 900))
            rss_task = asyncio.create_task(rss_client.fetch_feeds(
                ticker=self.ticker,
                sector=sector,
                max_age_days=self.config.get("NEWS_LOOKBACK_DAYS", 7),
            ))

        # ── Await Tavily ──
        try:
            tavily_result = await tavily_task
            if tavily_result and tavily_result.get("articles"):
                articles.extend(tavily_result["articles"])
                sources.append("tavily")
                tavily_summary = tavily_result.get("ai_summary")
                self.logger.info(f"Tavily returned {len(tavily_result['articles'])} articles for {self.ticker}")
        except Exception as e:
            self.logger.warning(f"Tavily search failed: {e}")

        # ── Await RSS ──
        if rss_task:
            try:
                rss_articles = await rss_task
                if rss_articles:
                    articles.extend(rss_articles)
                    sources.append("rss")
                    self.logger.info(f"RSS returned {len(rss_articles)} articles for {self.ticker}")
            except Exception as e:
                self.logger.warning(f"RSS fetch failed: {e}")

        # ── Fallback to OpenBB if no articles yet ──
        if not articles:
            data_provider = getattr(self, "_data_provider", None)
            if data_provider:
                self.logger.info(f"Fetching {self.ticker} news from OpenBB Platform (fallback)")
                try:
                    obb_articles = await data_provider.get_news(self.ticker, limit=max_articles)
                    if obb_articles and len(obb_articles) > 0:
                        articles.extend(obb_articles)
                        sources.append("openbb")
                        self.logger.info(f"OpenBB returned {len(obb_articles)} news articles for {self.ticker}")
                except Exception as e:
                    self.logger.warning(f"OpenBB news fetch failed for {self.ticker}: {e}")

        # ── Await Twitter ──
        try:
            twitter_posts = await twitter_task
        except Exception as e:
            self.logger.warning(f"Twitter fetch failed: {e}")
            twitter_posts = []

        source_str = ",".join(sources) if sources else "none"

        return {
            "articles": articles,
            "ticker": self.ticker,
            "total_count": len(articles),
            "company_info": company_info,
            "source": source_str,
            "twitter_posts": twitter_posts,
            "tavily_summary": tavily_summary,
        }

    async def analyze(self, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze news articles with relevance filtering, quality filtering, and categorization.

        Pipeline:
            1. Relevance scoring (existing)
            2. Quality filter — tier gate, heuristics, deduplication (new)
            3. Categorization (existing)

        Args:
            raw_data: Raw news data from fetch_data()

        Returns:
            Analyzed news data with filtered articles and diagnostics
        """
        articles = raw_data.get("articles", [])
        company_info = getattr(self, "_company_info", None) or raw_data.get("company_info", {})
        data_source = raw_data.get("source", "unknown")

        if not articles:
            return {
                "articles": [],
                "total_count": 0,
                "filtered_count": 0,
                "categories": {},
                "recent_count": 0,
                "quality_filter": {},
                "summary": "No news articles found for this ticker."
            }

        # ── Stage 1: Relevance scoring ──
        scored_articles = []
        for article in articles:
            if "relevance_score" in article:
                scored_articles.append(article)
            else:
                relevance = self._score_article_relevance(article, company_info)
                article_with_score = {**article, "relevance_score": round(relevance, 3)}
                scored_articles.append(article_with_score)

        scored_articles.sort(key=lambda a: a["relevance_score"], reverse=True)

        # Filter out articles below relevance threshold
        relevance_filtered = [
            a for a in scored_articles if a["relevance_score"] >= self.RELEVANCE_THRESHOLD
        ]
        relevance_removed = len(articles) - len(relevance_filtered)
        if relevance_removed > 0:
            self.logger.info(
                f"Relevance filter: kept {len(relevance_filtered)}/{len(articles)} articles "
                f"for {self.ticker} (removed {relevance_removed} below {self.RELEVANCE_THRESHOLD} threshold)"
            )

        # ── Stage 2: Quality filter ──
        quality_diagnostics = {}
        if self.config.get("NEWS_QUALITY_FILTER_ENABLED", True) and relevance_filtered:
            filter_result = run_quality_filter(relevance_filtered)
            filtered_articles = filter_result.passed
            quality_diagnostics = {
                "total_input": filter_result.diagnostics.total_input,
                "total_passed": filter_result.diagnostics.total_passed,
                "removed_listicle": filter_result.diagnostics.removed_listicle,
                "removed_affiliate": filter_result.diagnostics.removed_affiliate,
                "removed_press_release": filter_result.diagnostics.removed_press_release,
                "removed_duplicate": filter_result.diagnostics.removed_duplicate,
            }
        else:
            filtered_articles = relevance_filtered

        if not filtered_articles:
            total_removed = relevance_removed + (len(relevance_filtered) - len(filtered_articles))
            return {
                "articles": [],
                "total_count": 0,
                "filtered_count": total_removed,
                "categories": {},
                "recent_count": 0,
                "quality_filter": quality_diagnostics,
                "summary": f"No relevant news articles found for {self.ticker}. "
                           f"{total_removed} articles were removed by filters."
            }

        # ── Stage 3: Categorization and summary (existing logic) ──
        categorized = self._categorize_articles(filtered_articles)
        recent_count = self._count_recent_articles(filtered_articles, hours=24)
        key_headlines = self._extract_key_headlines(filtered_articles, limit=5)

        twitter_posts = raw_data.get("twitter_posts", [])
        twitter_buzz = self._build_twitter_buzz(twitter_posts)
        tavily_summary = raw_data.get("tavily_summary")

        total_removed = relevance_removed + (len(relevance_filtered) - len(filtered_articles))

        analysis = {
            "articles": filtered_articles,
            "total_count": len(filtered_articles),
            "filtered_count": total_removed,
            "categories": categorized,
            "recent_count": recent_count,
            "key_headlines": key_headlines,
            "twitter_posts": twitter_posts,
            "twitter_buzz": twitter_buzz,
            "tavily_summary": tavily_summary,
            "quality_filter": quality_diagnostics,
            "summary": self._generate_summary(filtered_articles, recent_count, total_removed, twitter_buzz, tavily_summary)
        }

        return analysis

    def _categorize_articles(self, articles: List[Dict[str, Any]]) -> Dict[str, int]:
        """
        Categorize articles by topic.

        Args:
            articles: List of articles

        Returns:
            Dictionary with category counts
        """
        categories = {
            "earnings": 0,
            "product": 0,
            "leadership": 0,
            "market": 0,
            "regulatory": 0,
            "other": 0
        }

        earnings_keywords = ["earnings", "revenue", "profit", "eps", "quarterly", "q1", "q2", "q3", "q4"]
        product_keywords = ["product", "launch", "release", "innovation", "technology"]
        leadership_keywords = ["ceo", "cfo", "executive", "director", "appointment", "resignation"]
        market_keywords = ["market", "shares", "stock", "trading", "analyst", "upgrade", "downgrade"]
        regulatory_keywords = ["sec", "fda", "regulatory", "compliance", "lawsuit", "investigation"]

        for article in articles:
            title = (article.get("title") or "").lower()
            description = (article.get("description") or "").lower()
            content = title + " " + description

            categorized = False

            if any(keyword in content for keyword in earnings_keywords):
                categories["earnings"] += 1
                categorized = True
            if any(keyword in content for keyword in product_keywords):
                categories["product"] += 1
                categorized = True
            if any(keyword in content for keyword in leadership_keywords):
                categories["leadership"] += 1
                categorized = True
            if any(keyword in content for keyword in market_keywords):
                categories["market"] += 1
                categorized = True
            if any(keyword in content for keyword in regulatory_keywords):
                categories["regulatory"] += 1
                categorized = True

            if not categorized:
                categories["other"] += 1

        return categories

    def _count_recent_articles(self, articles: List[Dict[str, Any]], hours: int = 24) -> int:
        """Count articles published in the last N hours."""
        cutoff = datetime.now() - timedelta(hours=hours)
        recent = 0

        for article in articles:
            published_str = article.get("published_at")
            if published_str:
                try:
                    # Parse ISO format datetime
                    published = datetime.fromisoformat(published_str.replace("Z", "+00:00"))
                    # Make cutoff timezone-aware if published is
                    if published.tzinfo:
                        from datetime import timezone
                        cutoff = cutoff.replace(tzinfo=timezone.utc)

                    if published > cutoff:
                        recent += 1
                except Exception as e:
                    self.logger.warning(f"Failed to parse date {published_str}: {e}")

        return recent

    def _extract_key_headlines(
        self,
        articles: List[Dict[str, Any]],
        limit: int = 5
    ) -> List[Dict[str, str]]:
        """Extract key headlines from the most relevant articles."""
        headlines = []

        for article in articles[:limit]:
            headlines.append({
                "title": article.get("title", ""),
                "source": article.get("source", ""),
                "url": article.get("url", ""),
                "published_at": article.get("published_at", ""),
                "relevance_score": article.get("relevance_score", 0.0)
            })

        return headlines

    def _build_twitter_buzz(self, twitter_posts: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Build summary statistics from Twitter/X posts.

        Args:
            twitter_posts: List of tweet dicts from _fetch_twitter_posts()

        Returns:
            Dictionary with social buzz metrics
        """
        if not twitter_posts:
            return {
                "total_tweets": 0,
                "total_engagement": 0,
                "avg_engagement": 0.0,
                "top_tweets": [],
            }

        total_engagement = sum(t.get("engagement", 0) for t in twitter_posts)
        avg_engagement = total_engagement / len(twitter_posts) if twitter_posts else 0.0

        # Top 5 tweets by engagement for display
        top_tweets = twitter_posts[:5]

        return {
            "total_tweets": len(twitter_posts),
            "total_engagement": total_engagement,
            "avg_engagement": round(avg_engagement, 1),
            "top_tweets": top_tweets,
        }

    def _generate_summary(
        self,
        articles: List[Dict[str, Any]],
        recent_count: int,
        filtered_count: int = 0,
        twitter_buzz: Optional[Dict[str, Any]] = None,
        tavily_summary: Optional[str] = None,
    ) -> str:
        """Generate news summary including filter stats, social buzz, and Tavily insights."""
        total = len(articles)

        if total == 0:
            return "No recent news articles found."

        summary = f"Found {total} relevant news articles"
        if filtered_count > 0:
            summary += f" (filtered {filtered_count} irrelevant)"
        summary += ". "

        summary += f"{recent_count} published in the last 24 hours. "

        # Mention if high news volume
        if recent_count > 5:
            summary += "High news volume indicates significant activity. "
        elif recent_count == 0:
            summary += "Low recent news activity. "

        # Add Twitter/X buzz context
        if twitter_buzz and twitter_buzz.get("total_tweets", 0) > 0:
            tweet_count = twitter_buzz["total_tweets"]
            avg_eng = twitter_buzz["avg_engagement"]
            summary += f"Social buzz: {tweet_count} tweets (avg engagement: {avg_eng:.0f}). "

        # Add Tavily AI summary if available
        if tavily_summary:
            # Truncate if too long
            max_summary_len = 200
            truncated = tavily_summary[:max_summary_len] + "..." if len(tavily_summary) > max_summary_len else tavily_summary
            summary += f"AI Summary: {truncated}"

        return summary
