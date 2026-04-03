"""Tests for news agent integration with RSS feeds and quality filter."""

import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from src.agents.news_agent import NewsAgent


def _make_config(**overrides):
    """Build a minimal config dict for NewsAgent."""
    defaults = {
        "TAVILY_ENABLED": False,
        "TAVILY_NEWS_ENABLED": False,
        "RSS_ENABLED": True,
        "RSS_CACHE_TTL": 900,
        "NEWS_QUALITY_FILTER_ENABLED": True,
        "MAX_NEWS_ARTICLES": 20,
        "TWITTER_BEARER_TOKEN": "",
        "NEWS_LOOKBACK_DAYS": 7,
    }
    defaults.update(overrides)
    return defaults


class TestNewsAgentRSSIntegration:
    """Tests for RSS feed integration in fetch_data()."""

    @pytest.mark.asyncio
    async def test_rss_articles_included_in_fetch(self):
        """When RSS is enabled and Tavily is disabled, RSS articles should appear."""
        agent = NewsAgent("AAPL", _make_config(TAVILY_ENABLED=False))
        mock_rss_articles = [
            {"title": "Apple Earnings Beat", "url": "https://reuters.com/a", "source": "Reuters", "source_tier": 1, "description": "AAPL beats", "content": "", "published_at": "2026-04-03T12:00:00Z", "rss_source": True},
        ]
        with patch("src.agents.news_agent.RSSClient") as MockRSSClient:
            mock_instance = MockRSSClient.return_value
            mock_instance.fetch_feeds = AsyncMock(return_value=mock_rss_articles)
            with patch.object(agent, "_fetch_twitter_posts", new_callable=AsyncMock, return_value=[]):
                with patch.object(agent, "_get_company_info", new_callable=AsyncMock, return_value={"long_name": "Apple Inc.", "short_name": "Apple", "sector": "Technology", "industry": "Consumer Electronics"}):
                    result = await agent.fetch_data()
                    assert len(result["articles"]) == 1
                    assert result["articles"][0]["rss_source"] is True
                    assert "rss" in result["source"]

    @pytest.mark.asyncio
    async def test_rss_disabled_skips_fetch(self):
        """When RSS_ENABLED is False, no RSS articles should be fetched."""
        agent = NewsAgent("AAPL", _make_config(RSS_ENABLED=False, TAVILY_ENABLED=False))
        with patch("src.agents.news_agent.RSSClient") as MockRSSClient:
            with patch.object(agent, "_fetch_twitter_posts", new_callable=AsyncMock, return_value=[]):
                with patch.object(agent, "_get_company_info", new_callable=AsyncMock, return_value={"long_name": "Apple Inc.", "short_name": "Apple", "sector": "Technology", "industry": "Consumer Electronics"}):
                    result = await agent.fetch_data()
                    MockRSSClient.assert_not_called()


class TestNewsAgentQualityFilter:
    """Tests for quality filter integration in analyze()."""

    @pytest.mark.asyncio
    async def test_quality_filter_removes_spam(self):
        """Spam articles should be filtered out in analyze()."""
        agent = NewsAgent("AAPL", _make_config())
        agent._company_info = {"long_name": "Apple Inc.", "short_name": "Apple", "sector": "Technology", "industry": "Consumer Electronics"}
        raw_data = {
            "articles": [
                {"title": "Apple Reports Record Revenue", "url": "https://reuters.com/a", "description": "Strong quarter for Apple Inc.", "content": "Apple reported...", "source": "reuters", "relevance_score": 0.9, "source_tier": 1},
                {"title": "Top 5 Stocks to Buy Now", "url": "https://seo-spam.com/a", "description": "Best stock picks", "content": "", "source": "seo-spam.com", "relevance_score": 0.3, "source_tier": 3},
            ],
            "source": "tavily,rss",
            "twitter_posts": [],
            "tavily_summary": None,
            "company_info": {"long_name": "Apple Inc.", "short_name": "Apple", "sector": "Technology", "industry": "Consumer Electronics"},
        }
        result = await agent.analyze(raw_data)
        assert result["total_count"] == 1
        titles = [a["title"] for a in result["articles"]]
        assert "Top 5 Stocks to Buy Now" not in titles

    @pytest.mark.asyncio
    async def test_quality_filter_diagnostics_in_output(self):
        """Filter diagnostics should appear in the analysis output."""
        agent = NewsAgent("AAPL", _make_config())
        agent._company_info = {"long_name": "Apple Inc.", "short_name": "Apple", "sector": "", "industry": ""}
        raw_data = {
            "articles": [
                {"title": "Apple News", "url": "https://reuters.com/a", "description": "AAPL stock update", "content": "", "source": "reuters", "relevance_score": 0.9, "source_tier": 1},
            ],
            "source": "rss",
            "twitter_posts": [],
            "tavily_summary": None,
            "company_info": {"long_name": "Apple Inc.", "short_name": "Apple", "sector": "", "industry": ""},
        }
        result = await agent.analyze(raw_data)
        assert "quality_filter" in result
        assert "total_input" in result["quality_filter"]

    @pytest.mark.asyncio
    async def test_quality_filter_disabled(self):
        """When NEWS_QUALITY_FILTER_ENABLED is False, no filtering should occur."""
        agent = NewsAgent("AAPL", _make_config(NEWS_QUALITY_FILTER_ENABLED=False))
        agent._company_info = {"long_name": "Apple Inc.", "short_name": "Apple", "sector": "", "industry": ""}
        raw_data = {
            "articles": [
                {"title": "Top 5 Stocks to Buy", "url": "https://spam.com/a", "description": "AAPL included", "content": "", "source": "spam.com", "relevance_score": 0.3, "source_tier": 3},
            ],
            "source": "rss",
            "twitter_posts": [],
            "tavily_summary": None,
            "company_info": {"long_name": "Apple Inc.", "short_name": "Apple", "sector": "", "industry": ""},
        }
        result = await agent.analyze(raw_data)
        assert result["total_count"] == 1
