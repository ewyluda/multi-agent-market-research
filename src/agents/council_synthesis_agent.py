"""LLM-powered council synthesis narrative agent.

Reads council results + thesis health + signal contract + validation report
and produces a ~200-word unified interpretation. Graceful fallback if LLM fails.
"""

import asyncio
import json
import logging
import re
from typing import Any, Dict, List, Optional

from .base_agent import BaseAgent

logger = logging.getLogger(__name__)


class CouncilSynthesisAgent(BaseAgent):
    """Synthesizes council output into a unified narrative via LLM."""

    def __init__(self, ticker: str, config: Dict[str, Any]):
        super().__init__(ticker, config)
        self._council_results: List[Dict[str, Any]] = []
        self._thesis_health: Optional[Dict[str, Any]] = None
        self._signal_contract: Optional[Dict[str, Any]] = None
        self._validation: Optional[Dict[str, Any]] = None

    def get_agent_type(self) -> str:
        return "council_synthesis"

    def set_synthesis_context(
        self,
        council_results: List[Dict[str, Any]],
        thesis_health: Optional[Dict[str, Any]] = None,
        signal_contract: Optional[Dict[str, Any]] = None,
        validation: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Inject council output and supporting data before execution."""
        self._council_results = council_results or []
        self._thesis_health = thesis_health
        self._signal_contract = signal_contract
        self._validation = validation

    async def fetch_data(self) -> Dict[str, Any]:
        """No external fetch needed; context injected via set_synthesis_context."""
        return {}

    async def analyze(self, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        """Produce synthesis narrative from council + supporting context."""
        if not self._council_results:
            return self._empty_narrative()

        prompt = self._build_synthesis_prompt()

        try:
            llm_text = await self._call_llm(prompt)
            return self._parse_narrative_response(llm_text)
        except Exception as exc:
            logger.warning(f"Council synthesis LLM call failed: {exc}")
            return self._empty_narrative(fallback_used=True)

    def _build_synthesis_prompt(self) -> str:
        sections = [
            "You are a senior investment analyst synthesizing the output of an investor council.",
            f"\n## Ticker: {self.ticker}",
            "\n## Council Results:",
        ]

        for r in self._council_results:
            investor = r.get("investor_name") or r.get("investor", "Unknown")
            stance = r.get("stance", "PASS")
            analysis = r.get("qualitative_analysis", "")
            obs = r.get("key_observations", [])
            obs_text = "; ".join(obs[:3]) if obs else "none"
            sections.append(f"\n**{investor}** — {stance}")
            sections.append(f"Analysis: {analysis}")
            sections.append(f"Key observations: {obs_text}")

        if self._thesis_health:
            health = self._thesis_health.get("overall_health", "UNKNOWN")
            indicators = self._thesis_health.get("indicators", [])
            ind_summary = ", ".join(f"{i['name']}: {i['status']}" for i in indicators[:5])
            sections.append(f"\n## Thesis Health: {health}")
            if ind_summary:
                sections.append(f"Indicators: {ind_summary}")

        if self._signal_contract:
            direction = self._signal_contract.get("direction", "unknown")
            conf = (self._signal_contract.get("confidence") or {}).get("raw", "?")
            sections.append(f"\n## Signal Contract: direction={direction}, confidence={conf}")

        if self._validation:
            val_status = self._validation.get("overall_status", "unknown")
            penalty = self._validation.get("total_confidence_penalty", 0)
            sections.append(f"\n## Validation: status={val_status}, penalty={penalty}")

        sections.append("""
## Task

Produce a JSON object with exactly these fields:
{
  "narrative": "<~200 words: what does the council agree on, where do they disagree, what does it mean for the position, what's the one thing to watch>",
  "position_implication": "<one-line action: e.g. Hold with tighter stop / Add on weakness / Reduce to half>",
  "watch_item": "<single most important thing to monitor>"
}

Respond ONLY with valid JSON. No markdown fences, no commentary.""")

        return "\n".join(sections)

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

    def _parse_narrative_response(self, text: str) -> Dict[str, Any]:
        """Parse LLM JSON response into SynthesisNarrative."""
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
            logger.warning(f"Council synthesis JSON parse failed: {exc}")
            return self._empty_narrative(fallback_used=True)

        llm_config = self.config.get("llm_config", {})
        return {
            "narrative": str(data.get("narrative", "")),
            "position_implication": str(data.get("position_implication", "")),
            "watch_item": str(data.get("watch_item", "")),
            "llm_provider": llm_config.get("provider", "unknown"),
            "fallback_used": False,
        }

    def _empty_narrative(self, fallback_used: bool = False) -> Dict[str, Any]:
        return {
            "narrative": "",
            "position_implication": "",
            "watch_item": "",
            "llm_provider": self.config.get("llm_config", {}).get("provider", "unknown"),
            "fallback_used": fallback_used if fallback_used else (not bool(self._council_results)),
        }
