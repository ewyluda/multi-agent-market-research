"""Solution agent for synthesizing all agent outputs into final recommendation."""

import asyncio
import anthropic
from openai import OpenAI
import json
from typing import Dict, Any, Optional
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
        # Extract data from each agent (use `or {}` to handle None values)
        news_data = (raw_data.get("news") or {}).get("data") or {}
        sentiment_data = (raw_data.get("sentiment") or {}).get("data") or {}
        fundamentals_data = (raw_data.get("fundamentals") or {}).get("data") or {}
        market_data = (raw_data.get("market") or {}).get("data") or {}
        technical_data = (raw_data.get("technical") or {}).get("data") or {}
        macro_data = (raw_data.get("macro") or {}).get("data") or {}
        options_data = (raw_data.get("options") or {}).get("data") or {}

        # Use LLM for chain-of-thought reasoning
        llm_config = self.config.get("llm_config", {})
        provider = llm_config.get("provider", "anthropic")

        if provider == "anthropic" and llm_config.get("api_key"):
            analysis = await self._synthesize_with_llm(
                news_data, sentiment_data, fundamentals_data,
                market_data, technical_data, macro_data, options_data, llm_config
            )
        elif provider in ("xai", "openai") and llm_config.get("api_key"):
            analysis = await self._synthesize_with_openai(
                news_data, sentiment_data, fundamentals_data,
                market_data, technical_data, macro_data, options_data, llm_config
            )
        else:
            # Fallback to rule-based synthesis
            analysis = self._simple_synthesis(
                news_data, sentiment_data, fundamentals_data,
                market_data, technical_data, macro_data, options_data
            )

        return analysis

    async def _synthesize_with_llm(
        self,
        news_data: Dict[str, Any],
        sentiment_data: Dict[str, Any],
        fundamentals_data: Dict[str, Any],
        market_data: Dict[str, Any],
        technical_data: Dict[str, Any],
        macro_data: Dict[str, Any],
        options_data: Dict[str, Any],
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
            macro_data: Macroeconomic agent output
            options_data: Options flow agent output
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
- Earnings Beat Rate: {fundamentals_data.get('recent_earnings', {}).get('beat_rate', 'N/A')}% ({fundamentals_data.get('recent_earnings', {}).get('beats', 0)}/{fundamentals_data.get('recent_earnings', {}).get('total', 0)})
- Earnings Trend: {fundamentals_data.get('recent_earnings', {}).get('trend', 'N/A')}
- Summary: {fundamentals_data.get('summary', '')}

## SEC EDGAR FINANCIAL DATA
- EPS Trend: {fundamentals_data.get('eps_trend', {}).get('trend', 'N/A')}
- Latest EPS: {fundamentals_data.get('eps_trend', {}).get('latest_eps', 'N/A')}
- EPS QoQ Change: {fundamentals_data.get('eps_trend', {}).get('qoq_pct', 'N/A')}%
- EPS YoY Change: {fundamentals_data.get('eps_trend', {}).get('yoy_pct', 'N/A')}%
- Revenue Trend: {fundamentals_data.get('revenue_trend', {}).get('trend', 'N/A')}
- Latest Revenue: {fundamentals_data.get('revenue_trend', {}).get('latest_revenue', 'N/A')}
- Revenue QoQ Change: {fundamentals_data.get('revenue_trend', {}).get('qoq_pct', 'N/A')}%
- Revenue YoY Change: {fundamentals_data.get('revenue_trend', {}).get('yoy_pct', 'N/A')}%

## EQUITY RESEARCH REPORT (AI-Generated Deep Analysis)
- Executive Summary: {fundamentals_data.get('equity_research_report', {}).get('executive_summary', 'N/A') if fundamentals_data.get('equity_research_report') else 'Not available'}
- Bull Case Catalysts: {[c.get('catalyst', '') for c in (fundamentals_data.get('equity_research_report') or {}).get('bull_case', {}).get('catalysts', [])] if fundamentals_data.get('equity_research_report') else 'N/A'}
- Competitive Moat: {(fundamentals_data.get('equity_research_report') or {}).get('bull_case', {}).get('moat', 'N/A')}
- Existential Risk: {(fundamentals_data.get('equity_research_report') or {}).get('bear_case', {}).get('existential_risk', 'N/A')}
- Concerning Metrics: {[(c.get('metric', '') + ': ' + c.get('concern', '')) for c in (fundamentals_data.get('equity_research_report') or {}).get('bear_case', {}).get('concerning_metrics', [])] if fundamentals_data.get('equity_research_report') else 'N/A'}
- FCF Analysis: {(fundamentals_data.get('equity_research_report') or {}).get('financial_health_check', {}).get('fcf_analysis', 'N/A')}
- Valuation Analysis: {(fundamentals_data.get('equity_research_report') or {}).get('financial_health_check', {}).get('valuation_analysis', 'N/A')}
- Uncomfortable Questions: {(fundamentals_data.get('equity_research_report') or {}).get('uncomfortable_questions', [])}
- Overall Assessment: {(fundamentals_data.get('equity_research_report') or {}).get('overall_assessment', 'N/A')}

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

## OPTIONS FLOW & UNUSUAL ACTIVITY
- Put/Call Volume Ratio: {options_data.get('put_call_ratio', 'N/A')}
- Put/Call OI Ratio: {options_data.get('put_call_oi_ratio', 'N/A')}
- Max Pain Strike: ${options_data.get('max_pain', 'N/A')}
- Unusual Activity: {[f"{u.get('type', '')} ${u.get('strike', '')} exp {u.get('expiration', '')} (vol/OI: {u.get('vol_oi_ratio', '')}x)" for u in (options_data.get('unusual_activity', []))[:3]] or 'None detected'}
- Highest IV Contracts: {[f"{c.get('type', '')} ${c.get('strike', '')} IV={c.get('implied_volatility', '')}" for c in (options_data.get('highest_iv_contracts', []))[:3]] or 'N/A'}
- Overall Options Signal: {options_data.get('overall_signal', 'N/A')}
- Summary: {options_data.get('summary', 'No options data available')}

## MACROECONOMIC ENVIRONMENT
- Federal Funds Rate: {macro_data.get('indicators', {}).get('federal_funds_rate', {}).get('current', 'N/A')} (Trend: {macro_data.get('indicators', {}).get('federal_funds_rate', {}).get('trend', 'N/A')})
- CPI: {macro_data.get('indicators', {}).get('cpi', {}).get('current', 'N/A')} (Trend: {macro_data.get('indicators', {}).get('cpi', {}).get('trend', 'N/A')})
- Real GDP: {macro_data.get('indicators', {}).get('real_gdp', {}).get('current', 'N/A')} (Trend: {macro_data.get('indicators', {}).get('real_gdp', {}).get('trend', 'N/A')})
- Unemployment: {macro_data.get('indicators', {}).get('unemployment', {}).get('current', 'N/A')}% (Trend: {macro_data.get('indicators', {}).get('unemployment', {}).get('trend', 'N/A')})
- Inflation: {macro_data.get('indicators', {}).get('inflation', {}).get('current', 'N/A')}% (Trend: {macro_data.get('indicators', {}).get('inflation', {}).get('trend', 'N/A')})
- 10Y Treasury Yield: {macro_data.get('indicators', {}).get('treasury_yield_10y', {}).get('current', 'N/A')}%
- 2Y Treasury Yield: {macro_data.get('indicators', {}).get('treasury_yield_2y', {}).get('current', 'N/A')}%
- Yield Curve: {macro_data.get('yield_curve', {}).get('status', 'N/A')} (Spread: {macro_data.get('yield_curve', {}).get('spread', 'N/A')}%)
- Economic Cycle: {macro_data.get('economic_cycle', 'N/A')}
- Risk Environment: {macro_data.get('risk_environment', 'N/A')}
- Summary: {macro_data.get('summary', 'No macro data available')}

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

1. Assess current company health (fundamentals + SEC earnings data)
2. Consider the equity research report's bull/bear thesis, moat, and risk analysis
3. Evaluate market conditions and price action
4. Consider sentiment and news impact
5. Synthesize technical signals
6. Evaluate options flow signals (put/call ratios, unusual activity, max pain vs current price)
7. Factor in macroeconomic environment (interest rates, yield curve, economic cycle)
8. Analyze earnings trends (beat rate, EPS/revenue trajectory from SEC filings)
9. Weigh concerning metrics and existential risks identified
10. Determine risk/reward ratio
11. Provide final recommendation

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

            def _call_anthropic():
                return client.messages.create(
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

            message = await asyncio.to_thread(_call_anthropic)

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
                market_data, technical_data, macro_data, options_data
            )

    async def _synthesize_with_openai(
        self,
        news_data: Dict[str, Any],
        sentiment_data: Dict[str, Any],
        fundamentals_data: Dict[str, Any],
        market_data: Dict[str, Any],
        technical_data: Dict[str, Any],
        macro_data: Dict[str, Any],
        options_data: Dict[str, Any],
        llm_config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Use OpenAI-compatible API (xAI/Grok, OpenAI, etc) for synthesis.

        Args:
            news_data: News agent output
            sentiment_data: Sentiment agent output
            fundamentals_data: Fundamentals agent output
            market_data: Market agent output
            technical_data: Technical agent output
            macro_data: Macroeconomic agent output
            options_data: Options flow agent output
            llm_config: LLM configuration

        Returns:
            Synthesized analysis with recommendation
        """
        # Construct comprehensive prompt (same as Anthropic version)
        prompt = f"""You are an expert financial analyst. Analyze {self.ticker} using the following data from specialized agents:

## FUNDAMENTALS
- Company: {fundamentals_data.get('company_name', 'N/A')}
- Sector: {fundamentals_data.get('sector', 'N/A')}
- P/E Ratio: {fundamentals_data.get('pe_ratio', 'N/A')}
- Profit Margins: {fundamentals_data.get('profit_margins', 'N/A')}
- ROE: {fundamentals_data.get('return_on_equity', 'N/A')}
- Dividend Yield: {fundamentals_data.get('dividend_yield', 'N/A')}
- Health Score: {fundamentals_data.get('health_score', 'N/A')}/100
- Earnings Beat Rate: {fundamentals_data.get('recent_earnings', {}).get('beat_rate', 'N/A')}% ({fundamentals_data.get('recent_earnings', {}).get('beats', 0)}/{fundamentals_data.get('recent_earnings', {}).get('total', 0)})
- Earnings Trend: {fundamentals_data.get('recent_earnings', {}).get('trend', 'N/A')}
- Summary: {fundamentals_data.get('summary', '')}

## SEC EDGAR FINANCIAL DATA
- EPS Trend: {fundamentals_data.get('eps_trend', {}).get('trend', 'N/A')}
- Latest EPS: {fundamentals_data.get('eps_trend', {}).get('latest_eps', 'N/A')}
- EPS QoQ Change: {fundamentals_data.get('eps_trend', {}).get('qoq_pct', 'N/A')}%
- EPS YoY Change: {fundamentals_data.get('eps_trend', {}).get('yoy_pct', 'N/A')}%
- Revenue Trend: {fundamentals_data.get('revenue_trend', {}).get('trend', 'N/A')}
- Latest Revenue: {fundamentals_data.get('revenue_trend', {}).get('latest_revenue', 'N/A')}
- Revenue QoQ Change: {fundamentals_data.get('revenue_trend', {}).get('qoq_pct', 'N/A')}%
- Revenue YoY Change: {fundamentals_data.get('revenue_trend', {}).get('yoy_pct', 'N/A')}%

## EQUITY RESEARCH REPORT (AI-Generated Deep Analysis)
- Executive Summary: {fundamentals_data.get('equity_research_report', {}).get('executive_summary', 'N/A') if fundamentals_data.get('equity_research_report') else 'Not available'}
- Bull Case Catalysts: {[c.get('catalyst', '') for c in (fundamentals_data.get('equity_research_report') or {}).get('bull_case', {}).get('catalysts', [])] if fundamentals_data.get('equity_research_report') else 'N/A'}
- Competitive Moat: {(fundamentals_data.get('equity_research_report') or {}).get('bull_case', {}).get('moat', 'N/A')}
- Existential Risk: {(fundamentals_data.get('equity_research_report') or {}).get('bear_case', {}).get('existential_risk', 'N/A')}
- Concerning Metrics: {[(c.get('metric', '') + ': ' + c.get('concern', '')) for c in (fundamentals_data.get('equity_research_report') or {}).get('bear_case', {}).get('concerning_metrics', [])] if fundamentals_data.get('equity_research_report') else 'N/A'}
- FCF Analysis: {(fundamentals_data.get('equity_research_report') or {}).get('financial_health_check', {}).get('fcf_analysis', 'N/A')}
- Valuation Analysis: {(fundamentals_data.get('equity_research_report') or {}).get('financial_health_check', {}).get('valuation_analysis', 'N/A')}
- Uncomfortable Questions: {(fundamentals_data.get('equity_research_report') or {}).get('uncomfortable_questions', [])}
- Overall Assessment: {(fundamentals_data.get('equity_research_report') or {}).get('overall_assessment', 'N/A')}

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

## OPTIONS FLOW & UNUSUAL ACTIVITY
- Put/Call Volume Ratio: {options_data.get('put_call_ratio', 'N/A')}
- Put/Call OI Ratio: {options_data.get('put_call_oi_ratio', 'N/A')}
- Max Pain Strike: ${options_data.get('max_pain', 'N/A')}
- Unusual Activity: {[f"{u.get('type', '')} ${u.get('strike', '')} exp {u.get('expiration', '')} (vol/OI: {u.get('vol_oi_ratio', '')}x)" for u in (options_data.get('unusual_activity', []))[:3]] or 'None detected'}
- Highest IV Contracts: {[f"{c.get('type', '')} ${c.get('strike', '')} IV={c.get('implied_volatility', '')}" for c in (options_data.get('highest_iv_contracts', []))[:3]] or 'N/A'}
- Overall Options Signal: {options_data.get('overall_signal', 'N/A')}
- Summary: {options_data.get('summary', 'No options data available')}

## MACROECONOMIC ENVIRONMENT
- Federal Funds Rate: {macro_data.get('indicators', {}).get('federal_funds_rate', {}).get('current', 'N/A')} (Trend: {macro_data.get('indicators', {}).get('federal_funds_rate', {}).get('trend', 'N/A')})
- CPI: {macro_data.get('indicators', {}).get('cpi', {}).get('current', 'N/A')} (Trend: {macro_data.get('indicators', {}).get('cpi', {}).get('trend', 'N/A')})
- Real GDP: {macro_data.get('indicators', {}).get('real_gdp', {}).get('current', 'N/A')} (Trend: {macro_data.get('indicators', {}).get('real_gdp', {}).get('trend', 'N/A')})
- Unemployment: {macro_data.get('indicators', {}).get('unemployment', {}).get('current', 'N/A')}% (Trend: {macro_data.get('indicators', {}).get('unemployment', {}).get('trend', 'N/A')})
- Inflation: {macro_data.get('indicators', {}).get('inflation', {}).get('current', 'N/A')}% (Trend: {macro_data.get('indicators', {}).get('inflation', {}).get('trend', 'N/A')})
- 10Y Treasury Yield: {macro_data.get('indicators', {}).get('treasury_yield_10y', {}).get('current', 'N/A')}%
- 2Y Treasury Yield: {macro_data.get('indicators', {}).get('treasury_yield_2y', {}).get('current', 'N/A')}%
- Yield Curve: {macro_data.get('yield_curve', {}).get('status', 'N/A')} (Spread: {macro_data.get('yield_curve', {}).get('spread', 'N/A')}%)
- Economic Cycle: {macro_data.get('economic_cycle', 'N/A')}
- Risk Environment: {macro_data.get('risk_environment', 'N/A')}
- Summary: {macro_data.get('summary', 'No macro data available')}

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

1. Assess current company health (fundamentals + SEC earnings data)
2. Consider the equity research report's bull/bear thesis, moat, and risk analysis
3. Evaluate market conditions and price action
4. Consider sentiment and news impact
5. Synthesize technical signals
6. Evaluate options flow signals (put/call ratios, unusual activity, max pain vs current price)
7. Factor in macroeconomic environment (interest rates, yield curve, economic cycle)
8. Analyze earnings trends (beat rate, EPS/revenue trajectory from SEC filings)
9. Weigh concerning metrics and existential risks identified
10. Determine risk/reward ratio
11. Provide final recommendation

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
            client = OpenAI(
                api_key=llm_config.get("api_key"),
                base_url=llm_config.get("base_url")
            )

            def _call_openai():
                return client.chat.completions.create(
                    model=llm_config.get("model", "grok-4-1-fast-reasoning"),
                    max_tokens=llm_config.get("max_tokens", 4096),
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
            self.logger.error(f"OpenAI-compatible synthesis failed: {e}", exc_info=True)
            # Fallback
            return self._simple_synthesis(
                news_data, sentiment_data, fundamentals_data,
                market_data, technical_data, macro_data, options_data
            )

    def _simple_synthesis(
        self,
        news_data: Dict[str, Any],
        sentiment_data: Dict[str, Any],
        fundamentals_data: Dict[str, Any],
        market_data: Dict[str, Any],
        technical_data: Dict[str, Any],
        macro_data: Optional[Dict[str, Any]] = None,
        options_data: Optional[Dict[str, Any]] = None,
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

        # Fundamentals (28% weight)
        health_score = fundamentals_data.get("health_score", 50)
        score += (health_score - 50) * 0.56  # Convert 0-100 to -28 to +28

        # Technical (23% weight)
        tech_strength = technical_data.get("signals", {}).get("strength", 0)
        score += tech_strength * 0.23  # -23 to +23

        # Sentiment (23% weight)
        sentiment_score = sentiment_data.get("overall_sentiment", 0)
        score += sentiment_score * 23  # -23 to +23

        # Market trend (18% weight)
        trend = market_data.get("trend", "sideways")
        if "uptrend" in trend:
            score += 18
        elif "downtrend" in trend:
            score -= 18

        # Macro environment (8% weight) - if available
        if macro_data:
            yield_status = macro_data.get("yield_curve", {}).get("status", "")
            cycle = macro_data.get("economic_cycle", "")
            if yield_status == "normal" and cycle == "expansion":
                score += 8
            elif yield_status == "inverted" or cycle == "contraction":
                score -= 8

        # Options flow (up to 8% weight) - if available
        if options_data:
            options_signal = options_data.get("overall_signal", "neutral")
            if options_signal == "bullish":
                score += 8
            elif options_signal == "bearish":
                score -= 8

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
