"""Tests for news quality filter — heuristics, dedup, and full pipeline."""

import pytest
from src.news_quality_filter import (
    detect_listicle,
    detect_affiliate,
    detect_press_release,
    FilterDiagnostics,
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
