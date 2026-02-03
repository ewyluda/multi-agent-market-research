"""Solution agent for synthesizing all agent outputs into final recommendation."""

import anthropic
import json
from typing import Dict, Any
from .base_agent import BaseAgent


class SolutionAgent(BaseAgent):
    """Agent that synthesizes all agent outputs using chain-of-thought reasoning."""

    def __init__(self, ticker: str, config: Dict[str, Any], agent_results: Dict[str, Any]):
        """
        Initialize solution agent with results from other agents.

        Args:
            ticker: Stock ticker
            config: Configuration
            agent_results: Dictionary of results from all other agents
        """
        super().__init__(ticker, config)
        self.agent_results = agent_results

    async def fetch_data(self) -> Dict[str, Any]:
        """
        Fetch data (already provided in constructor).

        Returns:
            Agent results dictionary
        """
        return self.agent_results

    async def analyze(self, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Synthesize all agent outputs into final recommendation.

        Args:
            raw_data: Results from all agents

        Returns:
            Final analysis with recommendation
        """
        # Extract data from each agent
        news_data = raw_data.get("news", {}).get("data", {})
        sentiment_data = raw_data.get("sentiment", {}).get("data", {})
        fundamentals_data = raw_data.get("fundamentals", {}).get("data", {})
        market_data = raw_data.get("market", {}).get("data", {})
        technical_data = raw_data.get("technical", {}).get("data", {})

        # Use LLM for chain-of-thought reasoning
        llm_config = self.config.get("llm_config", {})
        provider = llm_config.get("provider", "anthropic")

        if provider == "anthropic" and llm_config.get("api_key"):
            analysis = await self._synthesize_with_llm(
                news_data, sentiment_data, fundamentals_data,
                market_data, technical_data, llm_config
            )
        else:
            # Fallback to rule-based synthesis
            analysis = self._simple_synthesis(
                news_data, sentiment_data, fundamentals_data,
                market_data, technical_data
            )

        return analysis

    async def _synthesize_with_llm(
        self,
        news_data: Dict[str, Any],
        sentiment_data: Dict[str, Any],
        fundamentals_data: Dict[str, Any],
        market_data: Dict[str, Any],
        technical_data: Dict[str, Any],
        llm_config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Use LLM for chain-of-thought reasoning and synthesis.

        Args:
            news_data: News agent output
            sentiment_data: Sentiment agent output
            fundamentals_data: Fundamentals agent output
            market_data: Market agent output
            technical_data: Technical agent output
            llm_config: LLM configuration

        Returns:
            Synthesized analysis with recommendation
        """
        # Construct comprehensive prompt
        prompt = f"""You are an expert financial analyst. Analyze {self.ticker} using the following data from specialized agents:

## FUNDAMENTALS
- Company: {fundamentals_data.get('company_name', 'N/A')}
- Sector: {fundamentals_data.get('sector', 'N/A')}
- P/E Ratio: {fundamentals_data.get('pe_ratio', 'N/A')}
- Profit Margins: {fundamentals_data.get('profit_margins', 'N/A')}
- ROE: {fundamentals_data.get('return_on_equity', 'N/A')}
- Dividend Yield: {fundamentals_data.get('dividend_yield', 'N/A')}
- Health Score: {fundamentals_data.get('health_score', 'N/A')}/100
- Summary: {fundamentals_data.get('summary', '')}

## MARKET DATA
- Current Price: ${market_data.get('current_price', 'N/A')}
- Trend: {market_data.get('trend', 'N/A')}
- 1-Month Change: {market_data.get('price_change_1m', {}).get('change_pct', 'N/A')}%
- 3-Month Change: {market_data.get('price_change_3m', {}).get('change_pct', 'N/A')}%
- Volatility: {market_data.get('volatility_3m', 'N/A')}%
- Volume Trend: {market_data.get('volume_trend_1m', 'N/A')}
- Support: ${market_data.get('support_level', 'N/A')}
- Resistance: ${market_data.get('resistance_level', 'N/A')}
- Summary: {market_data.get('summary', '')}

## TECHNICAL ANALYSIS
- RSI: {technical_data.get('indicators', {}).get('rsi', {}).get('value', 'N/A')} ({technical_data.get('indicators', {}).get('rsi', {}).get('interpretation', 'N/A')})
- MACD: {technical_data.get('indicators', {}).get('macd', {}).get('interpretation', 'N/A')}
- Bollinger Bands: {technical_data.get('indicators', {}).get('bollinger_bands', {}).get('interpretation', 'N/A')}
- Overall Signal: {technical_data.get('signals', {}).get('overall', 'N/A')}
- Signal Strength: {technical_data.get('signals', {}).get('strength', 'N/A')}
- Summary: {technical_data.get('summary', '')}

## SENTIMENT ANALYSIS
- Overall Sentiment: {sentiment_data.get('overall_sentiment', 'N/A')}
- Confidence: {sentiment_data.get('confidence', 'N/A')}
- Factors:
  - Earnings: {sentiment_data.get('factors', {}).get('earnings', {})}
  - Guidance: {sentiment_data.get('factors', {}).get('guidance', {})}
  - Stock Reactions: {sentiment_data.get('factors', {}).get('stock_reactions', {})}
  - Strategic News: {sentiment_data.get('factors', {}).get('strategic_news', {})}
- Key Themes: {sentiment_data.get('key_themes', [])}
- Reasoning: {sentiment_data.get('reasoning', '')}

## NEWS SUMMARY
- Total Articles: {news_data.get('total_count', 0)}
- Recent (24h): {news_data.get('recent_count', 0)}
- Key Headlines: {[h.get('title', '') for h in news_data.get('key_headlines', [])[:3]]}

Using chain-of-thought reasoning and first principles:

1. Assess current company health (fundamentals)
2. Evaluate market conditions and price action
3. Consider sentiment and news impact
4. Synthesize technical signals
5. Determine risk/reward ratio
6. Provide final recommendation

Respond in JSON format:
{{
  "recommendation": "<BUY|HOLD|SELL>",
  "score": <integer from -100 (strong sell) to +100 (strong buy), with 0 being neutral>,
  "confidence": <float from 0.0 to 1.0>,
  "reasoning": "<comprehensive explanation using chain-of-thought reasoning>",
  "risks": ["<risk1>", "<risk2>", "<risk3>"],
  "opportunities": ["<opportunity1>", "<opportunity2>", "<opportunity3>"],
  "price_targets": {{
    "entry": <suggested entry price>,
    "target": <price target>,
    "stop_loss": <stop loss price>
  }},
  "position_size": "<SMALL|MEDIUM|LARGE>",
  "time_horizon": "<SHORT_TERM|MEDIUM_TERM|LONG_TERM>"
}}"""

        try:
            client = anthropic.Anthropic(api_key=llm_config.get("api_key"))

            message = client.messages.create(
                model=llm_config.get("model", "claude-3-5-sonnet-20241022"),
                max_tokens=llm_config.get("max_tokens", 4096),
                temperature=llm_config.get("temperature", 0.3),
                messages=[
                    {
                        "role": "user",
                        "content": prompt
                    }
                ]
            )

            # Extract JSON from response
            response_text = message.content[0].text

            # Parse JSON
            import re
            json_match = re.search(r'```json\s*(\{.*?\})\s*```', response_text, re.DOTALL)
            if json_match:
                json_str = json_match.group(1)
            else:
                json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
                if json_match:
                    json_str = json_match.group(0)
                else:
                    raise ValueError("Could not find JSON in LLM response")

            result = json.loads(json_str)

            # Add summary
            result["summary"] = self._generate_summary(result)

            return result

        except Exception as e:
            self.logger.error(f"LLM synthesis failed: {e}", exc_info=True)
            # Fallback
            return self._simple_synthesis(
                news_data, sentiment_data, fundamentals_data,
                market_data, technical_data
            )

    def _simple_synthesis(
        self,
        news_data: Dict[str, Any],
        sentiment_data: Dict[str, Any],
        fundamentals_data: Dict[str, Any],
        market_data: Dict[str, Any],
        technical_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Simple rule-based synthesis as fallback.

        Args:
            Agent outputs

        Returns:
            Basic recommendation
        """
        # Calculate weighted score
        score = 0

        # Fundamentals (30% weight)
        health_score = fundamentals_data.get("health_score", 50)
        score += (health_score - 50) * 0.6  # Convert 0-100 to -30 to +30

        # Technical (25% weight)
        tech_strength = technical_data.get("signals", {}).get("strength", 0)
        score += tech_strength * 0.25  # -25 to +25

        # Sentiment (25% weight)
        sentiment_score = sentiment_data.get("overall_sentiment", 0)
        score += sentiment_score * 25  # -25 to +25

        # Market trend (20% weight)
        trend = market_data.get("trend", "sideways")
        if "uptrend" in trend:
            score += 20
        elif "downtrend" in trend:
            score -= 20

        # Determine recommendation
        if score > 30:
            recommendation = "BUY"
        elif score < -30:
            recommendation = "SELL"
        else:
            recommendation = "HOLD"

        return {
            "recommendation": recommendation,
            "score": int(max(-100, min(100, score))),
            "confidence": 0.6,
            "reasoning": f"Based on weighted analysis: Fundamentals ({health_score}/100), Technical ({tech_strength}), Sentiment ({sentiment_score:.2f}), Trend ({trend})",
            "risks": ["Market volatility", "Sector-specific risks"],
            "opportunities": ["Potential upside based on fundamentals"],
            "price_targets": {
                "entry": market_data.get("current_price"),
                "target": None,
                "stop_loss": None
            },
            "position_size": "MEDIUM",
            "time_horizon": "MEDIUM_TERM",
            "summary": f"Recommendation: {recommendation} (Score: {int(score)})"
        }

    def _generate_summary(self, result: Dict[str, Any]) -> str:
        """Generate executive summary."""
        recommendation = result.get("recommendation", "HOLD")
        score = result.get("score", 0)
        confidence = result.get("confidence", 0.0)

        summary = f"Recommendation: {recommendation} (Score: {score:+d}). "
        summary += f"Confidence: {confidence:.0%}. "

        reasoning = result.get("reasoning", "")
        if reasoning:
            # Take first sentence of reasoning
            first_sentence = reasoning.split('.')[0] + '.'
            summary += first_sentence

        return summary
