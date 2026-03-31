"""LLM-powered council validator agent.

Cross-checks investor council qualitative claims against raw agent data.
Uses a single LLM call per analysis run. Gracefully degrades if LLM is unavailable.
"""

import asyncio
import json
import logging
import re
from typing import Any, Dict, List, Optional

from .base_agent import BaseAgent

logger = logging.getLogger(__name__)

# Claim domain → which agent_results key to include
_CLAIM_AGENT_MAP = {
    "macro": ["macro"],
    "rates": ["macro"],
    "regime": ["macro"],
    "fed": ["macro"],
    "revenue": ["fundamentals"],
    "margins": ["fundamentals"],
    "valuation": ["fundamentals"],
    "earnings": ["fundamentals"],
    "growth": ["fundamentals"],
    "price": ["technical", "market"],
    "momentum": ["technical"],
    "technicals": ["technical"],
    "rsi": ["technical"],
    "options": ["options"],
    "put": ["options"],
    "call": ["options"],
    "management": ["leadership"],
    "governance": ["leadership"],
    "ceo": ["leadership"],
    "news": ["news", "sentiment"],
    "sentiment": ["sentiment"],
    "catalyst": ["news"],
}


class CouncilValidatorAgent(BaseAgent):
    """Validates council investor claims against raw agent data via LLM."""

    def __init__(self, ticker: str, config: Dict[str, Any]):
        super().__init__(ticker, config)
        self._council_results: List[Dict[str, Any]] = []
        self._agent_results: Dict[str, Any] = {}

    def get_agent_type(self) -> str:
        return "council_validator"

    def set_council_context(
        self,
        council_results: List[Dict[str, Any]],
        agent_results: Dict[str, Any],
    ) -> None:
        """Inject council output and raw agent data before execution."""
        self._council_results = council_results or []
        self._agent_results = agent_results or {}

    async def fetch_data(self) -> Dict[str, Any]:
        """No external fetch needed; context injected via set_council_context."""
        return {}

    async def analyze(self, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        """Run LLM validation on council claims."""
        if not self._council_results:
            return self._empty_report()

        prompt = self._build_validation_prompt()

        try:
            llm_text = await self._call_llm(prompt)
            return self._parse_validation_response(llm_text)
        except Exception as exc:
            logger.warning(f"Council validation LLM call failed: {exc}")
            return self._empty_report(fallback_used=True)

    # ── Prompt ────────────────────────────────────────────────────────────────

    def _build_validation_prompt(self) -> str:
        sections = []

        # Raw agent data summary
        sections.append("## Raw Agent Data\n")
        for agent_name, result in self._agent_results.items():
            if not isinstance(result, dict) or not result.get("success"):
                continue
            data = result.get("data") or {}
            sections.append(f"### {agent_name}\n```json\n{json.dumps(data, indent=2, default=str)}\n```\n")

        # Council claims to validate
        sections.append("## Council Investor Claims to Validate\n")
        for inv_result in self._council_results:
            investor = inv_result.get("investor", "unknown")
            sections.append(f"### {investor}")
            sections.append(f"Stance: {inv_result.get('stance', 'N/A')}")
            sections.append(f"Analysis: {inv_result.get('qualitative_analysis', '')}")

            observations = inv_result.get("key_observations") or []
            if observations:
                sections.append("Key observations:")
                for obs in observations:
                    sections.append(f"  - {obs}")

            scenarios = inv_result.get("if_then_scenarios") or []
            if scenarios:
                sections.append("If-then scenarios:")
                for sc in scenarios:
                    sections.append(f"  - {sc.get('condition', '')} → {sc.get('action', '')}")
            sections.append("")

        data_section = "\n".join(sections)

        return f"""You are a validation auditor. Your job is to cross-check investor council claims against the raw quantitative data from our research agents.

For each investor, examine every claim they make (in their qualitative_analysis, key_observations, and if_then_scenarios) and determine whether the raw agent data SUPPORTS, CONTRADICTS, or is UNVERIFIABLE for that claim.

{data_section}

---

Respond ONLY with valid JSON matching this schema:
{{
  "investor_validations": [
    {{
      "investor": "<investor key>",
      "claims": [
        {{
          "claim": "<the specific claim text>",
          "verdict": "supported|contradicted|unverifiable",
          "evidence": "<what the raw data shows that supports or contradicts>",
          "severity": "warning|contradiction"
        }}
      ]
    }}
  ]
}}

Rules:
- Only mark a claim as "contradicted" if the raw data clearly disagrees
- "unverifiable" means no relevant data exists to check the claim
- severity "contradiction" = clear factual mismatch; "warning" = directional tension but not definitive
- Be precise: quote specific numbers from the raw data
"""

    # ── LLM call ──────────────────────────────────────────────────────────────

    async def _call_llm(self, prompt: str) -> str:
        """Call the configured LLM provider. Returns raw text response."""
        llm_config = self.config.get("llm_config", {})
        provider = llm_config.get("provider", "anthropic")
        api_key = llm_config.get("api_key")

        if not api_key:
            raise ValueError("No LLM API key configured")

        if provider == "anthropic":
            import anthropic
            client = anthropic.Anthropic(api_key=api_key)
            message = await asyncio.to_thread(
                lambda: client.messages.create(
                    model=llm_config.get("model", "claude-3-5-sonnet-20241022"),
                    max_tokens=llm_config.get("max_tokens", 4096),
                    temperature=0.1,
                    messages=[{"role": "user", "content": prompt}],
                )
            )
            return message.content[0].text
        elif provider in ("openai", "xai"):
            from openai import OpenAI
            kwargs = {"api_key": api_key}
            base_url = llm_config.get("base_url")
            if base_url:
                kwargs["base_url"] = base_url
            client = OpenAI(**kwargs)
            response = await asyncio.to_thread(
                lambda: client.chat.completions.create(
                    model=llm_config.get("model", "gpt-4o"),
                    max_tokens=llm_config.get("max_tokens", 4096),
                    temperature=0.1,
                    messages=[{"role": "user", "content": prompt}],
                )
            )
            return response.choices[0].message.content
        else:
            raise ValueError(f"Unknown LLM provider: {provider}")

    # ── Response parsing ──────────────────────────────────────────────────────

    def _parse_validation_response(self, text: str) -> Dict[str, Any]:
        """Parse LLM JSON response into a CouncilValidationReport."""
        json_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
        if json_match:
            text = json_match.group(1)
        else:
            obj_match = re.search(r"\{.*\}", text, re.DOTALL)
            if obj_match:
                text = obj_match.group(0)

        try:
            data = json.loads(text)
        except (json.JSONDecodeError, ValueError) as exc:
            logger.warning(f"Council validation JSON parse failed: {exc}")
            return self._empty_report(fallback_used=True)

        investor_validations = []
        total_checked = 0
        total_contradictions = 0

        for inv_data in data.get("investor_validations", []):
            investor = inv_data.get("investor", "unknown")
            claims = inv_data.get("claims", [])

            supported = 0
            contradicted = 0
            unverifiable = 0
            contradictions = []

            for claim in claims:
                verdict = str(claim.get("verdict") or "").lower()
                total_checked += 1

                if verdict == "supported":
                    supported += 1
                elif verdict == "contradicted":
                    contradicted += 1
                    total_contradictions += 1
                    contradictions.append({
                        "claim": claim.get("claim", ""),
                        "evidence": claim.get("evidence", ""),
                        "severity": claim.get("severity", "contradiction"),
                    })
                else:
                    unverifiable += 1

            investor_validations.append({
                "investor": investor,
                "claims_checked": len(claims),
                "claims_supported": supported,
                "claims_contradicted": contradicted,
                "claims_unverifiable": unverifiable,
                "contradictions": contradictions,
            })

        # Penalty: 0.05 per contradiction, capped at 0.25
        penalty = min(total_contradictions * 0.05, 0.25)

        llm_config = self.config.get("llm_config", {})
        return {
            "investor_validations": investor_validations,
            "total_claims_checked": total_checked,
            "total_contradictions": total_contradictions,
            "confidence_penalty": round(penalty, 4),
            "llm_provider": llm_config.get("provider", "unknown"),
            "fallback_used": False,
        }

    def _empty_report(self, fallback_used: bool = False) -> Dict[str, Any]:
        return {
            "investor_validations": [],
            "total_claims_checked": 0,
            "total_contradictions": 0,
            "confidence_penalty": 0.0,
            "llm_provider": self.config.get("llm_config", {}).get("provider", "unknown"),
            "fallback_used": fallback_used,
        }
