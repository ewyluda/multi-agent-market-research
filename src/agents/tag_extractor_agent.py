"""Tag extractor agent — lightweight LLM agent for qualitative company classification."""

import asyncio
import json
import re
from typing import Dict, Any, List, Optional

import anthropic
from openai import OpenAI

from .base_agent import BaseAgent

# ─── Tag Taxonomy ────────────────────────────────────────────────────────────

TAG_TAXONOMY = {
    "business_model": [
        "recurring_revenue", "transaction_based", "advertising_model",
        "platform_business", "hardware_dependent", "services_led",
        "subscription_transition",
    ],
    "corporate_events": [
        "activist_involved", "recent_ceo_change", "recent_cfo_change",
        "major_acquisition", "divestiture_underway", "restructuring",
        "ipo_recent", "spac_merger",
    ],
    "growth_drivers": [
        "pricing_power", "new_product_launch", "geographic_expansion",
        "market_share_gains", "cross_sell_opportunity", "ai_integration",
        "digital_transformation",
    ],
    "risk_flags": [
        "customer_concentration", "regulatory_risk", "debt_heavy",
        "margin_compression", "competitive_threat", "secular_decline",
        "accounting_concerns",
    ],
    "quality_indicators": [
        "high_insider_ownership", "consistent_buybacks", "dividend_grower",
        "strong_free_cash_flow", "high_roic", "network_effects",
        "switching_costs",
    ],
}

ALL_TAGS = {tag for tags in TAG_TAXONOMY.values() for tag in tags}
TAG_TO_CATEGORY = {tag: cat for cat, tags in TAG_TAXONOMY.items() for tag in tags}


class TagExtractorAgent(BaseAgent):
    """Lightweight agent that classifies companies with qualitative tags.

    Single LLM call with fixed taxonomy. Tags are validated against ALL_TAGS
    before returning. Runs in synthesis phase parallel with other agents.
    """

    def __init__(self, ticker: str, config: Dict[str, Any], agent_results: Dict[str, Any]):
        super().__init__(ticker, config)
        self.agent_results = agent_results

    async def fetch_data(self) -> Dict[str, Any]:
        return self.agent_results

    async def analyze(self, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        context = self._build_context()
        sources = self._get_available_sources()

        if not context.strip():
            return {"tags": [], "tags_count": 0, "data_sources_used": sources}

        try:
            prompt = self._build_prompt(context)
            llm_response = await self._call_llm(prompt)
            parsed = self._parse_llm_response(llm_response)
            raw_tags = parsed.get("tags", [])
        except Exception as e:
            self.logger.warning(f"Tag extraction failed for {self.ticker}: {e}")
            return {"tags": [], "tags_count": 0, "data_sources_used": sources}

        valid_tags = self._filter_valid_tags(raw_tags)

        return {
            "tags": valid_tags,
            "tags_count": len(valid_tags),
            "data_sources_used": sources,
        }

    # ─── Context Building ────────────────────────────────────────────────────

    def _build_context(self) -> str:
        """Build concise context string from agent results."""
        parts = [f"Ticker: {self.ticker}"]

        # Fundamentals
        fund = self._get_agent_data("fundamentals")
        if fund:
            parts.append(f"Company: {fund.get('company_name', self.ticker)}")
            parts.append(f"Sector: {fund.get('sector', 'N/A')}")
            rev = fund.get("revenue")
            if rev:
                parts.append(f"Revenue: ${rev/1e9:.1f}B")
            margin = fund.get("gross_margin")
            if margin is not None:
                parts.append(f"Gross Margin: {margin*100:.1f}%")
            desc = fund.get("business_description", "")
            if desc:
                parts.append(f"Business: {desc[:200]}")

        # Solution summary
        solution = self._get_agent_data("solution")
        if not solution:
            # Solution might be stored differently — check for recommendation/summary at top level
            pass
        if solution:
            parts.append(f"Recommendation: {solution.get('recommendation', 'N/A')}")
            summary = solution.get("summary", "")
            if summary:
                parts.append(f"Summary: {summary[:300]}")
            risks = solution.get("risks", [])
            if risks:
                parts.append(f"Risks: {'; '.join(risks[:3])}")
            opps = solution.get("opportunities", [])
            if opps:
                parts.append(f"Opportunities: {'; '.join(opps[:3])}")

        # News headlines
        news = self._get_agent_data("news")
        if news:
            articles = news.get("articles", [])[:3]
            headlines = [a.get("title", "") for a in articles if a.get("title")]
            if headlines:
                parts.append(f"Recent News: {'; '.join(headlines)}")

        # Thesis (if available)
        thesis_result = self.agent_results.get("thesis")
        if isinstance(thesis_result, dict) and not thesis_result.get("error"):
            bull = (thesis_result.get("bull_case") or {}).get("thesis", "")
            bear = (thesis_result.get("bear_case") or {}).get("thesis", "")
            if bull:
                parts.append(f"Bull Case: {bull[:200]}")
            if bear:
                parts.append(f"Bear Case: {bear[:200]}")

        return "\n".join(parts)

    def _get_agent_data(self, agent_name: str) -> Optional[Dict[str, Any]]:
        """Safely extract data dict from an agent result."""
        result = self.agent_results.get(agent_name, {})
        if isinstance(result, dict) and result.get("success"):
            return result.get("data")
        return None

    def _get_available_sources(self) -> List[str]:
        """Get list of agents that contributed context."""
        sources = []
        for name in ("fundamentals", "news", "solution"):
            result = self.agent_results.get(name, {})
            if isinstance(result, dict) and result.get("success") and result.get("data"):
                sources.append(name)
        return sources

    # ─── Tag Validation ──────────────────────────────────────────────────────

    @staticmethod
    def _filter_valid_tags(raw_tags: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Filter tags to only those in the fixed taxonomy."""
        valid = []
        for t in raw_tags:
            tag_name = t.get("tag", "")
            if tag_name in ALL_TAGS:
                # Ensure category is correct
                t["category"] = TAG_TO_CATEGORY[tag_name]
                valid.append(t)
        return valid

    # ─── LLM Prompt ──────────────────────────────────────────────────────────

    def _build_prompt(self, context: str) -> str:
        """Build the LLM prompt with full taxonomy."""
        taxonomy_str = ""
        for category, tags in TAG_TAXONOMY.items():
            taxonomy_str += f"\n  {category}: {', '.join(tags)}"

        return f"""You are a senior equity research analyst classifying a company based on qualitative attributes.

Given the analysis data below, select ALL tags that apply from the predefined taxonomy.
For each tag you select, provide a brief evidence string (1 sentence) explaining why it applies.

ONLY select tags from this list — do NOT invent new tags:
{taxonomy_str}

Return a JSON object with EXACTLY this structure — no markdown, no explanation, just raw JSON:

{{"tags": [{{"tag": "tag_name", "category": "category_name", "evidence": "one sentence why"}}]}}

Rules:
- Only select tags supported by the data. Do not guess.
- Typically 3-8 tags per company. Do not over-tag.
- Evidence should cite specific data points, not vague claims.

--- COMPANY ANALYSIS ---
{context}
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
                max_tokens=llm_config.get("max_tokens", 2048),
                temperature=llm_config.get("temperature", 0.2),
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
                max_tokens=llm_config.get("max_tokens", 2048),
                temperature=llm_config.get("temperature", 0.2),
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
