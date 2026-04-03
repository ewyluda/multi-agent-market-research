"""Tests for news source tier registry."""

import pytest
from src.news_source_tiers import get_source_tier, SOURCE_TIERS


class TestGetSourceTier:
    """Tests for get_source_tier() domain extraction and lookup."""

    def test_tier1_full_url(self):
        assert get_source_tier("https://www.reuters.com/business/some-article") == 1

    def test_tier1_bare_domain(self):
        assert get_source_tier("bloomberg.com") == 1

    def test_tier2_full_url(self):
        assert get_source_tier("https://seekingalpha.com/article/12345") == 2

    def test_tier2_subdomain(self):
        assert get_source_tier("https://finance.fool.com/investing/2026/04/article") == 2

    def test_tier3_unknown_domain(self):
        assert get_source_tier("https://random-finance-blog.com/stocks") == 3

    def test_tier3_empty_string(self):
        assert get_source_tier("") == 3

    def test_tier3_none_safe(self):
        """Passing None should not crash — return default tier."""
        assert get_source_tier(None) == 3

    def test_tier1_with_www_prefix(self):
        assert get_source_tier("https://www.wsj.com/articles/something") == 1

    def test_tier1_with_subdomain(self):
        assert get_source_tier("https://markets.ft.com/data/equities") == 1

    def test_source_tiers_dict_not_empty(self):
        assert len(SOURCE_TIERS) >= 15


class TestSourceTiersCompleteness:
    """Verify all expected tier 1 and tier 2 sources are present."""

    @pytest.mark.parametrize("domain", [
        "reuters.com", "bloomberg.com", "wsj.com", "ft.com",
        "cnbc.com", "barrons.com", "nytimes.com", "apnews.com",
    ])
    def test_tier1_sources(self, domain):
        assert SOURCE_TIERS[domain] == 1

    @pytest.mark.parametrize("domain", [
        "seekingalpha.com", "fool.com", "investopedia.com",
        "marketwatch.com", "thestreet.com", "techcrunch.com",
    ])
    def test_tier2_sources(self, domain):
        assert SOURCE_TIERS[domain] == 2
