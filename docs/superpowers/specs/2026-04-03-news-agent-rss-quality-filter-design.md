# News Agent: RSS Feeds + Quality Filter

**Date:** 2026-04-03
**Status:** Approved
**Scope:** Add curated RSS feed support and deterministic quality filtering to the news agent

---

## Problem

The news agent returns low-quality articles that provide no analytical value: SEO-bait listicles ("Top 5 Stocks to Buy"), press release regurgitation with no editorial content, and affiliate/promotional articles. The current relevance filter only checks whether an article is about the right company, not whether it contains useful insight.

## Solution

Two additions to the news pipeline:

1. **RSS feed system** — curated list of ~20 high-quality financial sources fetched concurrently alongside Tavily
2. **Quality filter** — three-stage deterministic pipeline that drops spam articles from all sources

## Architecture

```
fetch_data():
  ┌─ asyncio.gather ─────────────────────┐
  │  1. Tavily search (existing)          │
  │  2. RSS feeds (new)                   │
  │  3. Twitter posts (existing)          │
  └───────────────────────────────────────┘
  │
  ├─ Tavily succeeds: Tavily + RSS articles merged
  ├─ Tavily fails: RSS + OpenBB fallback
  ├─ Both fail: OpenBB only (existing)
  │
  └─ Return combined raw articles + twitter_posts

analyze():
  raw articles
  │
  ├─ Relevance scoring (existing, unchanged)
  ├─ Quality filter (new — Stage 1→2→3)
  ├─ Categorization (existing, unchanged)
  ├─ Key headlines (existing, unchanged)
  │
  └─ Return filtered articles + diagnostics
```

RSS runs concurrently with Tavily — both contribute articles. RSS is supplementary now but architectured to become primary if Tavily proves redundant after side-by-side comparison.

---

## Component 1: RSS Feed System

### New file: `src/rss_client.py`

Async RSS fetcher with caching and sector-based feed selection.

**Behavior:**
- `RSSClient.fetch_feeds(ticker, sector)` fetches all `[all]` feeds + sector-matched feeds concurrently
- Entries parsed with `feedparser`, filtered by recency (default 7 days)
- Articles matched to ticker using existing `_score_article_relevance()` logic
- Each article carries its source tier from the feed config
- TTL cache on feed fetches (15 min default) to avoid hammering sources

### New file: `src/rss_feeds.yaml`

Curated feed registry with ~20 feeds. Each feed has: name, URL, tier (1-3), and sectors list.

```yaml
feeds:
  # Tier 1 — Major wire services & premium financial press
  - name: Reuters Business
    url: https://www.reutersagency.com/feed/?best-topics=business-finance
    tier: 1
    sectors: [all]
  - name: Bloomberg Markets
    url: https://feeds.bloomberg.com/markets/news.rss
    tier: 1
    sectors: [all]
  - name: WSJ Markets
    url: https://feeds.a]wsj.com/rss/RSSMarketsMain.xml
    tier: 1
    sectors: [all]
  - name: CNBC Finance
    url: https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=10000664
    tier: 1
    sectors: [all]

  # Tier 2 — Analyst/editorial sources
  - name: Seeking Alpha
    url: https://seekingalpha.com/market_currents.xml
    tier: 2
    sectors: [all]
  - name: Motley Fool
    url: https://www.fool.com/feeds/index.aspx
    tier: 2
    sectors: [all]
  - name: Barrons
    url: https://www.barrons.com/feed
    tier: 2
    sectors: [all]

  # Sector-specific
  - name: TechCrunch
    url: https://techcrunch.com/feed/
    tier: 2
    sectors: [technology]
  - name: Fierce Pharma
    url: https://www.fiercepharma.com/rss/xml
    tier: 2
    sectors: [healthcare]
  # ... ~15-20 total feeds
```

**Config:**
- `RSS_ENABLED` (default `true`)
- `RSS_CACHE_TTL` (default `900` seconds / 15 min)

---

## Component 2: Quality Filter

### New file: `src/news_quality_filter.py`

Three-stage deterministic filter pipeline. All articles pass through regardless of source.

### Stage 1 — Source Tier Gate

- **Tier 1** (Reuters, Bloomberg, WSJ): pass through, skip content heuristics
- **Tier 2** (Seeking Alpha, Motley Fool, TechCrunch): pass through, eligible for content filtering
- **Tier 3 / unknown**: must pass all content filters to survive
- Tavily articles with no recognized source domain: treated as Tier 3

### Stage 2 — Content Heuristics

Pattern-based detection for three spam categories:

| Pattern | Detection Method | Examples |
|---------|-----------------|----------|
| Listicle/SEO | Regex on title: `r"^(top\|best\|worst)\s+\d+"`, `r"\d+\s+(stocks?\|picks?\|plays?)\s+to\s+(buy\|sell\|watch)"` | "Top 5 Stocks to Buy Now" |
| Affiliate/promo | Keyword set in title+body: "premium pick", "free report", "limited time", "exclusive offer", "sign up now", "our #1 pick" | "Is AAPL Our #1 Pick? Get the Free Report" |
| Press release wire | Source detection + boilerplate phrases: "BUSINESS WIRE", "PR Newswire", "GLOBE NEWSWIRE", "forward-looking statements", "safe harbor" | Raw PR with no editorial content |

Each heuristic returns a label (e.g., `"listicle"`, `"affiliate"`, `"press_release"`) or `None`. An article flagged by any heuristic is dropped.

### Stage 3 — Deduplication

- Fuzzy title similarity using `difflib.SequenceMatcher` (stdlib, no new dependency)
- Threshold: 0.75 similarity ratio = duplicate
- When duplicates found: keep article from highest-tier source
- Same tier: keep the one with longest content (more likely to have analysis)

### Filter Output

```python
@dataclass
class FilterResult:
    passed: List[Dict[str, Any]]    # Articles that survived
    diagnostics: FilterDiagnostics  # Stats for transparency

@dataclass
class FilterDiagnostics:
    total_input: int
    total_passed: int
    removed_listicle: int
    removed_affiliate: int
    removed_press_release: int
    removed_duplicate: int
    removed_thin_content: int
```

Diagnostics attached to news agent output. Filtered articles are silently dropped from results.

**Config:**
- `NEWS_QUALITY_FILTER_ENABLED` (default `true`)

---

## Component 3: Source Tier Registry

### New file: `src/news_source_tiers.py`

Domain-to-tier mapping shared across RSS client and quality filter. Used to classify articles from any source (RSS, Tavily, OpenBB) by their origin domain.

```python
SOURCE_TIERS = {
    # Tier 1 — Major financial press
    "reuters.com": 1,
    "bloomberg.com": 1,
    "wsj.com": 1,
    "ft.com": 1,
    "cnbc.com": 1,
    "barrons.com": 1,
    "nytimes.com": 1,
    "apnews.com": 1,

    # Tier 2 — Analyst/editorial
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

    # Tier 3 — Everything else (default)
}

def get_source_tier(url_or_domain: str) -> int:
    """Extract domain from URL, return tier (default 3)."""
```

---

## Component 4: News Agent Integration

### Modified file: `src/agents/news_agent.py`

**fetch_data() changes:**
- RSS fetch added to `asyncio.gather` alongside Tavily and Twitter
- RSS articles merged with Tavily articles when both succeed
- If Tavily fails, RSS + OpenBB fallback
- `data_source` field becomes comma-separated to reflect multiple sources (e.g., `"tavily,rss"`)

**analyze() changes:**
- Quality filter inserted after relevance scoring, before categorization
- Filter diagnostics attached to output dict
- No changes to downstream article shape — consumers unaffected

### Modified file: `src/config.py`

New config keys: `RSS_ENABLED`, `RSS_CACHE_TTL`, `NEWS_QUALITY_FILTER_ENABLED`

---

## File Summary

### New files
| File | Purpose |
|------|---------|
| `src/rss_client.py` | Async RSS fetcher with caching and sector matching |
| `src/rss_feeds.yaml` | Curated feed registry (~20 feeds with tier + sector tags) |
| `src/news_quality_filter.py` | Three-stage quality filter (tier gate, heuristics, dedup) |
| `src/news_source_tiers.py` | Domain-to-tier mapping, shared across sources |

### Modified files
| File | Change |
|------|--------|
| `src/agents/news_agent.py` | Add RSS to fetch concurrency, wire quality filter into analyze() |
| `src/config.py` | Add RSS and quality filter config keys |

### New dependency
- `feedparser` — standard RSS/Atom parser

### Not touched
- `src/tavily_client.py` — unchanged
- `src/data_provider.py` — unchanged
- `src/orchestrator.py` — unchanged (news agent interface stays the same)
- Frontend — unchanged (same article shape from `analysis.news`)

---

## Testing

- Unit tests for quality filter heuristics (listicle, affiliate, press release patterns)
- Unit tests for deduplication logic (fuzzy title matching, tier-based winner selection)
- Unit tests for source tier lookup (domain extraction, default tier)
- Integration test for RSS client with a mock feed
- Integration test for full news agent pipeline with quality filter wired in
