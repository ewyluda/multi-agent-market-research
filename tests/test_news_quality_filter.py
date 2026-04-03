"""Tests for news quality filter — heuristics, dedup, and full pipeline."""

import pytest
from src.news_quality_filter import (
    detect_listicle,
    detect_affiliate,
    detect_press_release,
    FilterDiagnostics,
    deduplicate_articles,
    run_quality_filter,
    FilterResult,
)


class TestListicleDetection:
    """Tests for SEO-bait / listicle pattern detection."""

    def test_top_n_stocks(self):
        assert detect_listicle("Top 5 Stocks to Buy Now", "") == "listicle"

    def test_best_n_picks(self):
        assert detect_listicle("Best 10 Picks for 2026", "") == "listicle"

    def test_worst_n_stocks(self):
        assert detect_listicle("Worst 3 Stocks to Sell Immediately", "") == "listicle"

    def test_n_stocks_to_buy(self):
        assert detect_listicle("7 Stocks to Buy Before Earnings Season", "") == "listicle"

    def test_n_plays_to_watch(self):
        assert detect_listicle("5 Plays to Watch This Week", "") == "listicle"

    def test_legitimate_headline(self):
        assert detect_listicle("Apple Reports Record Q4 Revenue", "") is None

    def test_number_in_non_listicle_context(self):
        assert detect_listicle("NVIDIA Up 5% After Earnings Beat", "") is None

    def test_case_insensitive(self):
        assert detect_listicle("TOP 3 STOCKS TO BUY", "") == "listicle"


class TestAffiliateDetection:
    """Tests for affiliate/promotional content detection."""

    def test_premium_pick_in_title(self):
        assert detect_affiliate("Is AAPL Our #1 Premium Pick?", "") == "affiliate"

    def test_free_report_in_body(self):
        assert detect_affiliate("AAPL Analysis", "Get the free report today") == "affiliate"

    def test_exclusive_offer(self):
        assert detect_affiliate("Exclusive Offer: Stock Picks", "") == "affiliate"

    def test_sign_up_now(self):
        assert detect_affiliate("Market Update", "Sign up now for alerts") == "affiliate"

    def test_our_number_one_pick(self):
        assert detect_affiliate("Our #1 Pick for 2026", "") == "affiliate"

    def test_legitimate_headline(self):
        assert detect_affiliate("Apple Reports Record Q4 Revenue", "Strong earnings beat") is None

    def test_limited_time(self):
        assert detect_affiliate("Limited Time: Premium Stock Picks", "") == "affiliate"


class TestPressReleaseDetection:
    """Tests for press release wire content detection."""

    def test_business_wire_in_body(self):
        assert detect_press_release("Company Announces Results", "BUSINESS WIRE -- Company today announced") == "press_release"

    def test_pr_newswire(self):
        assert detect_press_release("New Product Launch", "PR Newswire -- Company launches") == "press_release"

    def test_globe_newswire(self):
        assert detect_press_release("Q4 Results", "GLOBE NEWSWIRE -- Company reports") == "press_release"

    def test_forward_looking_statements(self):
        assert detect_press_release("Company Update", "This press release contains forward-looking statements") == "press_release"

    def test_safe_harbor(self):
        assert detect_press_release("Quarterly Results", "safe harbor provisions of the Private Securities") == "press_release"

    def test_legitimate_article(self):
        assert detect_press_release(
            "Apple Beats Estimates on Strong iPhone Sales",
            "Apple reported quarterly revenue that exceeded analyst expectations"
        ) is None

    def test_case_insensitive(self):
        assert detect_press_release("Results", "business wire -- Company") == "press_release"


class TestDeduplication:
    """Tests for fuzzy title deduplication."""

    def test_exact_duplicate_keeps_higher_tier(self):
        articles = [
            {"title": "Apple Reports Record Revenue", "url": "https://random-blog.com/a", "source_tier": 3, "content": "short"},
            {"title": "Apple Reports Record Revenue", "url": "https://reuters.com/a", "source_tier": 1, "content": "short"},
        ]
        result, removed = deduplicate_articles(articles)
        assert len(result) == 1
        assert removed == 1
        assert result[0]["source_tier"] == 1

    def test_fuzzy_duplicate_detected(self):
        articles = [
            {"title": "Apple Reports Record Q4 Revenue of $124B", "url": "https://a.com", "source_tier": 2},
            {"title": "Apple Reports Record Q4 Revenue of $124 Billion", "url": "https://b.com", "source_tier": 2},
        ]
        result, removed = deduplicate_articles(articles)
        assert len(result) == 1
        assert removed == 1

    def test_different_articles_kept(self):
        articles = [
            {"title": "Apple Reports Record Revenue", "url": "https://a.com", "source_tier": 2},
            {"title": "NVIDIA Launches New GPU Architecture", "url": "https://b.com", "source_tier": 2},
        ]
        result, removed = deduplicate_articles(articles)
        assert len(result) == 2
        assert removed == 0

    def test_same_tier_keeps_longer_content(self):
        articles = [
            {"title": "Tesla Q4 Results", "url": "https://a.com", "source_tier": 2, "content": "Short blurb."},
            {"title": "Tesla Q4 Results", "url": "https://b.com", "source_tier": 2, "content": "Detailed analysis of Tesla's quarterly performance with breakdowns."},
        ]
        result, removed = deduplicate_articles(articles)
        assert len(result) == 1
        assert "Detailed" in result[0]["content"]

    def test_empty_list(self):
        result, removed = deduplicate_articles([])
        assert result == []
        assert removed == 0

    def test_single_article(self):
        articles = [{"title": "Test", "url": "https://a.com"}]
        result, removed = deduplicate_articles(articles)
        assert len(result) == 1
        assert removed == 0


class TestRunQualityFilter:
    """Tests for the full filter pipeline."""

    def test_tier1_skips_heuristics(self):
        """A listicle title from Reuters should pass because it's Tier 1."""
        articles = [
            {"title": "Top 5 Stocks to Watch", "url": "https://reuters.com/article/123", "content": ""},
        ]
        result = run_quality_filter(articles)
        assert len(result.passed) == 1
        assert result.diagnostics.removed_listicle == 0

    def test_tier3_listicle_removed(self):
        articles = [
            {"title": "Top 5 Stocks to Buy Now", "url": "https://random-seo-site.com/stocks", "content": ""},
        ]
        result = run_quality_filter(articles)
        assert len(result.passed) == 0
        assert result.diagnostics.removed_listicle == 1

    def test_mixed_quality_articles(self):
        articles = [
            {"title": "Apple Reports Record Revenue", "url": "https://reuters.com/a", "content": "Detailed analysis..."},
            {"title": "Top 10 Stocks to Buy", "url": "https://seo-spam.com/a", "content": ""},
            {"title": "AAPL Analysis", "url": "https://random.com/a", "content": "Get the free report today"},
            {"title": "Company Announces Results", "url": "https://unknown.com/a", "content": "BUSINESS WIRE -- Company today announced"},
            {"title": "NVIDIA Earnings Beat Estimates", "url": "https://cnbc.com/a", "content": "Strong quarter..."},
        ]
        result = run_quality_filter(articles)
        assert len(result.passed) == 2
        assert result.diagnostics.removed_listicle == 1
        assert result.diagnostics.removed_affiliate == 1
        assert result.diagnostics.removed_press_release == 1

    def test_dedup_runs_after_heuristics(self):
        articles = [
            {"title": "Apple Record Revenue Q4", "url": "https://reuters.com/a", "content": "From Reuters..."},
            {"title": "Apple Record Revenue Q4", "url": "https://cnbc.com/a", "content": "From CNBC..."},
        ]
        result = run_quality_filter(articles)
        assert len(result.passed) == 1
        assert result.diagnostics.removed_duplicate == 1

    def test_empty_input(self):
        result = run_quality_filter([])
        assert len(result.passed) == 0
        assert result.diagnostics.total_input == 0

    def test_diagnostics_totals(self):
        articles = [
            {"title": "Good Article", "url": "https://wsj.com/a", "content": "Real analysis"},
            {"title": "Top 3 Stocks to Buy", "url": "https://spam.com/a", "content": ""},
        ]
        result = run_quality_filter(articles)
        assert result.diagnostics.total_input == 2
        assert result.diagnostics.total_passed == 1
