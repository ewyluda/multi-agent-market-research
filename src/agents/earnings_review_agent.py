"""Earnings review agent — structured earnings digest with deterministic beat/miss and sector KPIs."""

import asyncio
import json
import re
from typing import Dict, Any, List, Optional, Tuple

import anthropic
from openai import OpenAI

from .base_agent import BaseAgent

# ─── Sector KPI Templates ───────────────────────────────────────────────────

SECTOR_KPI_TEMPLATES = {
    "Technology": ["Revenue Growth", "Gross Margin", "Operating Margin", "R&D % of Revenue",
                   "Free Cash Flow", "Customer Count", "ARR", "Net Revenue Retention"],
    "Financial Services": ["Net Interest Margin", "Provision Ratio", "Loan Growth",
                           "CET1 Ratio", "ROE", "Efficiency Ratio", "Net Charge-offs"],
    "Consumer Cyclical": ["Same-Store Sales", "E-commerce Mix", "Inventory Turns",
                          "Gross Margin", "Average Transaction Value", "Store Count"],
    "Healthcare": ["Revenue Growth", "Pipeline Updates", "R&D Spend", "Gross Margin",
                   "Patient Volume", "Reimbursement Rates"],
    "Industrials": ["Book-to-Bill Ratio", "Backlog", "Utilization Rate", "Organic Growth",
                    "Margin Expansion", "Free Cash Flow Conversion"],
    "Communication Services": ["Subscriber Growth", "ARPU", "Churn Rate", "Content Spend",
                               "Ad Revenue Growth", "Engagement Metrics"],
    "Semiconductors": ["Book-to-Bill", "ASPs", "Utilization", "Design Wins",
                       "Inventory Days", "Gross Margin"],
}

DEFAULT_KPI_TEMPLATE = ["Revenue Growth", "Gross Margin", "Operating Margin",
                        "Free Cash Flow", "Debt/EBITDA", "Capex"]

# ─── Completeness Weights ────────────────────────────────────────────────────

_COMPLETENESS_WEIGHTS = {
    "earnings": 0.50,
    "fundamentals": 0.30,
    "market": 0.20,
}


class EarningsReviewAgent(BaseAgent):
    """Agent that produces structured earnings call digests.

    Deterministic beat/miss from EPS history + single-pass LLM for
    exec summary, KPI extraction, guidance deltas, quotes, thesis impact.

    Runs in the synthesis phase, parallel with SolutionAgent and ThesisAgent.
    """

    def __init__(self, ticker: str, config: Dict[str, Any], agent_results: Dict[str, Any]):
        super().__init__(ticker, config)
        self.agent_results = agent_results

    async def fetch_data(self) -> Dict[str, Any]:
        return self.agent_results

    async def analyze(self, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        earnings_data = self._get_agent_data("earnings")
        completeness = self._compute_data_completeness()
        sources = self._get_available_sources()

        # Deterministic beat/miss (always computed if EPS data exists)
        beat_miss = self._compute_beat_miss()
        sector_template_name = self._get_sector_template_name()

        # Check if we have enough data for LLM analysis
        has_transcript = self._has_transcript_data()
        if not has_transcript:
            return self._partial_result(beat_miss, sector_template_name, completeness, sources)

        if not earnings_data:
            return self._empty_result(sources)

        # Single-pass LLM for structured extraction
        try:
            prompt = self._build_prompt()
            llm_response = await self._call_llm(prompt)
            parsed = self._parse_llm_response(llm_response)
        except Exception as e:
            self.logger.warning(f"Earnings review LLM failed for {self.ticker}: {e}")
            return self._partial_result(beat_miss, sector_template_name, completeness, sources)

        result = {
            "executive_summary": parsed.get("executive_summary", ""),
            "beat_miss": beat_miss,
            "guidance_deltas": parsed.get("guidance_deltas", []),
            "kpi_table": parsed.get("kpi_table", []),
            "management_tone": parsed.get("management_tone", "neutral"),
            "notable_quotes": parsed.get("notable_quotes", []),
            "thesis_impact": parsed.get("thesis_impact", ""),
            "one_offs": parsed.get("one_offs", []),
            "sector_template": sector_template_name,
        }

        # Guardrails will be added in Task 3 (validate_earnings_review_output)
        result["data_completeness"] = completeness
        result["data_sources_used"] = sources
        return result

    # ─── Deterministic Computation ───────────────────────────────────────────

    def _compute_beat_miss(self) -> List[Dict[str, Any]]:
        """Compute deterministic beat/miss from EPS history."""
        earnings_data = self._get_agent_data("earnings")
        if not earnings_data:
            return []

        results = []
        eps_history = earnings_data.get("eps_history", [])
        if eps_history:
            latest = eps_history[0]
            actual = latest.get("actual")
            estimate = latest.get("estimate")
            surprise_pct = latest.get("surprise_pct")
            if actual is not None and estimate is not None:
                if surprise_pct is None:
                    surprise_pct = ((actual - estimate) / abs(estimate) * 100) if estimate != 0 else 0.0
                    surprise_pct = round(surprise_pct, 2)
                verdict = "beat" if surprise_pct > 1.0 else "miss" if surprise_pct < -1.0 else "inline"
                results.append({
                    "metric": "EPS",
                    "actual": actual,
                    "estimate": estimate,
                    "surprise_pct": surprise_pct,
                    "verdict": verdict,
                })
        return results

    def _get_sector_template(self) -> List[str]:
        """Get sector-specific KPI template."""
        fund_data = self._get_agent_data("fundamentals")
        if not fund_data:
            return DEFAULT_KPI_TEMPLATE
        sector = fund_data.get("sector", "")
        return SECTOR_KPI_TEMPLATES.get(sector, DEFAULT_KPI_TEMPLATE)

    def _get_sector_template_name(self) -> str:
        """Get the name of the sector template being used."""
        fund_data = self._get_agent_data("fundamentals")
        if not fund_data:
            return "default"
        sector = fund_data.get("sector", "")
        return sector if sector in SECTOR_KPI_TEMPLATES else "default"

    def _has_transcript_data(self) -> bool:
        """Check if meaningful transcript analysis is available."""
        earnings_data = self._get_agent_data("earnings")
        if not earnings_data:
            return False
        # If highlights are empty and analysis says "No earnings call transcripts", no transcript
        highlights = earnings_data.get("highlights", [])
        data_source = earnings_data.get("data_source", "")
        return len(highlights) > 0 and data_source != "none"

    # ─── Data Completeness ───────────────────────────────────────────────────

    def _compute_data_completeness(self) -> float:
        """Compute deterministic data completeness score (0.0-1.0)."""
        score = 0.0
        for agent_name, weight in _COMPLETENESS_WEIGHTS.items():
            result = self.agent_results.get(agent_name, {})
            if not (isinstance(result, dict) and result.get("success") and result.get("data")):
                continue
            if agent_name == "earnings":
                # Partial credit if EPS only (no transcript)
                if self._has_transcript_data():
                    score += weight  # Full 0.50
                else:
                    score += 0.15  # Partial credit
            else:
                score += weight
        return round(score, 2)

    def _get_available_sources(self) -> List[str]:
        """Get list of agents that have data."""
        sources = []
        for agent_name in _COMPLETENESS_WEIGHTS:
            result = self.agent_results.get(agent_name, {})
            if isinstance(result, dict) and result.get("success") and result.get("data"):
                sources.append(agent_name)
        return sources

    def _get_agent_data(self, agent_name: str) -> Optional[Dict[str, Any]]:
        """Safely extract data dict from an agent result."""
        result = self.agent_results.get(agent_name, {})
        if isinstance(result, dict) and result.get("success"):
            return result.get("data")
        return None

    # ─── LLM Prompt ──────────────────────────────────────────────────────────

    def _build_prompt(self) -> str:
        """Build the single-pass LLM prompt for earnings review extraction."""
        earnings_data = self._get_agent_data("earnings") or {}
        fund_data = self._get_agent_data("fundamentals") or {}
        market_data = self._get_agent_data("market") or {}

        sector_template = self._get_sector_template()
        template_str = ", ".join(sector_template)

        # Format earnings context
        highlights = earnings_data.get("highlights", [])
        highlights_str = "\n".join(
            f"  [{h.get('tag', '?')}] {h.get('text', '')}" for h in highlights[:6]
        ) or "  No highlights available."

        guidance = earnings_data.get("guidance", [])
        guidance_str = "\n".join(
            f"  {g.get('metric', '?')}: {g.get('prior', '?')} -> {g.get('current', '?')} ({g.get('direction', '?')})"
            for g in guidance[:5]
        ) or "  No guidance data."

        qa = earnings_data.get("qa_highlights", [])
        qa_str = "\n".join(
            f"  {q.get('analyst', '?')} ({q.get('firm', '?')}): {q.get('topic', '?')}\n    Q: {q.get('question', '')}\n    A: {q.get('answer', '')}"
            for q in qa[:4]
        ) or "  No Q&A highlights."

        tone = earnings_data.get("tone_analysis", {})
        tone_str = ", ".join(f"{k}: {v}" for k, v in tone.items()) if tone else "N/A"

        eps_history = earnings_data.get("eps_history", [])[:4]
        eps_str = " | ".join(
            f"{e.get('quarter', '?')}: ${e.get('actual', '?')} vs ${e.get('estimate', '?')} ({e.get('surprise_pct', 0):+.1f}%)"
            for e in eps_history
        ) or "N/A"

        analysis = earnings_data.get("analysis", "")

        # Format fundamentals context
        company = fund_data.get("company_name", self.ticker)
        sector = fund_data.get("sector", "N/A")
        revenue = fund_data.get("revenue")
        rev_str = f"${revenue / 1e9:.1f}B" if revenue else "N/A"
        margin = fund_data.get("gross_margin")
        margin_str = f"{margin * 100:.1f}%" if margin is not None else "N/A"

        # Format market context
        price = market_data.get("current_price", "N/A")
        high52 = market_data.get("high_52w", "N/A")
        low52 = market_data.get("low_52w", "N/A")
        chg1m = market_data.get("price_change_1m")
        chg_str = f"{chg1m * 100:+.1f}%" if chg1m is not None else "N/A"

        return f"""You are a senior equity research analyst writing a structured earnings review for {self.ticker} ({company}).

Produce a structured digest of this earnings call. Return a JSON object with EXACTLY these keys — no markdown, no explanation, just raw JSON:

{{
  "executive_summary": "3-5 sentence summary of the key takeaways from this earnings call",
  "guidance_deltas": [
    {{"metric": "Revenue|EPS|Gross Margin|...", "prior_value": "prior guidance or N/A", "new_value": "new guidance", "direction": "raised|lowered|maintained|introduced|withdrawn"}}
  ],
  "kpi_table": [
    {{"metric": "KPI name", "value": "current value", "prior_value": "prior quarter or null", "yoy_change": "YoY change or null", "source": "reported|call_disclosed|calculated"}}
  ],
  "management_tone": "confident|cautious|defensive|evasive|optimistic",
  "notable_quotes": ["2-3 short, impactful management quotes"],
  "thesis_impact": "1-2 sentences on how this quarter affects the investment thesis",
  "one_offs": ["Non-recurring items that distort reported results"]
}}

Rules:
- kpi_table: Prioritize these sector-specific metrics: [{template_str}]. Also include any additional KPIs disclosed on the call that are NOT in this list.
- kpi_table source field: "reported" = in financial statements, "call_disclosed" = mentioned only on the call, "calculated" = you derived it.
- guidance_deltas: Extract all forward guidance changes. Compare to prior quarter guidance if available.
- notable_quotes: Short (1-2 sentences), direct quotes from management that are most investment-relevant.
- one_offs: Only include items that are genuinely non-recurring and material.
- thesis_impact: Be specific about what changed for the investment thesis — don't just restate the summary.

--- COMPANY ---
{company} | Sector: {sector} | Revenue: {rev_str} | Gross Margin: {margin_str}
Price: ${price} | 52w: ${low52}-${high52} | 1M Change: {chg_str}

--- EARNINGS HIGHLIGHTS ---
{highlights_str}

--- GUIDANCE ---
{guidance_str}

--- Q&A HIGHLIGHTS ---
{qa_str}

--- TONE ANALYSIS ---
{tone_str}

--- EPS HISTORY ---
{eps_str}

--- ANALYST NARRATIVE ---
{analysis}
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
                temperature=llm_config.get("temperature", 0.3),
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
                temperature=llm_config.get("temperature", 0.3),
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

    def _empty_result(self, sources: List[str]) -> Dict[str, Any]:
        """Return empty result when no earnings data available."""
        return {
            "executive_summary": f"No earnings data available for {self.ticker}.",
            "beat_miss": [],
            "guidance_deltas": [],
            "kpi_table": [],
            "management_tone": "unknown",
            "notable_quotes": [],
            "thesis_impact": "",
            "one_offs": [],
            "sector_template": self._get_sector_template_name(),
            "data_completeness": 0.0,
            "data_sources_used": sources,
            "error": "No earnings data available.",
        }

    def _partial_result(
        self,
        beat_miss: List[Dict[str, Any]],
        sector_template_name: str,
        completeness: float,
        sources: List[str],
    ) -> Dict[str, Any]:
        """Return partial result with deterministic fields when transcript unavailable."""
        return {
            "executive_summary": f"No earnings transcript available for detailed review of {self.ticker}.",
            "beat_miss": beat_miss,
            "guidance_deltas": [],
            "kpi_table": [],
            "management_tone": "unknown",
            "notable_quotes": [],
            "thesis_impact": "",
            "one_offs": [],
            "sector_template": sector_template_name,
            "data_completeness": completeness,
            "data_sources_used": sources,
            "partial": True,
        }
