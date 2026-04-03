"""Tests for RSS client — feed loading, fetching, caching, article normalization."""

import pytest
import time
from unittest.mock import patch, AsyncMock, MagicMock
from src.rss_client import RSSClient, _normalize_entry, _load_feeds


class TestLoadFeeds:
    """Tests for YAML feed registry loading."""

    def test_load_feeds_returns_list(self):
        feeds = _load_feeds()
        assert isinstance(feeds, list)
        assert len(feeds) > 0

    def test_feed_has_required_keys(self):
        feeds = _load_feeds()
        for feed in feeds:
            assert "name" in feed, f"Feed missing 'name': {feed}"
            assert "url" in feed, f"Feed missing 'url': {feed}"
            assert "tier" in feed, f"Feed missing 'tier': {feed}"
            assert "sectors" in feed, f"Feed missing 'sectors': {feed}"

    def test_feed_tiers_are_valid(self):
        feeds = _load_feeds()
        for feed in feeds:
            assert feed["tier"] in (1, 2, 3), f"Invalid tier {feed['tier']} for {feed['name']}"

    def test_feed_sectors_is_list(self):
        feeds = _load_feeds()
        for feed in feeds:
            assert isinstance(feed["sectors"], list), f"sectors not a list for {feed['name']}"

    def test_sector_filtering(self):
        feeds = _load_feeds()
        tech_feeds = [f for f in feeds if "technology" in f["sectors"]]
        all_feeds = [f for f in feeds if "all" in f["sectors"]]
        assert len(all_feeds) > 0
        assert len(tech_feeds) > 0
        for f in tech_feeds:
            if "all" not in f["sectors"]:
                assert "technology" in f["sectors"]


class TestNormalizeEntry:
    """Tests for feedparser entry → article dict normalization."""

    def test_basic_entry(self):
        entry_dict = {
            "title": "Test Article",
            "link": "https://example.com/article",
            "summary": "Test summary",
            "published": "Thu, 03 Apr 2026 12:00:00 GMT",
        }
        result = _normalize_entry(entry_dict, source_name="Test Source", tier=2)
        assert result["title"] == "Test Article"
        assert result["url"] == "https://example.com/article"
        assert result["source"] == "Test Source"
        assert result["source_tier"] == 2
        assert result["rss_source"] is True

    def test_missing_title_returns_none(self):
        entry_dict = {"link": "https://example.com/article"}
        result = _normalize_entry(entry_dict, source_name="Test", tier=1)
        assert result is None

    def test_missing_link_returns_none(self):
        entry_dict = {"title": "Test Article"}
        result = _normalize_entry(entry_dict, source_name="Test", tier=1)
        assert result is None


class TestRSSClient:
    """Tests for RSSClient fetch and caching."""

    def test_select_feeds_all_sector(self):
        client = RSSClient()
        feeds = client._select_feeds(sector=None)
        assert all("all" in f["sectors"] for f in feeds)

    def test_select_feeds_technology(self):
        client = RSSClient()
        feeds = client._select_feeds(sector="technology")
        assert len(feeds) > 0
        sector_specific = [f for f in feeds if "all" not in f["sectors"]]
        assert all("technology" in f["sectors"] for f in sector_specific)

    @pytest.mark.asyncio
    async def test_fetch_feeds_returns_list(self):
        """Integration-style test with mocked HTTP."""
        client = RSSClient()
        mock_article = {
            "title": "Test Article",
            "url": "https://reuters.com/test",
            "source": "Reuters Business",
            "source_tier": 1,
            "description": "Test description about AAPL stock performance",
            "content": "",
            "published_at": "2026-04-03T12:00:00Z",
            "rss_source": True,
        }
        with patch.object(client, "_fetch_single_feed", new_callable=AsyncMock, return_value=[mock_article]):
            articles = await client.fetch_feeds(ticker="AAPL", sector=None)
            assert isinstance(articles, list)

    @pytest.mark.asyncio
    async def test_cache_ttl_prevents_refetch(self):
        """Cached feeds should not re-fetch within TTL."""
        client = RSSClient(cache_ttl=300)
        mock_article = {
            "title": "Cached Article",
            "url": "https://cnbc.com/test",
            "source": "CNBC Finance",
            "source_tier": 1,
            "description": "AAPL test",
            "content": "",
            "published_at": "2026-04-03T12:00:00Z",
            "rss_source": True,
        }
        with patch.object(client, "_fetch_single_feed", new_callable=AsyncMock, return_value=[mock_article]) as mock_fetch:
            await client.fetch_feeds(ticker="AAPL", sector=None)
            await client.fetch_feeds(ticker="AAPL", sector=None)
            first_call_count = mock_fetch.call_count
            await client.fetch_feeds(ticker="AAPL", sector=None)
            assert mock_fetch.call_count == first_call_count
