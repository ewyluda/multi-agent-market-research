"""News agent for gathering financial news articles with smart relevance filtering."""

import aiohttp
import asyncio
import yfinance as yf
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from .base_agent import BaseAgent


class NewsAgent(BaseAgent):
    """Agent for fetching financial news from various sources with relevance filtering.

    Data source priority:
        1. Alpha Vantage NEWS_SENTIMENT (includes built-in sentiment scores)
        2. NewsAPI (fallback)
    """

    RELEVANCE_THRESHOLD = 0.15  # Minimum score to keep an article (very permissive)

    async def _fetch_av_news(self) -> Optional[List[Dict[str, Any]]]:
        """
        Fetch news from Alpha Vantage NEWS_SENTIMENT endpoint.

        The AV NEWS_SENTIMENT endpoint provides articles with built-in
        ticker-specific relevance scores and sentiment data.

        Returns:
            List of formatted article dicts, or None on failure
        """
        lookback_days = self.config.get("NEWS_LOOKBACK_DAYS", 7)
        max_articles = self.config.get("MAX_NEWS_ARTICLES", 50)

        time_from = (datetime.now() - timedelta(days=lookback_days)).strftime("%Y%m%dT0000")

        data = await self._av_request({
            "function": "NEWS_SENTIMENT",
            "tickers": self.ticker,
            "sort": "RELEVANCE",
            "limit": str(min(max_articles, 200)),
            "time_from": time_from,
        })

        if not data or "feed" not in data:
            return None

        feed = data.get("feed", [])
        if not feed:
            return None

        articles = []
        for item in feed:
            # Extract ticker-specific sentiment from the ticker_sentiment array
            ticker_sentiment = None
            av_relevance = 0.0
            for ts in item.get("ticker_sentiment", []):
                if ts.get("ticker", "").upper() == self.ticker.upper():
                    ticker_sentiment = ts
                    try:
                        av_relevance = float(ts.get("relevance_score", 0))
                    except (ValueError, TypeError):
                        av_relevance = 0.0
                    break

            # Build article in the same format as NewsAPI articles
            articles.append({
                "title": item.get("title", ""),
                "source": item.get("source", ""),
                "author": ", ".join(item.get("authors", [])),
                "description": item.get("summary", ""),
                "url": item.get("url", ""),
                "published_at": self._parse_av_datetime(item.get("time_published", "")),
                "content": item.get("summary", ""),
                # AV-specific enrichment
                "av_overall_sentiment_score": self._safe_float(item.get("overall_sentiment_score")),
                "av_overall_sentiment_label": item.get("overall_sentiment_label", ""),
                "av_ticker_relevance": av_relevance,
                "av_ticker_sentiment_score": self._safe_float(
                    ticker_sentiment.get("ticker_sentiment_score") if ticker_sentiment else None
                ),
                "av_ticker_sentiment_label": (
                    ticker_sentiment.get("ticker_sentiment_label", "") if ticker_sentiment else ""
                ),
                # Use AV's relevance score directly as our relevance_score
                "relevance_score": round(av_relevance, 3),
            })

        self.logger.info(f"Alpha Vantage NEWS_SENTIMENT returned {len(articles)} articles for {self.ticker}")
        return articles

    @staticmethod
    def _parse_av_datetime(av_time: str) -> str:
        """
        Convert Alpha Vantage datetime format (20250207T120000) to ISO format.

        Args:
            av_time: AV datetime string like '20250207T120000'

        Returns:
            ISO format datetime string
        """
        if not av_time or len(av_time) < 15:
            return av_time
        try:
            dt = datetime.strptime(av_time[:15], "%Y%m%dT%H%M%S")
            return dt.isoformat() + "Z"
        except (ValueError, TypeError):
            return av_time

    @staticmethod
    def _safe_float(val) -> Optional[float]:
        """Safely convert a value to float."""
        if val is None or val == "None":
            return None
        try:
            return float(val)
        except (ValueError, TypeError):
            return None

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
        Fetch news articles. Tries Alpha Vantage NEWS_SENTIMENT first, falls back to NewsAPI.

        Alpha Vantage provides built-in ticker relevance and sentiment scores,
        so articles from AV are already pre-scored and don't need our relevance filter.

        Returns:
            Dictionary with news articles and company info
        """
        articles = []
        source = "unknown"

        # ── Try Alpha Vantage NEWS_SENTIMENT first ──
        av_api_key = self.config.get("ALPHA_VANTAGE_API_KEY", "")
        if av_api_key:
            self.logger.info(f"Fetching {self.ticker} news from Alpha Vantage NEWS_SENTIMENT (primary)")
            try:
                av_articles = await self._fetch_av_news()
                if av_articles and len(av_articles) > 0:
                    articles.extend(av_articles)
                    source = "alpha_vantage"
                    self.logger.info(f"Alpha Vantage returned {len(av_articles)} news articles for {self.ticker}")

                    # Still look up company info for category/relevance scoring
                    company_info = await self._get_company_info()
                    self._company_info = company_info

                    return {
                        "articles": articles,
                        "ticker": self.ticker,
                        "total_count": len(articles),
                        "company_info": company_info,
                        "source": source,
                    }
                else:
                    self.logger.info(f"Alpha Vantage returned no news for {self.ticker}, falling back to NewsAPI")
            except Exception as e:
                self.logger.warning(f"Alpha Vantage NEWS_SENTIMENT failed: {e}, falling back to NewsAPI")

        # ── Fallback to NewsAPI ──
        source = "newsapi"

        # Step 1: Look up company info for smart query construction
        company_info = await self._get_company_info()
        self._company_info = company_info  # Cache for use in analyze()

        self.logger.info(
            f"Company info for {self.ticker}: "
            f"long_name='{company_info.get('long_name')}', "
            f"short_name='{company_info.get('short_name')}'"
        )

        # Step 2: Fetch from NewsAPI with smart query
        news_api_key = self.config.get("NEWS_API_KEY")
        if news_api_key:
            try:
                news_articles = await self._fetch_from_newsapi(news_api_key, company_info)
                articles.extend(news_articles)
            except Exception as e:
                self.logger.warning(f"Failed to fetch from NewsAPI: {e}")

        return {
            "articles": articles,
            "ticker": self.ticker,
            "total_count": len(articles),
            "company_info": company_info,
            "source": source,
        }

    async def _fetch_from_newsapi(
        self,
        api_key: str,
        company_info: Dict[str, str]
    ) -> List[Dict[str, Any]]:
        """
        Fetch news from NewsAPI using a smart query built from company info.

        Args:
            api_key: NewsAPI key
            company_info: Dict with company name/sector/industry

        Returns:
            List of article dictionaries
        """
        base_url = self.config.get("NEWS_API_BASE_URL", "https://newsapi.org/v2")
        lookback_days = self.config.get("NEWS_LOOKBACK_DAYS", 7)
        max_articles = self.config.get("MAX_NEWS_ARTICLES", 20)

        # Calculate date range
        to_date = datetime.now()
        from_date = to_date - timedelta(days=lookback_days)

        # Build smart query using company name + financial identifiers
        query = self._build_news_query(company_info)

        # Construct URL
        url = f"{base_url}/everything"
        params = {
            "q": query,
            "from": from_date.strftime("%Y-%m-%d"),
            "to": to_date.strftime("%Y-%m-%d"),
            "language": "en",
            "sortBy": "publishedAt",
            "pageSize": max_articles,
            "apiKey": api_key
        }

        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    articles = data.get("articles", [])

                    # Format articles
                    formatted_articles = []
                    for article in articles:
                        formatted_articles.append({
                            "title": article.get("title"),
                            "source": article.get("source", {}).get("name"),
                            "author": article.get("author"),
                            "description": article.get("description"),
                            "url": article.get("url"),
                            "published_at": article.get("publishedAt"),
                            "content": article.get("content")
                        })

                    return formatted_articles
                else:
                    error_msg = await response.text()
                    raise Exception(f"NewsAPI request failed: {response.status} - {error_msg}")

    async def analyze(self, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze news articles with relevance filtering and categorization.

        For Alpha Vantage-sourced articles, relevance scores are pre-computed.
        For NewsAPI-sourced articles, our two-layer defense applies:
        1. Smart query (in fetch_data) reduces irrelevant articles from NewsAPI
        2. Relevance scoring here catches any that slip through

        Args:
            raw_data: Raw news data from fetch_data()

        Returns:
            Analyzed news data with relevance-filtered articles
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
                "summary": "No news articles found for this ticker."
            }

        # Score and filter articles for relevance
        scored_articles = []
        for article in articles:
            # AV articles already have relevance_score from the API
            if data_source == "alpha_vantage" and "relevance_score" in article:
                scored_articles.append(article)
            else:
                relevance = self._score_article_relevance(article, company_info)
                article_with_score = {**article, "relevance_score": round(relevance, 3)}
                scored_articles.append(article_with_score)

        # Sort by relevance descending
        scored_articles.sort(key=lambda a: a["relevance_score"], reverse=True)

        # Filter out articles below threshold
        filtered_articles = [
            a for a in scored_articles if a["relevance_score"] >= self.RELEVANCE_THRESHOLD
        ]

        removed_count = len(articles) - len(filtered_articles)
        if removed_count > 0:
            self.logger.info(
                f"Relevance filter: kept {len(filtered_articles)}/{len(articles)} articles "
                f"for {self.ticker} (removed {removed_count} below {self.RELEVANCE_THRESHOLD} threshold)"
            )

        # If all articles were filtered out, return empty with honest message
        if not filtered_articles:
            return {
                "articles": [],
                "total_count": 0,
                "filtered_count": removed_count,
                "categories": {},
                "recent_count": 0,
                "summary": f"No relevant news articles found for {self.ticker}. "
                           f"{removed_count} articles were removed as irrelevant."
            }

        # Categorize filtered articles
        categorized = self._categorize_articles(filtered_articles)

        # Count recent articles (last 24 hours)
        recent_count = self._count_recent_articles(filtered_articles, hours=24)

        # Extract key headlines (from filtered, relevance-sorted list)
        key_headlines = self._extract_key_headlines(filtered_articles, limit=5)

        analysis = {
            "articles": filtered_articles,
            "total_count": len(filtered_articles),
            "filtered_count": removed_count,
            "categories": categorized,
            "recent_count": recent_count,
            "key_headlines": key_headlines,
            "summary": self._generate_summary(filtered_articles, recent_count, removed_count)
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

    def _generate_summary(
        self,
        articles: List[Dict[str, Any]],
        recent_count: int,
        filtered_count: int = 0
    ) -> str:
        """Generate news summary including filter stats."""
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
            summary += "High news volume indicates significant activity."
        elif recent_count == 0:
            summary += "Low recent news activity."

        return summary
