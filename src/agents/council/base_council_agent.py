"""Base class for all Investor Council agents."""

import asyncio
import json
import logging
import re
import time
from abc import abstractmethod
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from ..base_agent import BaseAgent
from .profiles import get_profile


class BaseCouncilAgent(BaseAgent):
    """
    Abstract base for all Investor Council agents.

    Each concrete agent corresponds to one investor persona. The agent
    receives context (existing agent_results + optional thesis_card) via
    set_context() before execute() is called. It makes a single LLM call
    using the investor's framework and produces a structured CouncilResult.

    Lifecycle (called by the orchestrator's run_council method):
        agent.set_context(agent_results, thesis_card)
        result = await agent.execute()
    """

    # Subclasses set this to their investor key (e.g. "druckenmiller")
    INVESTOR_KEY: str = ""

    def __init__(self, ticker: str, config: Dict[str, Any]):
        super().__init__(ticker, config)
        self._agent_results: Dict[str, Any] = {}
        self._thesis_card: Optional[Dict[str, Any]] = None
        self._profile = get_profile(self.INVESTOR_KEY)

    def set_context(
        self,
        agent_results: Dict[str, Any],
        thesis_card: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Inject analysis context before execution."""
        self._agent_results = agent_results or {}
        self._thesis_card = thesis_card

    # ── BaseAgent interface ──────────────────────────────────────────────────

    async def fetch_data(self) -> Dict[str, Any]:
        """No external data needed; context is injected via set_context()."""
        return {}

    async def analyze(self, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        """Build prompt and call LLM."""
        llm_config = self.config.get("llm_config", {})
        provider = llm_config.get("provider", "anthropic")

        if provider == "anthropic":
            return await self._call_anthropic(llm_config)
        elif provider in ("openai", "xai"):
            return await self._call_openai(llm_config)
        else:
            return self._fallback_result("LLM provider not configured")

    # ── Prompt construction ──────────────────────────────────────────────────

    def _build_prompt(self) -> str:
        profile = self._profile
        framework_text = "\n".join(f"  {i+1}. {dim}" for i, dim in enumerate(profile["framework"]))
        rules_text = "\n".join(f"  - {rule}" for rule in profile["rules"])

        data_summary = self._build_data_summary()
        thesis_section = self._build_thesis_section()

        return f"""You are {profile['name']}, the legendary investor.

Your tagline: "{profile['tagline']}"

Your investment philosophy:
{profile['persona']}

Your analytical framework:
{framework_text}

Your classic rules:
{rules_text}

Your specific council role: {profile['council_role']}
Your primary question for this analysis: {profile['primary_question']}

---

You are analyzing {self.ticker} for the Investor Council.

{thesis_section}

Quantitative data summary from the multi-agent research pipeline:
{data_summary}

---

In your voice and using your framework, provide a structured analysis of {self.ticker}.

Respond ONLY with valid JSON matching this exact schema:
{{
  "investor": "{self.INVESTOR_KEY}",
  "stance": "<BULLISH|CAUTIOUS|BEARISH|PASS>",
  "thesis_health": "<INTACT|WATCHING|DETERIORATING|BROKEN|UNKNOWN>",
  "qualitative_analysis": "<2–4 sentences in your voice applying your framework to this specific stock and moment>",
  "primary_question_answered": "<Direct answer to your primary question in 1–2 sentences>",
  "key_observations": ["<observation 1>", "<observation 2>", "<observation 3>"],
  "if_then_scenarios": [
    {{
      "type": "<macro|event|price|catalyst>",
      "condition": "If <specific, concrete condition>",
      "action": "then <specific action — enter/exit/reduce/add/hold>",
      "conviction": "<high|medium|low>"
    }}
  ],
  "disagreement_flag": "<optional — note if your stance likely contradicts another council member's and why>"
}}

Rules:
- 2–3 if_then_scenarios, each with a concrete observable condition (not vague)
- thesis_health is UNKNOWN if no thesis card was provided
- stance PASS means the thesis is outside your circle of competence or there is insufficient data
- Speak in first person as {profile['name']}
"""

    def _build_data_summary(self) -> str:
        parts = []
        r = self._agent_results

        # Market data
        mkt = (r.get("market") or {}).get("data") or {}
        if mkt:
            price = mkt.get("current_price") or mkt.get("price")
            change = mkt.get("price_change_1m") or {}
            trend = mkt.get("trend", "N/A")
            parts.append(
                f"Market: price=${price}, 1-month change={change.get('change_pct', 'N/A')}%, trend={trend}"
            )

        # Fundamentals
        fund = (r.get("fundamentals") or {}).get("data") or {}
        if fund:
            metrics = fund.get("key_metrics") or {}
            pe = metrics.get("pe_ratio") or fund.get("pe_ratio", "N/A")
            rev_growth = metrics.get("revenue_growth") or fund.get("revenue_growth", "N/A")
            fcf = metrics.get("free_cash_flow") or fund.get("free_cash_flow", "N/A")
            debt = metrics.get("debt_to_equity") or fund.get("debt_to_equity", "N/A")
            parts.append(
                f"Fundamentals: P/E={pe}, revenue growth={rev_growth}, FCF={fcf}, D/E={debt}"
            )

        # Technical
        tech = (r.get("technical") or {}).get("data") or {}
        if tech:
            rsi = tech.get("rsi", "N/A")
            macd = tech.get("macd_signal", tech.get("macd", "N/A"))
            signal = tech.get("signal_strength", tech.get("overall_signal", "N/A"))
            parts.append(f"Technical: RSI={rsi}, MACD signal={macd}, overall={signal}")

        # Sentiment
        sent = (r.get("sentiment") or {}).get("data") or {}
        if sent:
            score = sent.get("overall_sentiment", "N/A")
            parts.append(f"Sentiment: overall={score}")

        # Macro
        macro = (r.get("macro") or {}).get("data") or {}
        if macro:
            fed = macro.get("fed_funds_rate", "N/A")
            regime = macro.get("economic_cycle", macro.get("regime", "N/A"))
            parts.append(f"Macro: fed funds rate={fed}, economic regime={regime}")

        # Options
        opts = (r.get("options") or {}).get("data") or {}
        if opts:
            pc = opts.get("put_call_ratio", "N/A")
            signal = opts.get("overall_signal", "N/A")
            parts.append(f"Options: P/C ratio={pc}, smart-money signal={signal}")

        # News headlines
        news = (r.get("news") or {}).get("data") or {}
        articles = news.get("articles") or news.get("news_articles") or []
        if articles:
            headlines = [a.get("title", "") for a in articles[:3] if a.get("title")]
            if headlines:
                parts.append("Recent headlines:\n" + "\n".join(f"  - {h}" for h in headlines))

        if not parts:
            return "No quantitative data available."
        return "\n".join(parts)

    def _build_thesis_section(self) -> str:
        if not self._thesis_card:
            return "No thesis card provided — analyze based on market data alone."

        tc = self._thesis_card
        lines = ["Investor's thesis card for this position:"]
        if tc.get("structural_thesis"):
            lines.append(f"  Structural thesis: {tc['structural_thesis']}")
        if tc.get("near_term_thesis"):
            lines.append(f"  Near-term thesis: {tc['near_term_thesis']}")
        if tc.get("load_bearing_assumption"):
            lines.append(f"  Load-bearing assumption: {tc['load_bearing_assumption']}")
        if tc.get("exit_conditions"):
            lines.append(f"  Pre-defined exit conditions: {tc['exit_conditions']}")
        if tc.get("time_horizon"):
            lines.append(f"  Time horizon: {tc['time_horizon']}")
        if tc.get("sizing_class"):
            lines.append(f"  Position sizing: {tc['sizing_class']}")

        indicators = tc.get("health_indicators") or []
        if indicators:
            lines.append("  Thesis health indicators to monitor:")
            for ind in indicators:
                name = ind.get("name", "")
                proxy = ind.get("proxy_signal", "")
                current = ind.get("current_value", "N/A")
                baseline = ind.get("baseline_value", "N/A")
                lines.append(f"    - {name} ({proxy}): current={current}, baseline={baseline}")

        return "\n".join(lines)

    # ── LLM calls ────────────────────────────────────────────────────────────

    async def _call_anthropic(self, llm_config: Dict[str, Any]) -> Dict[str, Any]:
        import anthropic

        api_key = llm_config.get("api_key")
        if not api_key:
            return self._fallback_result("No Anthropic API key configured")

        prompt = self._build_prompt()
        client = anthropic.Anthropic(api_key=api_key)

        def _call():
            return client.messages.create(
                model=llm_config.get("model", "claude-3-5-sonnet-20241022"),
                max_tokens=llm_config.get("max_tokens", 1024),
                temperature=llm_config.get("temperature", 0.3),
                messages=[{"role": "user", "content": prompt}],
            )

        message = await asyncio.to_thread(_call)
        return self._parse_llm_response(message.content[0].text)

    async def _call_openai(self, llm_config: Dict[str, Any]) -> Dict[str, Any]:
        from openai import OpenAI

        api_key = llm_config.get("api_key")
        base_url = llm_config.get("base_url")
        if not api_key:
            return self._fallback_result("No OpenAI API key configured")

        prompt = self._build_prompt()
        kwargs = {"api_key": api_key}
        if base_url:
            kwargs["base_url"] = base_url
        client = OpenAI(**kwargs)

        def _call():
            return client.chat.completions.create(
                model=llm_config.get("model", "gpt-4o"),
                max_tokens=llm_config.get("max_tokens", 1024),
                temperature=llm_config.get("temperature", 0.3),
                messages=[{"role": "user", "content": prompt}],
            )

        response = await asyncio.to_thread(_call)
        return self._parse_llm_response(response.choices[0].message.content)

    # ── Response parsing ─────────────────────────────────────────────────────

    def _parse_llm_response(self, text: str) -> Dict[str, Any]:
        """Extract JSON from LLM response (handles markdown code fences)."""
        # Strip markdown fences
        json_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
        if json_match:
            text = json_match.group(1)
        else:
            # Try to find raw JSON object
            obj_match = re.search(r"\{.*\}", text, re.DOTALL)
            if obj_match:
                text = obj_match.group(0)

        try:
            data = json.loads(text)
            # Normalise required fields
            data.setdefault("investor", self.INVESTOR_KEY)
            data.setdefault("stance", "PASS")
            data.setdefault("thesis_health", "UNKNOWN")
            data.setdefault("qualitative_analysis", "")
            data.setdefault("primary_question_answered", "")
            data.setdefault("key_observations", [])
            data.setdefault("if_then_scenarios", [])
            return data
        except (json.JSONDecodeError, ValueError) as exc:
            self.logger.warning(f"Council JSON parse failed for {self.INVESTOR_KEY}: {exc}")
            return self._fallback_result(f"JSON parse error: {exc}")

    def _fallback_result(self, reason: str) -> Dict[str, Any]:
        return {
            "investor": self.INVESTOR_KEY,
            "stance": "PASS",
            "thesis_health": "UNKNOWN",
            "qualitative_analysis": f"Analysis unavailable: {reason}",
            "primary_question_answered": "",
            "key_observations": [],
            "if_then_scenarios": [],
            "error": reason,
        }
