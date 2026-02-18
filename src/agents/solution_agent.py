"""Solution agent for synthesizing all agent outputs into final recommendation."""

import asyncio
import anthropic
from openai import OpenAI
import json
from typing import Dict, Any, Optional
from .base_agent import BaseAgent


class SolutionAgent(BaseAgent):
    """Agent that synthesizes all agent outputs into structured recommendations."""

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
        self.calibration_context: Optional[Dict[str, Any]] = None

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

        # Use LLM for synthesis
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

    def _build_prompt(
        self,
        news_data: Dict[str, Any],
        sentiment_data: Dict[str, Any],
        fundamentals_data: Dict[str, Any],
        market_data: Dict[str, Any],
        technical_data: Dict[str, Any],
        macro_data: Dict[str, Any],
        options_data: Dict[str, Any],
    ) -> str:
        """
        Build the synthesis prompt from agent data.

        Centralizes prompt construction so both Anthropic and OpenAI paths
        use the same text.  When ``calibration_context`` is set, a
        HISTORICAL ACCURACY section is appended to ground confidence in the
        model's track record.

        Returns:
            The full prompt string.
        """
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

Using first-principles reasoning:

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
  "reasoning": "<concise rationale summary (max 3 sentences)>",
  "rationale_summary": "<one concise paragraph no longer than 400 chars>",
  "risks": ["<risk1>", "<risk2>", "<risk3>"],
  "opportunities": ["<opportunity1>", "<opportunity2>", "<opportunity3>"],
  "price_targets": {{
    "entry": <suggested entry price>,
    "target": <price target>,
    "stop_loss": <stop loss price>
  }},
  "position_size": "<SMALL|MEDIUM|LARGE>",
  "time_horizon": "<SHORT_TERM|MEDIUM_TERM|LONG_TERM>",
  "scenarios": {{
    "bull": {{"probability": <0..1>, "expected_return_pct": <number|null>, "thesis": "<short thesis>"}},
    "base": {{"probability": <0..1>, "expected_return_pct": <number|null>, "thesis": "<short thesis>"}},
    "bear": {{"probability": <0..1>, "expected_return_pct": <number|null>, "thesis": "<short thesis>"}}
  }},
  "scenario_summary": "<one sentence summary of scenario mix>"
}}"""

        # Append calibration context if available
        if self.calibration_context:
            prompt += "\n## HISTORICAL ACCURACY (Your Track Record)\n"
            for horizon, data in sorted(self.calibration_context.items()):
                if isinstance(data, dict):
                    hit_rate = data.get("hit_rate")
                    sample_size = data.get("sample_size", 0)
                    if hit_rate is not None:
                        prompt += f"- {horizon} horizon: {hit_rate:.0%} accuracy ({sample_size} samples)\n"
            prompt += (
                "\nAdjust your confidence level to reflect this track record. "
                "If historical accuracy at this confidence band is low, lower your confidence accordingly.\n"
            )

        return prompt

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
        Use LLM for synthesis.

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
        prompt = self._build_prompt(
            news_data, sentiment_data, fundamentals_data,
            market_data, technical_data, macro_data, options_data,
        )

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
            return self._normalize_synthesis_result(result, market_data)

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
        prompt = self._build_prompt(
            news_data, sentiment_data, fundamentals_data,
            market_data, technical_data, macro_data, options_data,
        )

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
            return self._normalize_synthesis_result(result, market_data)

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

        result = {
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
            "summary": f"Recommendation: {recommendation} (Score: {int(score)})",
        }
        return self._normalize_synthesis_result(result, market_data)

    def _to_float(self, value: Any) -> Optional[float]:
        """Best-effort numeric conversion."""
        if value is None:
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    def _build_decision_card(self, result: Dict[str, Any], market_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Build a normalized, machine-readable decision card.

        If the LLM already produced `decision_card`, preserve provided fields and
        fill any missing values from core synthesis fields.
        """
        recommendation = str(result.get("recommendation", "HOLD")).upper()
        action_map = {"BUY": "buy", "HOLD": "hold", "SELL": "avoid"}
        action = action_map.get(recommendation, "hold")

        price_targets = result.get("price_targets") or {}
        entry = self._to_float(price_targets.get("entry")) or self._to_float(market_data.get("current_price"))
        target = self._to_float(price_targets.get("target"))
        stop_loss = self._to_float(price_targets.get("stop_loss"))
        confidence = self._to_float(result.get("confidence"))
        time_horizon = result.get("time_horizon")
        position_size = (result.get("position_size") or "").upper()

        entry_zone = None
        if entry is not None:
            entry_zone = {
                "low": round(entry * 0.98, 2),
                "high": round(entry * 1.02, 2),
                "reference": round(entry, 2),
            }

        targets = [round(target, 2)] if target is not None else []

        sizing_map = {
            "SMALL": "Use reduced size (about 0.5x normal risk).",
            "MEDIUM": "Use standard size (about 1.0x normal risk).",
            "LARGE": "Use increased size only if risk limits allow (about 1.5x normal risk).",
        }
        position_sizing_hint = sizing_map.get(position_size, "Size position according to your risk budget.")

        invalidation_conditions = result.get("invalidation_conditions")
        if not invalidation_conditions:
            risks = result.get("risks") or []
            invalidation_conditions = risks[:3] if risks else ["Risk/reward no longer supports the thesis."]

        base_card = {
            "action": action,
            "entry_zone": entry_zone,
            "stop_loss": round(stop_loss, 2) if stop_loss is not None else None,
            "targets": targets,
            "time_horizon": time_horizon,
            "confidence": confidence,
            "invalidation_conditions": invalidation_conditions,
            "position_sizing_hint": position_sizing_hint,
        }

        existing = result.get("decision_card") if isinstance(result.get("decision_card"), dict) else {}
        merged = {**base_card, **existing}
        merged.setdefault("targets", targets)
        merged.setdefault("invalidation_conditions", invalidation_conditions)
        return merged

    def _default_scenarios(self, recommendation: str, score: int) -> Dict[str, Dict[str, Any]]:
        """Generate baseline scenarios when the model response omits/invalidates them."""
        rec = str(recommendation or "HOLD").upper()
        score_val = self._to_float(score) or 0.0

        if rec == "BUY":
            probs = {"bull": 0.45, "base": 0.35, "bear": 0.20}
            base_return = max(2.0, round(score_val * 0.15, 2))
        elif rec == "SELL":
            probs = {"bull": 0.20, "base": 0.35, "bear": 0.45}
            base_return = min(-2.0, round(score_val * 0.15, 2))
        else:
            probs = {"bull": 0.30, "base": 0.45, "bear": 0.25}
            base_return = round(score_val * 0.08, 2)

        bull_return = round(base_return + 8.0, 2)
        bear_return = round(base_return - 10.0, 2)

        return {
            "bull": {
                "probability": probs["bull"],
                "expected_return_pct": bull_return,
                "thesis": "Upside catalysts exceed expectations and momentum broadens.",
            },
            "base": {
                "probability": probs["base"],
                "expected_return_pct": base_return,
                "thesis": "Current trend continues with mixed positive and negative signals.",
            },
            "bear": {
                "probability": probs["bear"],
                "expected_return_pct": bear_return,
                "thesis": "Downside risks dominate and execution or macro pressure increases.",
            },
        }

    def _build_scenario_summary(self, scenarios: Dict[str, Dict[str, Any]]) -> str:
        """Create one-line scenario framing for UI fallback display."""
        labels = [("bull", "Bull"), ("base", "Base"), ("bear", "Bear")]
        parts = []
        for key, label in labels:
            block = scenarios.get(key, {})
            probability = self._to_float(block.get("probability"))
            expected_return = self._to_float(block.get("expected_return_pct"))

            prob_text = f"{(probability or 0.0) * 100:.0f}%"
            ret_text = "n/a" if expected_return is None else f"{expected_return:+.1f}%"
            parts.append(f"{label} {prob_text} ({ret_text})")

        return "; ".join(parts) + "."

    def _normalize_scenarios(self, result: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
        """Normalize bull/base/bear scenario structure and probabilities."""
        scenario_order = ["bull", "base", "bear"]
        defaults = self._default_scenarios(result.get("recommendation"), result.get("score"))
        raw_scenarios = result.get("scenarios") if isinstance(result.get("scenarios"), dict) else {}

        normalized: Dict[str, Dict[str, Any]] = {}
        probabilities = []
        for scenario_name in scenario_order:
            default_block = defaults[scenario_name]
            raw_block = raw_scenarios.get(scenario_name) if isinstance(raw_scenarios.get(scenario_name), dict) else {}

            probability = self._to_float(raw_block.get("probability"))
            if probability is None:
                probability = default_block["probability"]
            probability = max(0.0, min(1.0, float(probability)))
            probabilities.append(probability)

            expected_return = self._to_float(raw_block.get("expected_return_pct"))
            if expected_return is not None:
                expected_return = round(expected_return, 2)

            thesis = raw_block.get("thesis")
            if not isinstance(thesis, str) or not thesis.strip():
                thesis = default_block["thesis"]

            normalized[scenario_name] = {
                "probability": probability,
                "expected_return_pct": expected_return,
                "thesis": thesis.strip(),
            }

        total_probability = sum(probabilities)
        if total_probability <= 0:
            normalized = defaults
            total_probability = 1.0

        # Renormalize to target a total of 1.0 (float tolerance naturally <= 0.01).
        for scenario_name in scenario_order:
            normalized[scenario_name]["probability"] = (
                normalized[scenario_name]["probability"] / total_probability
            )

        return normalized

    def _normalize_synthesis_result(self, result: Dict[str, Any], market_data: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize synthesis payload so downstream systems get a stable schema."""
        normalized = dict(result)

        recommendation = str(normalized.get("recommendation", "HOLD")).upper()
        if recommendation not in {"BUY", "HOLD", "SELL"}:
            recommendation = "HOLD"
        normalized["recommendation"] = recommendation

        score = self._to_float(normalized.get("score"))
        normalized["score"] = int(max(-100, min(100, score if score is not None else 0)))

        confidence = self._to_float(normalized.get("confidence"))
        normalized["confidence"] = max(0.0, min(1.0, confidence if confidence is not None else 0.5))

        if not isinstance(normalized.get("risks"), list):
            normalized["risks"] = []
        if not isinstance(normalized.get("opportunities"), list):
            normalized["opportunities"] = []
        if not isinstance(normalized.get("price_targets"), dict):
            normalized["price_targets"] = {}

        scenarios = self._normalize_scenarios(normalized)
        normalized["scenarios"] = scenarios

        scenario_summary = normalized.get("scenario_summary")
        if not isinstance(scenario_summary, str) or not scenario_summary.strip():
            scenario_summary = self._build_scenario_summary(scenarios)
        normalized["scenario_summary"] = scenario_summary.strip()

        normalized["decision_card"] = self._build_decision_card(normalized, market_data)
        normalized["summary"] = self._generate_summary(normalized)

        rationale_summary = normalized.get("rationale_summary")
        if not isinstance(rationale_summary, str) or not rationale_summary.strip():
            rationale_summary = normalized.get("reasoning") or normalized.get("summary") or ""
        rationale_summary = str(rationale_summary).strip().replace("\n", " ")
        if len(rationale_summary) > 400:
            rationale_summary = rationale_summary[:399].rstrip() + "…"
        normalized["rationale_summary"] = rationale_summary

        reasoning = normalized.get("reasoning")
        if not isinstance(reasoning, str) or not reasoning.strip():
            normalized["reasoning"] = rationale_summary
        else:
            concise_reasoning = reasoning.strip().replace("\n", " ")
            if len(concise_reasoning) > 400:
                concise_reasoning = concise_reasoning[:399].rstrip() + "…"
            normalized["reasoning"] = concise_reasoning

        return normalized

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
