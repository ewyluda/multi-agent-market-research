# News Agent: RSS Feeds + Quality Filter — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add curated RSS feed support and a deterministic quality filter to the news agent, eliminating SEO-bait, affiliate spam, and press release regurgitation while adding high-quality financial sources.

**Architecture:** RSS feeds run concurrently with Tavily in `fetch_data()`. All articles from all sources pass through a three-stage quality filter (source tier gate → content heuristics → deduplication) in `analyze()` before categorization. A shared source-tier registry maps domains to quality tiers across all data sources.

**Tech Stack:** Python 3, asyncio, feedparser, PyYAML (already available), difflib.SequenceMatcher (stdlib), aiohttp (already used)

---

## File Structure

| File | Responsibility |
|------|---------------|
| `src/news_source_tiers.py` (new) | Domain-to-tier mapping + `get_source_tier()` lookup function |
| `src/news_quality_filter.py` (new) | Three-stage quality filter: tier gate, content heuristics, deduplication |
| `src/rss_feeds.yaml` (new) | Curated feed registry (~20 feeds with tier + sector tags) |
| `src/rss_client.py` (new) | Async RSS fetcher with TTL caching and sector-based feed selection |
| `src/agents/news_agent.py` (modify) | Wire RSS into `fetch_data()`, quality filter into `analyze()` |
| `src/config.py` (modify) | Add `RSS_ENABLED`, `RSS_CACHE_TTL`, `NEWS_QUALITY_FILTER_ENABLED` |
| `tests/test_news_source_tiers.py` (new) | Tests for tier lookup |
| `tests/test_news_quality_filter.py` (new) | Tests for all three filter stages |
| `tests/test_rss_client.py` (new) | Tests for RSS client with mock feeds |
| `tests/test_agents/test_news_agent.py` (new) | Tests for news agent integration with RSS + quality filter |

Dependencies build bottom-up: source tiers → quality filter → RSS client → news agent integration.

---

### Task 1: Source Tier Registry

**Files:**
- Create: `src/news_source_tiers.py`
- Create: `tests/test_news_source_tiers.py`

- [ ] **Step 1: Write failing tests for source tier lookup**

Create `tests/test_news_source_tiers.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_news_source_tiers.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'src.news_source_tiers'`

- [ ] **Step 3: Implement source tier registry**

Create `src/news_source_tiers.py`:

```python
"""Source tier registry for news quality classification.

Maps news source domains to quality tiers:
  - Tier 1: Major financial press (Reuters, Bloomberg, WSJ, etc.)
  - Tier 2: Analyst/editorial sources (Seeking Alpha, Motley Fool, etc.)
  - Tier 3: Everything else (default)

Used by both the quality filter and RSS client to classify articles
from any data source (Tavily, OpenBB, RSS) by their origin domain.
"""

from urllib.parse import urlparse
from typing import Optional

SOURCE_TIERS = {
    # Tier 1 — Major financial press & wire services
    "reuters.com": 1,
    "bloomberg.com": 1,
    "wsj.com": 1,
    "ft.com": 1,
    "cnbc.com": 1,
    "barrons.com": 1,
    "nytimes.com": 1,
    "apnews.com": 1,
    "washingtonpost.com": 1,
    "bbc.com": 1,

    # Tier 2 — Analyst/editorial & sector-specific
    "seekingalpha.com": 2,
    "fool.com": 2,
    "investopedia.com": 2,
    "marketwatch.com": 2,
    "thestreet.com": 2,
    "techcrunch.com": 2,
    "fiercepharma.com": 2,
    "zdnet.com": 2,
    "arstechnica.com": 2,
    "theverge.com": 2,
    "investors.com": 2,
    "finance.yahoo.com": 2,
    "benzinga.com": 2,

    # Tier 3 — Everything else (implicit default)
}


def get_source_tier(url_or_domain: Optional[str]) -> int:
    """Extract domain from a URL or bare domain string, return its tier.

    Args:
        url_or_domain: A full URL (https://www.reuters.com/article/...)
                       or bare domain (reuters.com). None and empty strings
                       return the default tier 3.

    Returns:
        Integer tier: 1 (premium), 2 (editorial), or 3 (unknown/default).
    """
    if not url_or_domain:
        return 3

    text = url_or_domain.strip()

    # If it looks like a URL, parse it; otherwise treat as bare domain
    if "://" in text:
        try:
            hostname = urlparse(text).hostname or ""
        except Exception:
            return 3
    else:
        hostname = text.split("/")[0]

    hostname = hostname.lower()

    # Strip www. prefix
    if hostname.startswith("www."):
        hostname = hostname[4:]

    # Direct lookup first
    if hostname in SOURCE_TIERS:
        return SOURCE_TIERS[hostname]

    # Try parent domain (e.g., "markets.ft.com" → "ft.com")
    parts = hostname.split(".")
    if len(parts) > 2:
        parent = ".".join(parts[-2:])
        if parent in SOURCE_TIERS:
            return SOURCE_TIERS[parent]

    return 3
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_news_source_tiers.py -v`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/news_source_tiers.py tests/test_news_source_tiers.py
git commit -m "feat: add news source tier registry for quality classification"
```

---

### Task 2: Quality Filter — Content Heuristics

**Files:**
- Create: `src/news_quality_filter.py`
- Create: `tests/test_news_quality_filter.py`

- [ ] **Step 1: Write failing tests for content heuristic detectors**

Create `tests/test_news_quality_filter.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_news_quality_filter.py::TestListicleDetection -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'src.news_quality_filter'`

- [ ] **Step 3: Implement content heuristic detectors**

Create `src/news_quality_filter.py`:

```python
"""Deterministic quality filter for news articles.

Three-stage pipeline:
  Stage 1 — Source tier gate (Tier 1 skips content checks)
  Stage 2 — Content heuristics (listicle, affiliate, press release)
  Stage 3 — Deduplication (fuzzy title matching)

All articles from any source (Tavily, OpenBB, RSS) pass through this filter
in the news agent's analyze() method.
"""

import re
import logging
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from typing import Dict, Any, List, Optional

from .news_source_tiers import get_source_tier

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────
# Stage 2 — Content Heuristic Detectors
# ──────────────────────────────────────────────

_LISTICLE_PATTERNS = [
    re.compile(r"^(top|best|worst)\s+\d+", re.IGNORECASE),
    re.compile(r"\d+\s+(stocks?|picks?|plays?)\s+to\s+(buy|sell|watch)", re.IGNORECASE),
]

_AFFILIATE_PHRASES = [
    "premium pick",
    "free report",
    "limited time",
    "exclusive offer",
    "sign up now",
    "our #1 pick",
    "our number one pick",
    "act now",
    "subscribe today",
    "join now",
    "unlock access",
]

_PRESS_RELEASE_PHRASES = [
    "business wire",
    "pr newswire",
    "globe newswire",
    "forward-looking statements",
    "safe harbor",
    "accesswire",
    "cision",
]


def detect_listicle(title: str, body: str) -> Optional[str]:
    """Detect SEO-bait listicle patterns in article title.

    Args:
        title: Article title/headline.
        body: Article body/description (unused currently, reserved for future).

    Returns:
        "listicle" if detected, None otherwise.
    """
    for pattern in _LISTICLE_PATTERNS:
        if pattern.search(title):
            return "listicle"
    return None


def detect_affiliate(title: str, body: str) -> Optional[str]:
    """Detect affiliate/promotional content by keyword matching.

    Args:
        title: Article title/headline.
        body: Article body/description/content.

    Returns:
        "affiliate" if detected, None otherwise.
    """
    combined = f"{title} {body}".lower()
    for phrase in _AFFILIATE_PHRASES:
        if phrase in combined:
            return "affiliate"
    return None


def detect_press_release(title: str, body: str) -> Optional[str]:
    """Detect raw press release wire content.

    Args:
        title: Article title/headline.
        body: Article body/description/content.

    Returns:
        "press_release" if detected, None otherwise.
    """
    combined = f"{title} {body}".lower()
    for phrase in _PRESS_RELEASE_PHRASES:
        if phrase in combined:
            return "press_release"
    return None


# ──────────────────────────────────────────────
# Stage 3 — Deduplication
# ──────────────────────────────────────────────

def deduplicate_articles(
    articles: List[Dict[str, Any]],
    threshold: float = 0.75,
) -> tuple[List[Dict[str, Any]], int]:
    """Remove duplicate articles by fuzzy title similarity.

    When duplicates are found:
      - Keep the article from the highest-tier source (lowest tier number).
      - If same tier, keep the one with the longest content.

    Args:
        articles: List of article dicts. Each must have "title" and "url" keys.
                  Articles should already have a "source_tier" key (int).
        threshold: SequenceMatcher ratio above which titles are considered duplicates.

    Returns:
        Tuple of (deduplicated articles, number of duplicates removed).
    """
    if len(articles) <= 1:
        return articles, 0

    kept: List[Dict[str, Any]] = []
    removed = 0

    for article in articles:
        title = (article.get("title") or "").strip().lower()
        if not title:
            kept.append(article)
            continue

        is_duplicate = False
        for i, existing in enumerate(kept):
            existing_title = (existing.get("title") or "").strip().lower()
            ratio = SequenceMatcher(None, title, existing_title).ratio()
            if ratio >= threshold:
                # Duplicate found — keep the better one
                article_tier = article.get("source_tier", 3)
                existing_tier = existing.get("source_tier", 3)
                article_content_len = len(article.get("content") or article.get("description") or "")
                existing_content_len = len(existing.get("content") or existing.get("description") or "")

                if article_tier < existing_tier or (
                    article_tier == existing_tier and article_content_len > existing_content_len
                ):
                    # New article is better — replace existing
                    kept[i] = article
                # Either way, the incoming article is handled
                is_duplicate = True
                removed += 1
                break

        if not is_duplicate:
            kept.append(article)

    return kept, removed


# ──────────────────────────────────────────────
# Full Pipeline
# ──────────────────────────────────────────────

@dataclass
class FilterDiagnostics:
    """Statistics from the quality filter run."""
    total_input: int = 0
    total_passed: int = 0
    removed_listicle: int = 0
    removed_affiliate: int = 0
    removed_press_release: int = 0
    removed_duplicate: int = 0


@dataclass
class FilterResult:
    """Output of the quality filter pipeline."""
    passed: List[Dict[str, Any]] = field(default_factory=list)
    diagnostics: FilterDiagnostics = field(default_factory=FilterDiagnostics)


_HEURISTIC_DETECTORS = [
    detect_listicle,
    detect_affiliate,
    detect_press_release,
]


def run_quality_filter(articles: List[Dict[str, Any]]) -> FilterResult:
    """Run the full three-stage quality filter pipeline.

    Stage 1: Source tier gate — Tier 1 articles skip content heuristics.
    Stage 2: Content heuristics — detect listicle, affiliate, press release.
    Stage 3: Deduplication — fuzzy title matching, keep best source.

    Each article should have a "url" key for tier lookup. If a "source_tier"
    key is already present (e.g., from RSS), it is used directly.

    Args:
        articles: List of article dicts from any source.

    Returns:
        FilterResult with passed articles and diagnostics.
    """
    diagnostics = FilterDiagnostics(total_input=len(articles))

    if not articles:
        return FilterResult(passed=[], diagnostics=diagnostics)

    # Assign tiers to articles that don't have one
    for article in articles:
        if "source_tier" not in article:
            article["source_tier"] = get_source_tier(article.get("url", ""))

    # Stage 1 + 2: Tier gate + content heuristics
    after_heuristics = []
    for article in articles:
        tier = article.get("source_tier", 3)

        # Tier 1 sources skip content heuristics
        if tier == 1:
            after_heuristics.append(article)
            continue

        # Run content heuristic detectors
        title = article.get("title") or ""
        body = article.get("content") or article.get("description") or ""

        flagged = False
        for detector in _HEURISTIC_DETECTORS:
            label = detector(title, body)
            if label:
                if label == "listicle":
                    diagnostics.removed_listicle += 1
                elif label == "affiliate":
                    diagnostics.removed_affiliate += 1
                elif label == "press_release":
                    diagnostics.removed_press_release += 1
                flagged = True
                break

        if not flagged:
            after_heuristics.append(article)

    # Stage 3: Deduplication
    deduplicated, dup_count = deduplicate_articles(after_heuristics)
    diagnostics.removed_duplicate = dup_count

    diagnostics.total_passed = len(deduplicated)
    logger.info(
        "Quality filter: %d → %d articles (listicle=%d, affiliate=%d, "
        "press_release=%d, duplicate=%d)",
        diagnostics.total_input,
        diagnostics.total_passed,
        diagnostics.removed_listicle,
        diagnostics.removed_affiliate,
        diagnostics.removed_press_release,
        diagnostics.removed_duplicate,
    )

    return FilterResult(passed=deduplicated, diagnostics=diagnostics)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_news_quality_filter.py -v`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/news_quality_filter.py tests/test_news_quality_filter.py
git commit -m "feat: add news quality filter with heuristic detectors"
```

---

### Task 3: Quality Filter — Deduplication & Full Pipeline Tests

**Files:**
- Modify: `tests/test_news_quality_filter.py`

- [ ] **Step 1: Add deduplication and full pipeline tests**

Append to `tests/test_news_quality_filter.py`:

```python
from src.news_quality_filter import deduplicate_articles, run_quality_filter, FilterResult


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
```

- [ ] **Step 2: Run all quality filter tests**

Run: `python -m pytest tests/test_news_quality_filter.py -v`
Expected: All tests PASS

- [ ] **Step 3: Commit**

```bash
git add tests/test_news_quality_filter.py
git commit -m "test: add deduplication and full pipeline tests for quality filter"
```

---

### Task 4: RSS Feed Registry

**Files:**
- Create: `src/rss_feeds.yaml`

- [ ] **Step 1: Create the curated feed registry**

Create `src/rss_feeds.yaml`:

```yaml
# Curated RSS feed registry for financial news.
#
# Each feed has:
#   - name: Human-readable source name
#   - url: RSS/Atom feed URL
#   - tier: Quality tier (1=premium press, 2=editorial/analyst)
#   - sectors: List of sectors this feed covers, or [all] for general
#
# Sectors match yfinance sector names (lowercase):
#   technology, healthcare, financial-services, consumer-cyclical,
#   industrials, energy, consumer-defensive, real-estate,
#   communication-services, utilities, basic-materials

feeds:
  # ── Tier 1 — Major wire services & premium financial press ──
  - name: Reuters Business
    url: https://www.reutersagency.com/feed/?best-topics=business-finance
    tier: 1
    sectors: [all]

  - name: CNBC Finance
    url: https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=10000664
    tier: 1
    sectors: [all]

  - name: CNBC Earnings
    url: https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=15839135
    tier: 1
    sectors: [all]

  - name: WSJ Markets
    url: https://feeds.content.dowjones.io/public/rss/RSSMarketsMain
    tier: 1
    sectors: [all]

  - name: NYT Business
    url: https://rss.nytimes.com/services/xml/rss/nyt/Business.xml
    tier: 1
    sectors: [all]

  - name: AP Business
    url: https://rsshub.app/apnews/topics/business
    tier: 1
    sectors: [all]

  - name: FT Markets
    url: https://www.ft.com/rss/markets
    tier: 1
    sectors: [all]

  - name: Barrons
    url: https://www.barrons.com/feed
    tier: 1
    sectors: [all]

  # ── Tier 2 — Analyst/editorial sources ──
  - name: Seeking Alpha Market News
    url: https://seekingalpha.com/market_currents.xml
    tier: 2
    sectors: [all]

  - name: MarketWatch Top Stories
    url: https://feeds.marketwatch.com/marketwatch/topstories/
    tier: 2
    sectors: [all]

  - name: Investopedia News
    url: https://www.investopedia.com/feedbuilder/feed/getfeed?feedName=rss_headline
    tier: 2
    sectors: [all]

  - name: Benzinga News
    url: https://www.benzinga.com/feed
    tier: 2
    sectors: [all]

  # ── Sector-specific ──
  - name: TechCrunch
    url: https://techcrunch.com/feed/
    tier: 2
    sectors: [technology]

  - name: The Verge
    url: https://www.theverge.com/rss/index.xml
    tier: 2
    sectors: [technology]

  - name: Ars Technica
    url: https://feeds.arstechnica.com/arstechnica/index
    tier: 2
    sectors: [technology]

  - name: Fierce Pharma
    url: https://www.fiercepharma.com/rss/xml
    tier: 2
    sectors: [healthcare]

  - name: Fierce Biotech
    url: https://www.fiercebiotech.com/rss/xml
    tier: 2
    sectors: [healthcare]

  - name: E&E News Energy
    url: https://www.eenews.net/feed/
    tier: 2
    sectors: [energy]

  - name: American Banker
    url: https://www.americanbanker.com/feed
    tier: 2
    sectors: [financial-services]
```

- [ ] **Step 2: Commit**

```bash
git add src/rss_feeds.yaml
git commit -m "feat: add curated RSS feed registry with 19 financial sources"
```

---

### Task 5: RSS Client

**Files:**
- Create: `src/rss_client.py`
- Create: `tests/test_rss_client.py`

- [ ] **Step 1: Write failing tests for RSS client**

Create `tests/test_rss_client.py`:

```python
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
        # tech-only feeds should not have "all" in sectors
        for f in tech_feeds:
            if "all" not in f["sectors"]:
                assert "technology" in f["sectors"]


class TestNormalizeEntry:
    """Tests for feedparser entry → article dict normalization."""

    def test_basic_entry(self):
        entry = MagicMock()
        entry.get = lambda k, d="": {
            "title": "Test Article",
            "link": "https://example.com/article",
            "summary": "Test summary",
            "published": "Thu, 03 Apr 2026 12:00:00 GMT",
        }.get(k, d)
        entry.title = "Test Article"
        entry.link = "https://example.com/article"
        entry.get.return_value = ""

        # Use a simpler approach
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
        # Should return all feeds with "all" in sectors
        assert all("all" in f["sectors"] for f in feeds)

    def test_select_feeds_technology(self):
        client = RSSClient()
        feeds = client._select_feeds(sector="technology")
        # Should include "all" feeds AND technology-specific feeds
        assert len(feeds) > 0
        sector_specific = [f for f in feeds if "all" not in f["sectors"]]
        assert all("technology" in f["sectors"] for f in sector_specific)

    @pytest.mark.asyncio
    async def test_fetch_feeds_returns_list(self):
        """Integration-style test with mocked HTTP."""
        client = RSSClient()
        # Mock _fetch_single_feed to return a canned article
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
            # _fetch_single_feed should only be called once per feed (cached on second call)
            first_call_count = mock_fetch.call_count
            await client.fetch_feeds(ticker="AAPL", sector=None)
            assert mock_fetch.call_count == first_call_count
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_rss_client.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'src.rss_client'`

- [ ] **Step 3: Install feedparser dependency**

```bash
pip install feedparser
```

Add `feedparser` to `requirements.txt` (find the data/network section and add it there).

- [ ] **Step 4: Implement RSS client**

Create `src/rss_client.py`:

```python
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
        # Cache: feed_url → (timestamp, list of raw entries)
        self._cache: Dict[str, tuple[float, List[Dict[str, Any]]]] = {}

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

        logger.info("RSS total: %d articles from %d feeds for %s", len(all_articles), len(feeds), ticker)
        return all_articles
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m pytest tests/test_rss_client.py -v`
Expected: All tests PASS

- [ ] **Step 6: Commit**

```bash
git add src/rss_client.py tests/test_rss_client.py requirements.txt
git commit -m "feat: add async RSS client with caching and sector-based feed selection"
```

---

### Task 6: Config Updates

**Files:**
- Modify: `src/config.py`

- [ ] **Step 1: Add RSS and quality filter config keys**

Add the following three lines after the Tavily configuration block (after line 81 in `src/config.py`, after `TAVILY_SEARCH_DEPTH`):

```python
    # RSS Feed Configuration
    RSS_ENABLED = os.getenv("RSS_ENABLED", "true").lower() == "true"
    RSS_CACHE_TTL = int(os.getenv("RSS_CACHE_TTL", "900"))

    # News Quality Filter
    NEWS_QUALITY_FILTER_ENABLED = os.getenv("NEWS_QUALITY_FILTER_ENABLED", "true").lower() == "true"
```

- [ ] **Step 2: Verify config loads without errors**

Run: `python -c "from src.config import Config; print('RSS_ENABLED:', Config.RSS_ENABLED); print('RSS_CACHE_TTL:', Config.RSS_CACHE_TTL); print('NEWS_QUALITY_FILTER_ENABLED:', Config.NEWS_QUALITY_FILTER_ENABLED)"`
Expected: Prints `RSS_ENABLED: True`, `RSS_CACHE_TTL: 900`, `NEWS_QUALITY_FILTER_ENABLED: True`

- [ ] **Step 3: Commit**

```bash
git add src/config.py
git commit -m "feat: add RSS and quality filter config keys"
```

---

### Task 7: News Agent Integration

**Files:**
- Modify: `src/agents/news_agent.py`
- Create: `tests/test_agents/test_news_agent.py`

This is the integration task — wiring RSS into `fetch_data()` and the quality filter into `analyze()`.

- [ ] **Step 1: Write failing integration tests**

Create `tests/test_agents/test_news_agent.py`:

```python
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
        # The spam article should be filtered out
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
        # Spam should NOT be filtered when quality filter is disabled
        assert result["total_count"] == 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_agents/test_news_agent.py -v`
Expected: FAIL — `ImportError` for `RSSClient` (not yet imported in news_agent.py)

- [ ] **Step 3: Modify news agent — add RSS to fetch_data()**

In `src/agents/news_agent.py`, add the import at the top (after the existing imports around line 9):

```python
from ..rss_client import RSSClient
from ..news_quality_filter import run_quality_filter
```

Replace the `fetch_data()` method (lines 581-674) with this updated version that adds RSS as a concurrent source:

```python
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
```

- [ ] **Step 4: Modify news agent — add quality filter to analyze()**

In the `analyze()` method (starts around line 676), insert the quality filter after relevance scoring and before categorization. Replace the `analyze()` method with:

```python
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
```

- [ ] **Step 5: Run integration tests**

Run: `python -m pytest tests/test_agents/test_news_agent.py -v`
Expected: All tests PASS

- [ ] **Step 6: Run all existing tests to check for regressions**

Run: `python -m pytest tests/ -v --timeout=60 -x -m "not slow"`
Expected: No new failures

- [ ] **Step 7: Commit**

```bash
git add src/agents/news_agent.py tests/test_agents/test_news_agent.py
git commit -m "feat: integrate RSS feeds and quality filter into news agent"
```

---

### Task 8: Verify Full Pipeline End-to-End

**Files:**
- No new files — verification only

- [ ] **Step 1: Run the full test suite**

```bash
python -m pytest tests/ -v --timeout=60 -m "not slow"
```

Expected: All tests pass, no regressions.

- [ ] **Step 2: Verify imports and module loading**

```bash
python -c "
from src.news_source_tiers import get_source_tier, SOURCE_TIERS
from src.news_quality_filter import run_quality_filter, FilterResult
from src.rss_client import RSSClient, _load_feeds
from src.agents.news_agent import NewsAgent
from src.config import Config
print('All imports successful')
print(f'Source tiers: {len(SOURCE_TIERS)} domains')
print(f'RSS feeds: {len(_load_feeds())} feeds')
print(f'RSS_ENABLED: {Config.RSS_ENABLED}')
print(f'NEWS_QUALITY_FILTER_ENABLED: {Config.NEWS_QUALITY_FILTER_ENABLED}')
"
```

Expected: All imports succeed, correct counts printed.

- [ ] **Step 3: Final commit (if any fixes were needed)**

Only commit if Step 1 or 2 required fixes. Otherwise skip.

---

Plan complete and saved to `docs/superpowers/plans/2026-04-03-news-agent-rss-quality-filter.md`. Two execution options:

**1. Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** — Execute tasks in this session using executing-plans, batch execution with checkpoints

Which approach?