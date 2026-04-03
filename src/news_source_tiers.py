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
