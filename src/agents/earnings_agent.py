"""Earnings call analysis agent — deep transcript analysis via LLM."""

import asyncio
import json
import re
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone

import anthropic
from openai import OpenAI

from .base_agent import BaseAgent

logger = logging.getLogger(__name__)


class EarningsAgent(BaseAgent):
    """Agent for deep earnings call transcript analysis.

    Fetches up to 4 quarters of earnings transcripts and EPS history,
    then uses LLM to extract highlights, guidance, Q&A summaries,
    and management tone analysis.
    """

    async def fetch_data(self) -> Dict[str, Any]:
        """Fetch earnings transcripts and EPS history.

        Returns:
            Dict with 'transcripts' list and 'earnings_history' dict.
        """
        num_quarters = self.config.get("EARNINGS_TRANSCRIPT_QUARTERS", 4)
        dp = getattr(self, "_data_provider", None)
        if not dp:
            return {"transcripts": [], "earnings_history": {}}

        transcripts_task = dp.get_earnings_transcripts(self.ticker, num_quarters=num_quarters)
        earnings_task = dp.get_earnings(self.ticker)

        transcripts_result, earnings_result = await asyncio.gather(
            transcripts_task, earnings_task, return_exceptions=True
        )

        transcripts = transcripts_result if isinstance(transcripts_result, list) else []
        earnings_history = earnings_result if isinstance(earnings_result, dict) else {}

        self.logger.info(
            f"Fetched {len(transcripts)} transcripts and earnings history for {self.ticker}"
        )

        return {
            "transcripts": transcripts,
            "earnings_history": earnings_history,
        }

    async def analyze(self, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze earnings transcripts via LLM.

        Args:
            raw_data: Output from fetch_data().

        Returns:
            Structured earnings analysis dict.
        """
        transcripts = raw_data.get("transcripts", [])
        earnings_history = raw_data.get("earnings_history", {})

        # Build EPS history from earnings data
        eps_history = self._build_eps_history(earnings_history)

        # Build available quarters list
        available_quarters = [
            {"quarter": t["quarter"], "year": t["year"], "date": t.get("date", "")}
            for t in transcripts
        ]

        if not transcripts:
            return self._empty_result(eps_history, available_quarters)

        latest = transcripts[0]
        call_metadata = {
            "quarter": latest.get("quarter"),
            "year": latest.get("year"),
            "date": latest.get("date", ""),
            "symbol": self.ticker,
        }

        # Build LLM prompt and call
        prompt = self._build_prompt(transcripts)

        try:
            llm_response = await self._call_llm(prompt)
            parsed = self._parse_llm_response(llm_response)
        except Exception as e:
            self.logger.warning(f"LLM analysis failed for {self.ticker}: {e}")
            return self._fallback_result(call_metadata, eps_history, available_quarters)

        return {
            "call_metadata": call_metadata,
            "tone": parsed.get("tone", "neutral"),
            "guidance_direction": parsed.get("guidance_direction", "maintained"),
            "highlights": parsed.get("highlights", []),
            "guidance": parsed.get("guidance", []),
            "qa_highlights": parsed.get("qa_highlights", []),
            "tone_analysis": parsed.get("tone_analysis", {
                "confidence": 50, "specificity": 50,
                "defensiveness": 50, "forward_looking": 50, "hedging": 50,
            }),
            "eps_history": eps_history,
            "available_quarters": available_quarters,
            "analysis": parsed.get("analysis", ""),
            "stance": parsed.get("stance", "neutral"),
            "data_source": latest.get("data_source", "fmp"),
        }

    # ─── EPS History Builder ─────────────────────────────────────────────────

    def _build_eps_history(self, earnings_history: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Build formatted EPS history from raw earnings data."""
        eps_list = earnings_history.get("eps_history", [])
        result = []
        for entry in eps_list[:8]:
            actual = entry.get("reported_eps") or entry.get("actual_eps")
            estimate = entry.get("estimated_eps") or entry.get("consensus_eps")
            if actual is None or estimate is None:
                continue
            actual = float(actual)
            estimate = float(estimate)
            surprise_pct = ((actual - estimate) / abs(estimate) * 100) if estimate != 0 else 0.0
            date_str = entry.get("date", "")
            label = self._date_to_quarter_label(date_str)
            result.append({
                "quarter": label,
                "actual": actual,
                "estimate": estimate,
                "surprise_pct": round(surprise_pct, 2),
            })
        return result

    @staticmethod
    def _date_to_quarter_label(date_str: str) -> str:
        """Convert date string to quarter label like Q1'26."""
        if not date_str:
            return "?"
        try:
            dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        except (ValueError, TypeError):
            return "?"
        q = (dt.month - 1) // 3 + 1
        return f"Q{q}'{dt.strftime('%y')}"

    # ─── LLM Prompt ──────────────────────────────────────────────────────────

    def _build_prompt(self, transcripts: List[Dict[str, Any]]) -> str:
        """Build the LLM prompt from transcript content."""
        latest = transcripts[0]
        q, y = latest.get("quarter", "?"), latest.get("year", "?")

        prior_content = ""
        if len(transcripts) > 1:
            prior = transcripts[1]
            prior_content = (
                f"\n\n--- PRIOR QUARTER TRANSCRIPT (Q{prior.get('quarter')}/{prior.get('year')}) ---\n"
                f"{prior.get('content', '')[:8000]}"
            )

        return f"""Analyze this earnings call transcript for {self.ticker} (Q{q}/{y}).
Return a JSON object with EXACTLY these keys — no markdown, no explanation, just raw JSON:

{{
  "highlights": [
    {{"tag": "BEAT|MISS|NEW|WATCH", "text": "one-sentence highlight"}}
  ],
  "guidance": [
    {{"metric": "Revenue|EPS|Gross Margin|CapEx|...", "prior": "$X-YB", "current": "$X-YB", "direction": "raised|lowered|maintained|introduced|withdrawn"}}
  ],
  "qa_highlights": [
    {{"analyst": "Name", "firm": "Firm", "topic": "2-3 word tag", "question": "one sentence", "answer": "2-3 sentences"}}
  ],
  "tone_analysis": {{
    "confidence": 0-100,
    "specificity": 0-100,
    "defensiveness": 0-100,
    "forward_looking": 0-100,
    "hedging": 0-100
  }},
  "tone": "confident|cautious|defensive|evasive|optimistic",
  "guidance_direction": "raised|lowered|maintained|mixed",
  "stance": "bullish|bearish|neutral",
  "analysis": "2-3 paragraph investment-focused narrative"
}}

Rules:
- highlights: 4-6 items. Tag each: BEAT (exceeded expectations), MISS (missed), NEW (strategic announcement), WATCH (risk/concern).
- guidance: Compare current quarter guidance vs prior quarter. If prior quarter transcript is provided, use it for "prior" values. If no prior data, use "N/A" for prior.
- qa_highlights: Top 3-5 most material Q&A exchanges. Include analyst name and firm if mentioned.
- tone_analysis: Score each dimension 0-100 based on management language and behavior in Q&A.
- stance: Overall investment signal from the call.
- analysis: Write as an equity research analyst. Focus on what matters for the investment thesis.

--- CURRENT QUARTER TRANSCRIPT (Q{q}/{y}) ---
{latest.get('content', '')}
{prior_content}
"""

    # ─── LLM Call ─────────────────────────────────────────────────────────────

    async def _call_llm(self, prompt: str) -> str:
        """Call the configured LLM provider."""
        llm_config = self.config.get("llm_config", {})
        provider = llm_config.get("provider", "anthropic")

        if provider == "anthropic":
            return await self._call_anthropic(prompt, llm_config)
        else:
            return await self._call_openai(prompt, llm_config)

    async def _call_anthropic(self, prompt: str, llm_config: Dict[str, Any]) -> str:
        api_key = llm_config.get("api_key")
        if not api_key:
            raise ValueError("No Anthropic API key configured")

        client = anthropic.Anthropic(api_key=api_key)

        def _call():
            return client.messages.create(
                model=llm_config.get("model", "claude-3-5-sonnet-20241022"),
                max_tokens=llm_config.get("max_tokens", 4096),
                temperature=0.3,
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
                temperature=0.3,
                messages=[{"role": "user", "content": prompt}],
            )

        response = await asyncio.to_thread(_call)
        return response.choices[0].message.content.strip()

    # ─── Response Parsing ─────────────────────────────────────────────────────

    def _parse_llm_response(self, raw: str) -> Dict[str, Any]:
        """Parse LLM JSON response, stripping markdown fences if present."""
        text = raw.strip()
        if text.startswith("```"):
            text = re.sub(r"^```(?:json)?\s*\n?", "", text)
            text = re.sub(r"\n?```\s*$", "", text)
        return json.loads(text)

    # ─── Fallback / Empty Results ─────────────────────────────────────────────

    def _empty_result(
        self,
        eps_history: List[Dict[str, Any]],
        available_quarters: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Return result when no transcripts are available."""
        return {
            "call_metadata": {"quarter": None, "year": None, "date": "", "symbol": self.ticker},
            "tone": "neutral",
            "guidance_direction": "maintained",
            "highlights": [],
            "guidance": [],
            "qa_highlights": [],
            "tone_analysis": {
                "confidence": 50, "specificity": 50,
                "defensiveness": 50, "forward_looking": 50, "hedging": 50,
            },
            "eps_history": eps_history,
            "available_quarters": available_quarters,
            "analysis": "No earnings call transcripts available for analysis.",
            "stance": "neutral",
            "data_source": "none",
        }

    def _fallback_result(
        self,
        call_metadata: Dict[str, Any],
        eps_history: List[Dict[str, Any]],
        available_quarters: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Return result when LLM call fails."""
        return {
            "call_metadata": call_metadata,
            "tone": "neutral",
            "guidance_direction": "maintained",
            "highlights": [],
            "guidance": [],
            "qa_highlights": [],
            "tone_analysis": {
                "confidence": 50, "specificity": 50,
                "defensiveness": 50, "forward_looking": 50, "hedging": 50,
            },
            "eps_history": eps_history,
            "available_quarters": available_quarters,
            "analysis": "Earnings call analysis unavailable — LLM processing failed.",
            "stance": "neutral",
            "data_source": call_metadata.get("symbol", "fmp"),
        }
