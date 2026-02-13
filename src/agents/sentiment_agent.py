"""Sentiment agent for analyzing market sentiment using LLM."""

import asyncio
import anthropic
from openai import OpenAI
from typing import Dict, Any, List, Optional
import json
from .base_agent import BaseAgent


class SentimentAgent(BaseAgent):
    """Agent for analyzing sentiment using LLM-based analysis."""

    async def fetch_data(self) -> Dict[str, Any]:
        """
        Fetch data required for sentiment analysis.
        This agent depends on outputs from news and market agents.

        Returns:
            Dictionary with placeholder for news data
        """
        # This agent will receive news articles from the orchestrator
        # For now, return empty structure
        return {
            "ticker": self.ticker,
            "news_articles": [],
            "market_data": {}
        }

    async def analyze(self, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze sentiment using LLM.

        Args:
            raw_data: Dictionary with news articles and market context

        Returns:
            Sentiment analysis with factor breakdown
        """
        news_articles = raw_data.get("news_articles", [])
        market_data = raw_data.get("market_data", {})
        twitter_posts = raw_data.get("twitter_posts", [])

        if not news_articles or len(news_articles) == 0:
            return {
                "overall_sentiment": 0.0,
                "confidence": 0.0,
                "factors": {},
                "summary": "No news data available for sentiment analysis"
            }

        # Use LLM to analyze sentiment
        llm_config = self.config.get("llm_config", {})
        provider = llm_config.get("provider", "anthropic")

        if provider == "anthropic":
            analysis = await self._analyze_with_anthropic(news_articles, market_data, llm_config, twitter_posts)
        elif provider in ("xai", "openai"):
            analysis = await self._analyze_with_openai(news_articles, market_data, llm_config, twitter_posts)
        else:
            # Fallback to simple analysis
            analysis = self._simple_sentiment_analysis(news_articles)

        return analysis

    async def _analyze_with_anthropic(
        self,
        articles: List[Dict[str, Any]],
        market_data: Dict[str, Any],
        llm_config: Dict[str, Any],
        twitter_posts: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """
        Analyze sentiment using Anthropic Claude API.

        Args:
            articles: News articles
            market_data: Market context
            llm_config: LLM configuration
            twitter_posts: Optional tweets from Twitter/X

        Returns:
            Sentiment analysis
        """
        api_key = llm_config.get("api_key")
        if not api_key:
            self.logger.warning("No Anthropic API key provided, using simple analysis")
            return self._simple_sentiment_analysis(articles)

        # Prepare article summaries for LLM (with AV sentiment enrichment)
        articles_text, av_sentiment_section = self._build_article_summaries(articles)
        twitter_section = self._build_twitter_section(twitter_posts or [])

        # Get sentiment factors config
        sentiment_factors = self.config.get("SENTIMENT_FACTORS", {})

        # Construct prompt
        prompt = f"""Analyze the market sentiment for {self.ticker} based on the following recent news articles:

{articles_text}
{av_sentiment_section}{twitter_section}
Market Context:
- Current Price: {market_data.get('current_price', 'N/A')}
- 1-Month Change: {market_data.get('price_change_1m', {}).get('change_pct', 'N/A')}%
- Trend: {market_data.get('trend', 'N/A')}

Analyze sentiment across these factors:
1. Earnings Performance: Earnings beats/misses, revenue growth
2. Guidance/EV Losses: Forward guidance changes, strategic concerns
3. Stock Reactions: Market reactions to announcements
4. Strategic News: New initiatives, partnerships, leadership changes
5. Social Sentiment: Twitter/X community sentiment and buzz level

For each factor, provide:
- Score: -1.0 (very bearish) to +1.0 (very bullish)
- Weight: Relative importance (0.0 to 1.0)
- Contribution: Score × Weight

Respond in JSON format:
{{
  "overall_sentiment": <float from -1.0 to 1.0>,
  "confidence": <float from 0.0 to 1.0>,
  "factors": {{
    "earnings": {{"score": <float>, "weight": <float>, "contribution": <float>}},
    "guidance": {{"score": <float>, "weight": <float>, "contribution": <float>}},
    "stock_reactions": {{"score": <float>, "weight": <float>, "contribution": <float>}},
    "strategic_news": {{"score": <float>, "weight": <float>, "contribution": <float>}},
    "social_sentiment": {{"score": <float>, "weight": <float>, "contribution": <float>}}
  }},
  "reasoning": "<brief explanation of the overall sentiment>",
  "key_themes": ["<theme1>", "<theme2>", "<theme3>"]
}}"""

        try:
            client = anthropic.Anthropic(api_key=api_key)

            def _call_anthropic():
                return client.messages.create(
                    model=llm_config.get("model", "claude-3-5-sonnet-20241022"),
                    max_tokens=llm_config.get("max_tokens", 2048),
                    temperature=llm_config.get("temperature", 0.3),
                    messages=[
                        {
                            "role": "user",
                            "content": prompt
                        }
                    ]
                )

            message = await asyncio.to_thread(_call_anthropic)

            # Extract JSON from response
            response_text = message.content[0].text

            # Try to parse JSON from response
            # Claude might wrap it in markdown code blocks
            import re
            json_match = re.search(r'```json\s*(\{.*?\})\s*```', response_text, re.DOTALL)
            if json_match:
                json_str = json_match.group(1)
            else:
                # Try to find raw JSON
                json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
                if json_match:
                    json_str = json_match.group(0)
                else:
                    raise ValueError("Could not find JSON in LLM response")

            result = json.loads(json_str)

            # Add summary
            result["summary"] = self._generate_summary_from_llm_result(result)

            return result

        except Exception as e:
            self.logger.error(f"LLM sentiment analysis failed: {e}", exc_info=True)
            # Fallback to simple analysis
            return self._simple_sentiment_analysis(articles)

    async def _analyze_with_openai(
        self,
        articles: List[Dict[str, Any]],
        market_data: Dict[str, Any],
        llm_config: Dict[str, Any],
        twitter_posts: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """
        Analyze sentiment using OpenAI-compatible API (works with xAI/Grok, OpenAI, etc).

        Args:
            articles: News articles
            market_data: Market context
            llm_config: LLM configuration
            twitter_posts: Optional tweets from Twitter/X

        Returns:
            Sentiment analysis
        """
        api_key = llm_config.get("api_key")
        if not api_key:
            self.logger.warning("No API key provided for OpenAI-compatible provider, using simple analysis")
            return self._simple_sentiment_analysis(articles)

        # Prepare article summaries for LLM (with AV sentiment enrichment)
        articles_text, av_sentiment_section = self._build_article_summaries(articles)
        twitter_section = self._build_twitter_section(twitter_posts or [])

        # Construct prompt (same as Anthropic version)
        prompt = f"""Analyze the market sentiment for {self.ticker} based on the following recent news articles:

{articles_text}
{av_sentiment_section}{twitter_section}
Market Context:
- Current Price: {market_data.get('current_price', 'N/A')}
- 1-Month Change: {market_data.get('price_change_1m', {}).get('change_pct', 'N/A')}%
- Trend: {market_data.get('trend', 'N/A')}

Analyze sentiment across these factors:
1. Earnings Performance: Earnings beats/misses, revenue growth
2. Guidance/EV Losses: Forward guidance changes, strategic concerns
3. Stock Reactions: Market reactions to announcements
4. Strategic News: New initiatives, partnerships, leadership changes
5. Social Sentiment: Twitter/X community sentiment and buzz level

For each factor, provide:
- Score: -1.0 (very bearish) to +1.0 (very bullish)
- Weight: Relative importance (0.0 to 1.0)
- Contribution: Score × Weight

Respond in JSON format:
{{
  "overall_sentiment": <float from -1.0 to 1.0>,
  "confidence": <float from 0.0 to 1.0>,
  "factors": {{
    "earnings": {{"score": <float>, "weight": <float>, "contribution": <float>}},
    "guidance": {{"score": <float>, "weight": <float>, "contribution": <float>}},
    "stock_reactions": {{"score": <float>, "weight": <float>, "contribution": <float>}},
    "strategic_news": {{"score": <float>, "weight": <float>, "contribution": <float>}},
    "social_sentiment": {{"score": <float>, "weight": <float>, "contribution": <float>}}
  }},
  "reasoning": "<brief explanation of the overall sentiment>",
  "key_themes": ["<theme1>", "<theme2>", "<theme3>"]
}}"""

        try:
            client = OpenAI(
                api_key=api_key,
                base_url=llm_config.get("base_url")
            )

            def _call_openai():
                return client.chat.completions.create(
                    model=llm_config.get("model", "grok-4-1-fast-reasoning"),
                    max_tokens=llm_config.get("max_tokens", 2048),
                    temperature=llm_config.get("temperature", 0.3),
                    messages=[
                        {
                            "role": "user",
                            "content": prompt
                        }
                    ]
                )

            response = await asyncio.to_thread(_call_openai)

            # Extract JSON from response
            response_text = response.choices[0].message.content

            # Try to parse JSON from response
            import re
            json_match = re.search(r'```json\s*(\{.*?\})\s*```', response_text, re.DOTALL)
            if json_match:
                json_str = json_match.group(1)
            else:
                # Try to find raw JSON
                json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
                if json_match:
                    json_str = json_match.group(0)
                else:
                    raise ValueError("Could not find JSON in LLM response")

            result = json.loads(json_str)

            # Add summary
            result["summary"] = self._generate_summary_from_llm_result(result)

            return result

        except Exception as e:
            self.logger.error(f"OpenAI-compatible sentiment analysis failed: {e}", exc_info=True)
            # Fallback to simple analysis
            return self._simple_sentiment_analysis(articles)

    def _simple_sentiment_analysis(self, articles: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Simple rule-based sentiment analysis as fallback.

        Args:
            articles: News articles

        Returns:
            Basic sentiment analysis
        """
        positive_keywords = [
            "beat", "beats", "exceed", "strong", "growth", "gain", "up", "positive",
            "surge", "rally", "bullish", "upgrade", "outperform", "success", "record"
        ]
        negative_keywords = [
            "miss", "misses", "weak", "decline", "loss", "down", "negative", "fall",
            "drop", "bearish", "downgrade", "underperform", "concern", "risk", "warning"
        ]

        positive_count = 0
        negative_count = 0

        for article in articles:
            content = (
                (article.get("title") or "") + " " +
                (article.get("description") or "")
            ).lower()

            for keyword in positive_keywords:
                if keyword in content:
                    positive_count += 1

            for keyword in negative_keywords:
                if keyword in content:
                    negative_count += 1

        total = positive_count + negative_count
        if total == 0:
            sentiment_score = 0.0
        else:
            sentiment_score = (positive_count - negative_count) / total

        # Blend in AV pre-computed sentiment scores when available
        av_scores = [a.get("av_ticker_sentiment_score") for a in articles
                     if a.get("av_ticker_sentiment_score") is not None]
        if av_scores:
            av_avg = sum(av_scores) / len(av_scores)
            # Weight: 60% AV scores, 40% keyword score (AV is more reliable)
            sentiment_score = max(-1.0, min(1.0, (0.6 * av_avg) + (0.4 * sentiment_score)))
            confidence = 0.65
            reasoning = (
                f"Blended analysis: AV avg sentiment {av_avg:+.3f} ({len(av_scores)} articles), "
                f"keywords: {positive_count} positive, {negative_count} negative"
            )
        else:
            confidence = 0.5
            reasoning = f"Basic keyword analysis: {positive_count} positive, {negative_count} negative mentions"

        return {
            "overall_sentiment": sentiment_score,
            "confidence": confidence,
            "factors": {
                "earnings": {"score": sentiment_score * 0.7, "weight": 0.3, "contribution": sentiment_score * 0.21},
                "guidance": {"score": sentiment_score * 0.6, "weight": 0.4, "contribution": sentiment_score * 0.24},
                "stock_reactions": {"score": sentiment_score * 0.8, "weight": 0.2, "contribution": sentiment_score * 0.16},
                "strategic_news": {"score": sentiment_score * 0.5, "weight": 0.1, "contribution": sentiment_score * 0.05}
            },
            "reasoning": reasoning,
            "key_themes": ["general market sentiment"],
            "summary": f"Sentiment: {'Positive' if sentiment_score > 0 else 'Negative' if sentiment_score < 0 else 'Neutral'} (confidence: {'medium' if av_scores else 'low'})"
        }

    def _build_article_summaries(self, articles: List[Dict[str, Any]]) -> tuple:
        """Build article summary text and AV sentiment section for LLM prompts.

        Returns:
            Tuple of (articles_text, av_sentiment_section)
        """
        article_summaries = []
        for i, article in enumerate(articles[:10], 1):
            title = article.get("title", "")
            description = article.get("description", "")
            published = article.get("published_at", "")

            summary_line = f"{i}. [{published}] {title}\n   {description}"

            # Append AV pre-computed sentiment if available
            av_sentiment_score = article.get("av_ticker_sentiment_score")
            av_sentiment_label = article.get("av_ticker_sentiment_label", "")
            av_relevance = article.get("av_ticker_relevance")
            if av_sentiment_score is not None:
                summary_line += (
                    f"\n   [AV Sentiment: {av_sentiment_label} ({av_sentiment_score:+.3f}), "
                    f"Relevance: {av_relevance:.2f}]"
                )

            article_summaries.append(summary_line)

        articles_text = "\n\n".join(article_summaries)

        # Compute AV sentiment aggregate stats
        av_scores = [a.get("av_ticker_sentiment_score") for a in articles[:10]
                     if a.get("av_ticker_sentiment_score") is not None]
        av_sentiment_section = ""
        if av_scores:
            avg_score = sum(av_scores) / len(av_scores)
            bullish_count = sum(1 for a in articles[:10]
                               if (a.get("av_ticker_sentiment_label") or "").lower().startswith("bull"))
            bearish_count = sum(1 for a in articles[:10]
                               if (a.get("av_ticker_sentiment_label") or "").lower().startswith("bear"))
            neutral_count = len(av_scores) - bullish_count - bearish_count
            av_sentiment_section = (
                f"\nAlpha Vantage Pre-Computed Sentiment (for reference):\n"
                f"- Average Ticker Sentiment Score: {avg_score:+.3f}\n"
                f"- Distribution: {bullish_count} bullish, {neutral_count} neutral, {bearish_count} bearish\n"
                f"- Note: These are machine-computed scores. Use them as one input alongside your own analysis.\n"
            )

        return articles_text, av_sentiment_section

    def _build_twitter_section(self, twitter_posts: List[Dict[str, Any]]) -> str:
        """Build Twitter/X social sentiment section for LLM prompts.

        Args:
            twitter_posts: List of tweet dicts from NewsAgent

        Returns:
            Formatted string section for inclusion in LLM prompt
        """
        if not twitter_posts:
            return ""

        lines = ["\nTwitter/X Social Sentiment (recent cashtag mentions, sorted by engagement):"]
        for i, tweet in enumerate(twitter_posts[:10], 1):
            text = tweet.get("text", "").replace("\n", " ")[:200]
            metrics = tweet.get("metrics", {})
            engagement = tweet.get("engagement", 0)
            created = tweet.get("created_at", "")
            lines.append(
                f"{i}. [{created}] {text}\n"
                f"   [Likes: {metrics.get('likes', 0)}, "
                f"RTs: {metrics.get('retweets', 0)}, "
                f"Replies: {metrics.get('replies', 0)}, "
                f"Total engagement: {engagement}]"
            )

        total = len(twitter_posts)
        total_engagement = sum(t.get("engagement", 0) for t in twitter_posts)
        lines.append(
            f"\nTwitter Summary: {total} tweets found, "
            f"total engagement: {total_engagement}. "
            f"Use these as a supplementary social signal — not a primary indicator.\n"
        )

        return "\n".join(lines)

    def _generate_summary_from_llm_result(self, result: Dict[str, Any]) -> str:
        """Generate summary from LLM analysis result."""
        sentiment = result.get("overall_sentiment", 0.0)
        confidence = result.get("confidence", 0.0)

        if sentiment > 0.3:
            sentiment_label = "Positive"
        elif sentiment < -0.3:
            sentiment_label = "Negative"
        else:
            sentiment_label = "Neutral"

        summary = f"Overall sentiment: {sentiment_label} ({sentiment:+.2f}). "
        summary += f"Confidence: {confidence:.0%}. "

        reasoning = result.get("reasoning", "")
        if reasoning:
            summary += reasoning

        return summary

    def set_context_data(
        self,
        news_articles: List[Dict[str, Any]],
        market_data: Dict[str, Any],
        twitter_posts: Optional[List[Dict[str, Any]]] = None,
    ):
        """
        Set context data from other agents for sentiment analysis.

        Args:
            news_articles: Articles from NewsAgent
            market_data: Market data from MarketAgent
            twitter_posts: Optional tweets from NewsAgent's Twitter/X fetch
        """
        self._context_news = news_articles
        self._context_market = market_data
        self._context_twitter = twitter_posts or []

    async def execute(self) -> Dict[str, Any]:
        """
        Execute sentiment analysis with context data.

        Returns:
            Analysis result
        """
        # Use context data if available
        if hasattr(self, '_context_news') and hasattr(self, '_context_market'):
            raw_data = {
                "ticker": self.ticker,
                "news_articles": self._context_news,
                "market_data": self._context_market,
                "twitter_posts": getattr(self, '_context_twitter', []),
            }
            return await self._execute_with_data(raw_data)
        else:
            # Fall back to standard execution
            return await super().execute()

    async def _execute_with_data(self, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        """Execute with provided data."""
        import time
        from datetime import datetime

        self.start_time = time.time()
        timestamp = datetime.utcnow().isoformat()

        try:
            self.logger.info(f"Starting {self.__class__.__name__} for {self.ticker}")

            # Analyze data directly
            analysis_result = await self.analyze(raw_data)
            self.logger.debug(f"Analysis complete")

            self.result = analysis_result
            self.end_time = time.time()

            return {
                "success": True,
                "agent_type": self.get_agent_type(),
                "data": analysis_result,
                "error": None,
                "duration_seconds": self.get_duration(),
                "timestamp": timestamp
            }

        except Exception as e:
            self.error = str(e)
            self.end_time = time.time()
            self.logger.error(f"{self.__class__.__name__} failed: {e}", exc_info=True)

            return {
                "success": False,
                "agent_type": self.get_agent_type(),
                "data": None,
                "error": str(e),
                "duration_seconds": self.get_duration(),
                "timestamp": timestamp
            }
