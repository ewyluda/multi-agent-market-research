"""News agent for gathering financial news articles."""

import aiohttp
import asyncio
from typing import Dict, Any, List
from datetime import datetime, timedelta
from .base_agent import BaseAgent


class NewsAgent(BaseAgent):
    """Agent for fetching financial news from various sources."""

    async def fetch_data(self) -> Dict[str, Any]:
        """
        Fetch news articles from NewsAPI and other sources.

        Returns:
            Dictionary with news articles
        """
        articles = []

        # Fetch from NewsAPI if key is available
        news_api_key = self.config.get("NEWS_API_KEY")
        if news_api_key:
            try:
                news_articles = await self._fetch_from_newsapi(news_api_key)
                articles.extend(news_articles)
            except Exception as e:
                self.logger.warning(f"Failed to fetch from NewsAPI: {e}")

        # Could add more sources here (Twitter, RSS feeds, etc.)

        return {
            "articles": articles,
            "ticker": self.ticker,
            "total_count": len(articles)
        }

    async def _fetch_from_newsapi(self, api_key: str) -> List[Dict[str, Any]]:
        """
        Fetch news from NewsAPI.

        Args:
            api_key: NewsAPI key

        Returns:
            List of article dictionaries
        """
        base_url = self.config.get("NEWS_API_BASE_URL", "https://newsapi.org/v2")
        lookback_days = self.config.get("NEWS_LOOKBACK_DAYS", 7)
        max_articles = self.config.get("MAX_NEWS_ARTICLES", 20)

        # Calculate date range
        to_date = datetime.now()
        from_date = to_date - timedelta(days=lookback_days)

        # Build query - search for ticker symbol and company name
        query = self.ticker

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
        Analyze news articles for relevance and categorization.

        Args:
            raw_data: Raw news data

        Returns:
            Analyzed news data with categorization
        """
        articles = raw_data.get("articles", [])

        if not articles:
            return {
                "articles": [],
                "total_count": 0,
                "categories": {},
                "recent_count": 0,
                "summary": "No news articles found for this ticker."
            }

        # Categorize articles
        categorized = self._categorize_articles(articles)

        # Count recent articles (last 24 hours)
        recent_count = self._count_recent_articles(articles, hours=24)

        # Extract key headlines
        key_headlines = self._extract_key_headlines(articles, limit=5)

        analysis = {
            "articles": articles,
            "total_count": len(articles),
            "categories": categorized,
            "recent_count": recent_count,
            "key_headlines": key_headlines,
            "summary": self._generate_summary(articles, recent_count)
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
        """Extract key headlines."""
        headlines = []

        for article in articles[:limit]:
            headlines.append({
                "title": article.get("title", ""),
                "source": article.get("source", ""),
                "url": article.get("url", ""),
                "published_at": article.get("published_at", "")
            })

        return headlines

    def _generate_summary(self, articles: List[Dict[str, Any]], recent_count: int) -> str:
        """Generate news summary."""
        total = len(articles)

        if total == 0:
            return "No recent news articles found."

        summary = f"Found {total} news articles. "
        summary += f"{recent_count} published in the last 24 hours. "

        # Mention if high news volume
        if recent_count > 5:
            summary += "High news volume indicates significant activity."
        elif recent_count == 0:
            summary += "Low recent news activity."

        return summary
