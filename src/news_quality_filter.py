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
