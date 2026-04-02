"""Thesis agent — two-pass LLM bull/bear investment debate engine."""

import asyncio
import json
import re
import logging
from typing import Dict, Any, List, Optional, Tuple

import anthropic
from openai import OpenAI

from .base_agent import BaseAgent

# Weights for data completeness scoring (sum to 1.0)
_COMPLETENESS_WEIGHTS = {
    "fundamentals": 0.30,
    "news": 0.15,
    "earnings": 0.20,
    "leadership": 0.10,
    "market": 0.10,
    "technical": 0.05,
    "macro": 0.05,
    "options": 0.05,
}


class ThesisAgent(BaseAgent):
    """Agent that generates structured bull/bear investment debates.

    Two-pass LLM approach:
        Pass 1 ("The Analyst"): Extracts key investment facts from tiered agent data.
        Pass 2 ("The Debater"): Generates structured bull/bear thesis from extracted facts.

    Runs in the synthesis phase, parallel with SolutionAgent.
    """

    def __init__(self, ticker: str, config: Dict[str, Any], agent_results: Dict[str, Any]):
        super().__init__(ticker, config)
        self.agent_results = agent_results

    async def fetch_data(self) -> Dict[str, Any]:
        return self.agent_results

    async def analyze(self, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        # Check data gate
        gate_passes, sources = self._check_data_gate()
        if not gate_passes:
            self.logger.warning(f"Thesis data gate failed for {self.ticker} — insufficient data")
            return self._empty_result(sources)

        completeness = self._compute_data_completeness()
        rich_context, key_metrics = self._extract_tiered_data()

        # Pass 1: Extract facts
        try:
            pass1_prompt = self._build_pass1_prompt(rich_context, key_metrics)
            pass1_response = await self._call_llm(pass1_prompt)
            extracted_facts = self._parse_llm_response(pass1_response)
        except Exception as e:
            self.logger.warning(f"Thesis Pass 1 failed for {self.ticker}: {e}")
            return self._empty_result(sources, completeness)

        # Pass 2: Generate debate
        try:
            pass2_prompt = self._build_pass2_prompt(extracted_facts)
            pass2_response = await self._call_llm(pass2_prompt)
            thesis_raw = self._parse_llm_response(pass2_response)
        except Exception as e:
            self.logger.warning(f"Thesis Pass 2 failed for {self.ticker}: {e}, using Pass 1 fallback")
            return self._pass1_fallback(extracted_facts, completeness, sources)

        # Attach deterministic fields (override LLM values)
        thesis_raw["data_completeness"] = completeness
        thesis_raw["data_sources_used"] = sources

        # Guardrails: evidence grounding, catalyst specificity, cross-reference
        from ..llm_guardrails import validate_thesis_output
        validated, warnings = validate_thesis_output(thesis_raw, extracted_facts, self.agent_results)
        if warnings:
            validated["guardrail_warnings"] = warnings
        return validated

    # ─── Data Gate ───────────────────────────────────────────────────────────

    def _check_data_gate(self) -> Tuple[bool, List[str]]:
        """Check minimum data requirements. Returns (passes, sources_available)."""
        sources = []
        for agent_name in _COMPLETENESS_WEIGHTS:
            result = self.agent_results.get(agent_name, {})
            if isinstance(result, dict) and result.get("success") and result.get("data"):
                sources.append(agent_name)

        # Gate: fundamentals required + at least one of news/earnings/market
        has_fundamentals = "fundamentals" in sources
        has_secondary = any(s in sources for s in ("news", "earnings", "market"))

        return (has_fundamentals and has_secondary), sources

    def _compute_data_completeness(self) -> float:
        """Compute deterministic data completeness score (0.0-1.0)."""
        score = 0.0
        for agent_name, weight in _COMPLETENESS_WEIGHTS.items():
            result = self.agent_results.get(agent_name, {})
            if isinstance(result, dict) and result.get("success") and result.get("data"):
                score += weight
        return round(score, 2)

    # ─── Tiered Data Extraction ──────────────────────────────────────────────

    def _extract_tiered_data(self) -> Tuple[str, str]:
        """Extract tiered context from agent results.

        Returns:
            (rich_context, key_metrics) — both as formatted strings for the LLM prompt.
        """
        rich_parts = []
        metric_parts = []

        # Rich: Fundamentals
        fund_data = self._get_agent_data("fundamentals")
        if fund_data:
            rich_parts.append(self._format_fundamentals(fund_data))

        # Rich: News
        news_data = self._get_agent_data("news")
        if news_data:
            rich_parts.append(self._format_news(news_data))

        # Rich: Earnings
        earnings_data = self._get_agent_data("earnings")
        if earnings_data:
            rich_parts.append(self._format_earnings(earnings_data))

        # Rich: Leadership
        leadership_data = self._get_agent_data("leadership")
        if leadership_data:
            rich_parts.append(self._format_leadership(leadership_data))

        # Key metrics: Technical
        tech_data = self._get_agent_data("technical")
        if tech_data:
            metric_parts.append(self._format_technical_metrics(tech_data))

        # Key metrics: Macro
        macro_data = self._get_agent_data("macro")
        if macro_data:
            metric_parts.append(self._format_macro_metrics(macro_data))

        # Key metrics: Options
        options_data = self._get_agent_data("options")
        if options_data:
            metric_parts.append(self._format_options_metrics(options_data))

        # Key metrics: Market
        market_data = self._get_agent_data("market")
        if market_data:
            metric_parts.append(self._format_market_metrics(market_data))

        return "\n\n".join(rich_parts), "\n\n".join(metric_parts)

    def _get_agent_data(self, agent_name: str) -> Optional[Dict[str, Any]]:
        """Safely extract data dict from an agent result."""
        result = self.agent_results.get(agent_name, {})
        if isinstance(result, dict) and result.get("success"):
            return result.get("data")
        return None

    @staticmethod
    def _format_fundamentals(data: Dict[str, Any]) -> str:
        name = data.get("company_name", "Unknown")
        sector = data.get("sector", "N/A")
        mcap = data.get("market_cap")
        mcap_str = f"${mcap / 1e9:.1f}B" if mcap else "N/A"
        revenue = data.get("revenue")
        rev_str = f"${revenue / 1e9:.1f}B" if revenue else "N/A"
        rev_growth = data.get("revenue_growth")
        rev_growth_str = f"{rev_growth * 100:.1f}%" if rev_growth is not None else "N/A"
        margin = data.get("gross_margin")
        margin_str = f"{margin * 100:.1f}%" if margin is not None else "N/A"
        pe = data.get("pe_ratio", "N/A")
        dte = data.get("debt_to_equity", "N/A")
        desc = data.get("business_description", "")
        estimates = data.get("analyst_estimates", {})
        target_mean = estimates.get("target_mean", "N/A")
        target_high = estimates.get("target_high", "N/A")
        insiders = data.get("insider_trading", [])
        insider_str = ""
        if insiders:
            lines = []
            for t in insiders[:3]:
                lines.append(f"  - {t.get('owner_name', '?')}: {t.get('transaction_type', '?')} {t.get('shares', '?')} shares")
            insider_str = "\nRecent Insider Trading:\n" + "\n".join(lines)

        return f"""FUNDAMENTALS — {name}
Sector: {sector} | Market Cap: {mcap_str}
Revenue: {rev_str} (Growth: {rev_growth_str}) | Gross Margin: {margin_str}
P/E: {pe} | Debt/Equity: {dte}
Analyst Targets: Mean ${target_mean}, High ${target_high}
Business: {desc}{insider_str}"""

    @staticmethod
    def _format_news(data: Dict[str, Any]) -> str:
        articles = data.get("articles", [])[:5]
        sentiment = data.get("news_sentiment", "N/A")
        lines = [f"NEWS (Overall Sentiment: {sentiment})"]
        for a in articles:
            lines.append(f"  - {a.get('title', 'Untitled')}: {a.get('summary', '')}")
        return "\n".join(lines)

    @staticmethod
    def _format_earnings(data: Dict[str, Any]) -> str:
        tone = data.get("tone", "N/A")
        direction = data.get("guidance_direction", "N/A")
        lines = [f"EARNINGS (Tone: {tone}, Guidance: {direction})"]
        for h in data.get("highlights", [])[:4]:
            lines.append(f"  [{h.get('tag', '?')}] {h.get('text', '')}")
        for g in data.get("guidance", [])[:3]:
            lines.append(f"  Guidance — {g.get('metric', '?')}: {g.get('prior', '?')} → {g.get('current', '?')} ({g.get('direction', '?')})")
        for qa in data.get("qa_highlights", [])[:2]:
            lines.append(f"  Q&A — {qa.get('analyst', '?')} ({qa.get('firm', '?')}): {qa.get('topic', '?')}")
        eps = data.get("eps_history", [])[:4]
        if eps:
            eps_strs = [f"{e['quarter']}: ${e['actual']} vs ${e['estimate']} ({e['surprise_pct']:+.1f}%)" for e in eps if 'quarter' in e]
            if eps_strs:
                lines.append(f"  EPS History: {' | '.join(eps_strs)}")
        return "\n".join(lines)

    @staticmethod
    def _format_leadership(data: Dict[str, Any]) -> str:
        score = data.get("overall_score", "N/A")
        grade = data.get("grade", "N/A")
        summary = data.get("executive_summary", "N/A")
        flags = data.get("red_flags", [])
        lines = [f"LEADERSHIP (Score: {score}, Grade: {grade})", f"  {summary}"]
        if flags:
            for f in flags[:3]:
                desc = f.get("description", str(f)) if isinstance(f, dict) else str(f)
                lines.append(f"  Red Flag: {desc}")
        return "\n".join(lines)

    @staticmethod
    def _format_technical_metrics(data: Dict[str, Any]) -> str:
        rsi = data.get("rsi", "N/A")
        macd = data.get("macd_signal", "N/A")
        sma50 = data.get("sma_50", "N/A")
        sma200 = data.get("sma_200", "N/A")
        support = data.get("support", "N/A")
        resistance = data.get("resistance", "N/A")
        return f"TECHNICAL: RSI {rsi} | MACD {macd} | 50-SMA ${sma50} | 200-SMA ${sma200} | Support ${support} | Resistance ${resistance}"

    @staticmethod
    def _format_macro_metrics(data: Dict[str, Any]) -> str:
        return (
            f"MACRO: Fed Funds {data.get('fed_funds_rate', 'N/A')}% | "
            f"CPI {data.get('cpi_yoy', 'N/A')}% | "
            f"GDP {data.get('gdp_growth', 'N/A')}% | "
            f"Unemployment {data.get('unemployment_rate', 'N/A')}% | "
            f"Yield Spread {data.get('yield_curve_spread', 'N/A')}"
        )

    @staticmethod
    def _format_options_metrics(data: Dict[str, Any]) -> str:
        pcr = data.get("put_call_ratio", "N/A")
        iv = data.get("iv_percentile", "N/A")
        unusual = data.get("unusual_activity", [])
        unusual_str = f" | Unusual: {len(unusual)} signals" if unusual else ""
        return f"OPTIONS: Put/Call {pcr} | IV Percentile {iv}%{unusual_str}"

    @staticmethod
    def _format_market_metrics(data: Dict[str, Any]) -> str:
        price = data.get("current_price", "N/A")
        high = data.get("high_52w", "N/A")
        low = data.get("low_52w", "N/A")
        vol = data.get("avg_volume")
        vol_str = f"{vol / 1e6:.1f}M" if vol else "N/A"
        chg1m = data.get("price_change_1m")
        chg1m_str = f"{chg1m * 100:+.1f}%" if chg1m is not None else "N/A"
        chg3m = data.get("price_change_3m")
        chg3m_str = f"{chg3m * 100:+.1f}%" if chg3m is not None else "N/A"
        return f"MARKET: Price ${price} | 52w High ${high} / Low ${low} | Vol {vol_str} | 1M {chg1m_str} | 3M {chg3m_str}"

    # ─── LLM Prompts ────────────────────────────────────────────────────────

    def _build_pass1_prompt(self, rich_context: str, key_metrics: str) -> str:
        """Build the Pass 1 fact extraction prompt."""
        return f"""You are a senior equity research analyst. Extract the key investment-relevant facts from this data for {self.ticker}.

IMPORTANT RULES:
- Only extract facts that appear in the provided data. Do NOT infer metrics not present.
- If a data point seems contradictory (e.g., revenue growth positive but guidance lowered), flag the contradiction explicitly rather than resolving it.
- Be specific — cite numbers, not vague claims.

Return a JSON object with EXACTLY these keys — no markdown, no explanation, just raw JSON:

{{
  "company_context": "2-3 sentence business summary with sector and scale",
  "key_financials": ["5-8 most important financial data points with numbers"],
  "recent_developments": ["3-5 material recent events or news items"],
  "management_signals": ["3-5 signals from earnings calls or leadership assessment"],
  "macro_technical_context": ["2-4 relevant macro or technical factors"],
  "potential_tensions": ["4-8 areas where reasonable investors could disagree — phrase each as a debatable question"]
}}

--- COMPANY DATA ---

{rich_context}

--- KEY METRICS ---

{key_metrics}
"""

    def _build_pass2_prompt(self, extracted_facts: Dict[str, Any]) -> str:
        """Build the Pass 2 debate generation prompt."""
        facts_json = json.dumps(extracted_facts, indent=2)
        return f"""You are a buy-side portfolio manager preparing a structured investment debate for {self.ticker}.

Given the extracted facts below, construct a bull/bear thesis. Rules:

1. Every evidence item MUST trace to a fact from the extraction. Do not introduce new data points.
2. If bull and bear views on a tension point don't actually conflict, discard that point — only include genuine disagreements.
3. Tension points should be specific to this company, not generic market concerns.
4. Management questions should reference specific tensions — not boilerplate.
5. Adapt the number of tension points and questions to how much is genuinely debatable (minimum 3 tension points, maximum 8).

Return a JSON object with EXACTLY these keys — no markdown, no explanation, just raw JSON:

{{
  "bull_case": {{
    "thesis": "2-3 sentence core bull thesis",
    "key_drivers": ["3-5 primary bull drivers"],
    "catalysts": ["2-4 near-term bull catalysts"]
  }},
  "bear_case": {{
    "thesis": "2-3 sentence core bear thesis",
    "key_drivers": ["3-5 primary bear drivers"],
    "catalysts": ["2-4 near-term bear catalysts"]
  }},
  "tension_points": [
    {{
      "topic": "Short descriptive label",
      "bull_view": "Bull argument with evidence (2-3 sentences)",
      "bear_view": "Bear counter-argument with evidence (2-3 sentences)",
      "evidence": ["2-4 data points from the extraction supporting this debate"],
      "resolution_catalyst": "Specific event or data point that would settle this"
    }}
  ],
  "management_questions": [
    {{
      "role": "CEO or CFO",
      "question": "The specific question",
      "context": "Why this matters for the investment thesis"
    }}
  ],
  "thesis_summary": "One paragraph synthesizing the overall investment debate — what is the core disagreement and what would resolve it?"
}}

--- EXTRACTED FACTS ---

{facts_json}
"""

    # ─── LLM Call ────────────────────────────────────────────────────────────

    async def _call_llm(self, prompt: str) -> str:
        """Call the configured LLM provider."""
        llm_config = self.config.get("llm_config", {})
        provider = llm_config.get("provider", "anthropic")
        if provider == "anthropic":
            return await self._call_anthropic(prompt, llm_config)
        elif provider in ("openai", "xai"):
            return await self._call_openai(prompt, llm_config)
        else:
            raise ValueError(f"Unsupported LLM provider: {provider!r}")

    async def _call_anthropic(self, prompt: str, llm_config: Dict[str, Any]) -> str:
        api_key = llm_config.get("api_key")
        if not api_key:
            raise ValueError("No Anthropic API key configured")
        client = anthropic.Anthropic(api_key=api_key)

        def _call():
            return client.messages.create(
                model=llm_config.get("model", "claude-3-5-sonnet-20241022"),
                max_tokens=llm_config.get("max_tokens", 4096),
                temperature=llm_config.get("temperature", 0.4),
                messages=[{"role": "user", "content": prompt}],
            )

        message = await asyncio.to_thread(_call)
        return message.content[0].text.strip()

    async def _call_openai(self, prompt: str, llm_config: Dict[str, Any]) -> str:
        api_key = llm_config.get("api_key")
        if not api_key:
            raise ValueError("No API key configured")
        kwargs = {}
        base_url = llm_config.get("base_url")
        if base_url:
            kwargs["base_url"] = base_url
        client = OpenAI(api_key=api_key, **kwargs)

        def _call():
            return client.chat.completions.create(
                model=llm_config.get("model", "gpt-4o"),
                max_tokens=llm_config.get("max_tokens", 4096),
                temperature=llm_config.get("temperature", 0.4),
                messages=[{"role": "user", "content": prompt}],
            )

        response = await asyncio.to_thread(_call)
        return response.choices[0].message.content.strip()

    # ─── Response Parsing ────────────────────────────────────────────────────

    @staticmethod
    def _parse_llm_response(raw: str) -> Dict[str, Any]:
        """Parse LLM JSON response, stripping markdown fences if present."""
        text = raw.strip()
        if text.startswith("```"):
            text = re.sub(r"^```(?:json)?\s*\n?", "", text)
            text = re.sub(r"\n?```\s*$", "", text)
        return json.loads(text)

    # ─── Fallback Results ────────────────────────────────────────────────────

    def _empty_result(self, sources: List[str], completeness: float = 0.0) -> Dict[str, Any]:
        """Return empty result when data gate fails or Pass 1 errors."""
        return {
            "bull_case": {"thesis": "", "key_drivers": [], "catalysts": []},
            "bear_case": {"thesis": "", "key_drivers": [], "catalysts": []},
            "tension_points": [],
            "management_questions": [],
            "thesis_summary": f"Insufficient data to generate investment thesis for {self.ticker}.",
            "data_completeness": completeness,
            "data_sources_used": sources,
            "error": "Data gate failed — fundamentals required plus at least one of: news, earnings, market.",
        }

    def _pass1_fallback(
        self,
        extracted_facts: Dict[str, Any],
        completeness: float,
        sources: List[str],
    ) -> Dict[str, Any]:
        """Fallback when Pass 2 fails — surface extracted facts directly."""
        tensions = extracted_facts.get("potential_tensions", [])
        tension_points = [
            {
                "topic": t if isinstance(t, str) else str(t),
                "bull_view": "",
                "bear_view": "",
                "evidence": [],
                "resolution_catalyst": "",
            }
            for t in tensions[:8]
        ]
        return {
            "bull_case": {"thesis": "", "key_drivers": extracted_facts.get("key_financials", [])[:3], "catalysts": []},
            "bear_case": {"thesis": "", "key_drivers": [], "catalysts": []},
            "tension_points": tension_points,
            "management_questions": [],
            "thesis_summary": f"Partial analysis for {self.ticker} — fact extraction succeeded but debate generation failed.",
            "data_completeness": completeness,
            "data_sources_used": sources,
            "extracted_facts": extracted_facts,
            "pass2_failed": True,
        }
