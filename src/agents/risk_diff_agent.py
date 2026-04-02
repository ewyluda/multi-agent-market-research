"""Risk Diff agent — two-pass LLM SEC filing risk factor change detection."""

import asyncio
import json
import re
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple

import anthropic
from openai import OpenAI

from .base_agent import BaseAgent


class RiskDiffAgent(BaseAgent):
    """Agent that detects changes in SEC filing risk factors across periods.

    Hybrid agent: fetches filing metadata from FMP and full text from EDGAR
    in fetch_data(), then runs a two-pass LLM:
        Pass 1 ("The Cataloger"): Extracts risk inventory per filing (concurrent).
        Pass 2 ("The Comparator"): Diffs inventories across periods.

    Data gate:
        - 0 filings parsed -> empty result
        - 1 filing parsed -> risk inventory only (has_diff=False)
        - 2+ filings parsed -> full diff

    Runs in the synthesis phase, parallel with Solution, Thesis, EarningsReview,
    Narrative, and TagExtractor.
    """

    def __init__(self, ticker: str, config: Dict[str, Any], agent_results: Dict[str, Any]):
        super().__init__(ticker, config)
        self.agent_results = agent_results

    async def fetch_data(self) -> Dict[str, Any]:
        """Fetch SEC filing metadata and risk factor sections.

        1. Get filing metadata from FMP (two most recent 10-Ks + latest 10-Q).
        2. For each filing, concurrently fetch HTML from EDGAR and parse Item 1A.
        3. Return filings with risk text and extraction methods.
        """
        dp = getattr(self, "_data_provider", None)
        if not dp:
            return {"filings": [], "agent_results": self.agent_results}

        # Fetch metadata: two 10-Ks + one 10-Q
        ten_k_task = dp.get_sec_filing_metadata(self.ticker, filing_type="10-K", limit=2)
        ten_q_task = dp.get_sec_filing_metadata(self.ticker, filing_type="10-Q", limit=1)

        ten_k_filings, ten_q_filings = await asyncio.gather(
            ten_k_task, ten_q_task, return_exceptions=True
        )
        ten_k_filings = ten_k_filings if isinstance(ten_k_filings, list) else []
        ten_q_filings = ten_q_filings if isinstance(ten_q_filings, list) else []

        all_metadata = ten_k_filings + ten_q_filings

        if not all_metadata:
            self.logger.info(f"RiskDiff: no filing metadata found for {self.ticker}")
            return {"filings": [], "agent_results": self.agent_results}

        # Concurrently fetch and parse each filing's risk section
        async def _fetch_section(meta: Dict[str, Any]) -> Optional[Dict[str, Any]]:
            url = meta.get("filing_url", "")
            if not url:
                return None
            try:
                section_result = await dp.get_sec_filing_section(
                    self.ticker, url, section="1A"
                )
                if section_result is None:
                    return None

                risk_text = section_result.get("section_text")
                extraction_method = section_result.get("extraction_method", "unknown")

                # Handle LLM fallback case
                if risk_text is None and extraction_method == "needs_llm_fallback":
                    raw_text = section_result.get("raw_text_for_fallback", "")
                    if raw_text:
                        risk_text = await self._llm_extract_risk_section(raw_text)
                        extraction_method = "llm_fallback" if risk_text else "failed"

                if not risk_text:
                    return None

                return {
                    "filing_type": meta.get("filing_type", ""),
                    "filing_date": meta.get("filing_date", ""),
                    "accession_number": meta.get("accession_number", ""),
                    "filing_url": url,
                    "risk_text": risk_text,
                    "extraction_method": extraction_method,
                }
            except Exception as e:
                self.logger.warning(f"RiskDiff: failed to fetch section for {url}: {e}")
                return None

        section_tasks = [_fetch_section(meta) for meta in all_metadata]
        section_results = await asyncio.gather(*section_tasks, return_exceptions=True)

        filings = []
        for result in section_results:
            if isinstance(result, dict) and result.get("risk_text"):
                filings.append(result)

        self.logger.info(
            f"RiskDiff: fetched {len(filings)}/{len(all_metadata)} filing sections for {self.ticker}"
        )

        return {"filings": filings, "agent_results": self.agent_results}

    async def analyze(self, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        """Run two-pass LLM analysis on fetched filing data."""
        filings = raw_data.get("filings", [])
        completeness = self._compute_data_completeness(filings)
        sources = self._get_data_sources(filings)

        # Data gate: 0 filings -> empty
        if not filings:
            return self._empty_result(completeness, sources)

        # Pass 1: Extract risk inventories concurrently
        pass1_tasks = [self._run_pass1(f) for f in filings]
        pass1_results = await asyncio.gather(*pass1_tasks, return_exceptions=True)

        inventories = []
        for i, result in enumerate(pass1_results):
            if isinstance(result, dict) and result.get("risks"):
                inventories.append({
                    "filing": filings[i],
                    "inventory": result,
                })
            elif isinstance(result, Exception):
                self.logger.warning(f"RiskDiff Pass 1 failed for filing {i}: {result}")

        if not inventories:
            return self._empty_result(completeness, sources)

        # Build filing comparison metadata
        filings_compared = [
            {
                "type": inv["filing"]["filing_type"],
                "date": inv["filing"]["filing_date"],
                "accession_number": inv["filing"]["accession_number"],
            }
            for inv in inventories
        ]
        extraction_methods = [inv["filing"].get("extraction_method", "unknown") for inv in inventories]

        # Current risk inventory (from latest filing)
        current_inventory = inventories[0]["inventory"].get("risks", [])

        # Data gate: 1 filing -> inventory only
        if len(inventories) < 2:
            return self._inventory_only_result(
                current_inventory, filings_compared, extraction_methods,
                completeness, sources,
            )

        # Pass 2: Diff comparison
        try:
            # Separate 10-K inventories for primary diff
            ten_k_inventories = [inv for inv in inventories if inv["filing"]["filing_type"] == "10-K"]
            ten_q_inventories = [inv for inv in inventories if inv["filing"]["filing_type"] == "10-Q"]

            current_10k = ten_k_inventories[0]["inventory"] if ten_k_inventories else inventories[0]["inventory"]
            prior_10k = ten_k_inventories[1]["inventory"] if len(ten_k_inventories) >= 2 else None
            supplementary_10q = ten_q_inventories[0]["inventory"] if ten_q_inventories else None

            if prior_10k is None:
                # Can't diff without a prior — use any second inventory
                prior_10k = inventories[1]["inventory"]

            diff_result = await self._run_pass2(current_10k, prior_10k, supplementary_10q)

            diff_result["current_risk_inventory"] = current_inventory
            diff_result["filings_compared"] = filings_compared
            diff_result["has_diff"] = True
            diff_result["extraction_methods"] = extraction_methods
            diff_result["data_completeness"] = completeness
            diff_result["data_sources_used"] = sources

            # Guardrails
            from ..llm_guardrails import validate_risk_diff_output
            validated, guardrail_warnings = validate_risk_diff_output(diff_result)
            if guardrail_warnings:
                validated["guardrail_warnings"] = guardrail_warnings
            return validated

        except Exception as e:
            self.logger.warning(f"RiskDiff Pass 2 failed for {self.ticker}: {e}, using Pass 1 fallback")
            return self._pass1_fallback(
                current_inventory, filings_compared, extraction_methods,
                completeness, sources,
            )

    # --- Pass 1: Risk Inventory -------------------------------------------------

    async def _run_pass1(self, filing: Dict[str, Any]) -> Dict[str, Any]:
        """Pass 1 -- extract risk inventory from one filing's risk section."""
        risk_text = filing.get("risk_text", "")
        # Truncate to ~10K chars if needed
        if len(risk_text) > 10000:
            risk_text = risk_text[:10000]

        prompt = self._build_pass1_prompt(risk_text, filing)
        response = await self._call_llm(prompt)
        return self._parse_llm_response(response)

    def _build_pass1_prompt(self, risk_text: str, filing: Dict[str, Any]) -> str:
        """Build Pass 1 risk inventory extraction prompt."""
        filing_type = filing.get("filing_type", "10-K")
        filing_date = filing.get("filing_date", "unknown")

        return f"""You are a senior SEC filing analyst extracting risk topics from a company's Risk Factors section.

This is from a {filing_type} filed on {filing_date} for {self.ticker}.

IMPORTANT RULES:
- Extract DISTINCT risk topics only. Do not duplicate or split a single risk into multiple topics.
- Severity classification:
  - "high": language includes "material adverse effect", "significant risk", "could materially impact"
  - "medium": language includes "could impact", "may affect", "risks associated with"
  - "low": language includes "may affect", "potential impact", general cautionary language
- Do NOT invent risks not present in the text.
- text_excerpt should be a brief (1-2 sentence) direct quote from the filing.

Return a JSON object with EXACTLY this structure — no markdown, no explanation, just raw JSON:

{{
  "risks": [
    {{
      "topic": "Supply Chain Concentration",
      "severity": "high",
      "summary": "Company depends on 3 suppliers for 80% of components.",
      "text_excerpt": "We rely on a limited number of suppliers..."
    }}
  ]
}}

--- RISK FACTORS TEXT ---

{risk_text}
"""

    # --- Pass 2: Risk Diff ------------------------------------------------------

    async def _run_pass2(
        self,
        current_inventory: Dict[str, Any],
        prior_inventory: Dict[str, Any],
        supplementary_10q: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Pass 2 -- diff two risk inventories."""
        prompt = self._build_pass2_prompt(current_inventory, prior_inventory, supplementary_10q)
        response = await self._call_llm(prompt)
        return self._parse_llm_response(response)

    def _build_pass2_prompt(
        self,
        current: Dict[str, Any],
        prior: Dict[str, Any],
        supplementary: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Build Pass 2 risk diff comparison prompt."""
        current_json = json.dumps(current, indent=2)
        prior_json = json.dumps(prior, indent=2)
        supplement_section = ""
        if supplementary:
            supplement_json = json.dumps(supplementary, indent=2)
            supplement_section = f"""
--- SUPPLEMENTARY (Latest 10-Q Risk Inventory) ---
{supplement_json}
"""

        return f"""You are a senior SEC filing analyst comparing risk factor disclosures across periods for {self.ticker}.

Compare the CURRENT risk inventory against the PRIOR risk inventory. Classify each change:
- "new": Risk topic appears in current but not in prior
- "removed": Risk topic appears in prior but not in current
- "escalated": Same topic, but stronger language or higher severity in current
- "de-escalated": Same topic, but weaker language or lower severity in current
- "reworded": Same meaning, different words (not a substantive change)

IMPORTANT RULES:
- risk_score: 0 = minimal risk, 100 = extreme risk. Base on count and severity of CURRENT risks.
- risk_score_delta: Positive = riskier than prior period, negative = safer. Range [-50, +50].
- top_emerging_threats: 3-5 most actionable new or escalated risks for investors.
- Only classify as "escalated" if there is a genuine severity increase, not just rewording.

Return a JSON object with EXACTLY this structure — no markdown, no explanation, just raw JSON:

{{
  "new_risks": [
    {{
      "risk_topic": "AI Regulation",
      "change_type": "new",
      "severity": "medium",
      "current_text_excerpt": "New AI regulations may...",
      "prior_text_excerpt": "",
      "analysis": "Newly disclosed risk from emerging regulation."
    }}
  ],
  "removed_risks": [],
  "changed_risks": [],
  "risk_score": 65,
  "risk_score_delta": 5,
  "top_emerging_threats": ["AI regulation exposure"],
  "summary": "Risk profile moderately elevated with new AI regulatory disclosure."
}}

--- CURRENT (Latest 10-K Risk Inventory) ---
{current_json}

--- PRIOR (Previous 10-K Risk Inventory) ---
{prior_json}
{supplement_section}"""

    # --- LLM Fallback for HTML Parsing ------------------------------------------

    async def _llm_extract_risk_section(self, raw_text: str) -> Optional[str]:
        """Use LLM to extract Risk Factors section from stripped filing text."""
        prompt = (
            "The following is a SEC filing document. Extract ONLY the Risk Factors section "
            "(Item 1A). Return the full text of that section, nothing else. If you cannot "
            "find a Risk Factors section, return 'NOT_FOUND'.\n\n"
            f"--- FILING TEXT (first 30K chars) ---\n\n{raw_text[:30000]}"
        )
        try:
            response = await self._call_llm(prompt)
            if response.strip() == "NOT_FOUND" or len(response.strip()) < 200:
                return None
            return response.strip()
        except Exception as e:
            self.logger.warning(f"RiskDiff LLM fallback failed: {e}")
            return None

    # --- Data Completeness ------------------------------------------------------

    def _compute_data_completeness(self, filings: List[Dict[str, Any]]) -> float:
        """Compute data completeness score (0.0-1.0).

        Weights:
            latest_10k: 0.40
            prior_10k: 0.30
            latest_10q: 0.15
            fundamentals context: 0.15
        """
        score = 0.0

        ten_ks = [f for f in filings if f.get("filing_type") == "10-K" and f.get("risk_text")]
        ten_qs = [f for f in filings if f.get("filing_type") == "10-Q" and f.get("risk_text")]

        if len(ten_ks) >= 1:
            score += 0.40  # latest_10k
        if len(ten_ks) >= 2:
            score += 0.30  # prior_10k
        if len(ten_qs) >= 1:
            score += 0.15  # latest_10q

        # Fundamentals context
        fund_result = self.agent_results.get("fundamentals", {})
        if isinstance(fund_result, dict) and fund_result.get("success") and fund_result.get("data"):
            score += 0.15

        return round(min(score, 1.0), 2)

    def _get_data_sources(self, filings: List[Dict[str, Any]]) -> List[str]:
        """Get list of data sources used."""
        sources = []
        if filings:
            sources.append("fmp_filings")
            sources.append("edgar_html")
        methods = set(f.get("extraction_method", "") for f in filings)
        if "llm_fallback" in methods:
            sources.append("llm_fallback_extraction")
        fund_result = self.agent_results.get("fundamentals", {})
        if isinstance(fund_result, dict) and fund_result.get("success"):
            sources.append("fundamentals")
        return sources

    def _get_agent_data(self, agent_name: str) -> Optional[Dict[str, Any]]:
        """Safely extract data dict from agent results."""
        result = self.agent_results.get(agent_name, {})
        if isinstance(result, dict) and result.get("success"):
            return result.get("data")
        return None

    # --- LLM Call ---------------------------------------------------------------

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

    # --- Response Parsing -------------------------------------------------------

    @staticmethod
    def _parse_llm_response(raw: str) -> Dict[str, Any]:
        """Parse LLM JSON response, stripping markdown fences if present."""
        text = raw.strip()
        if text.startswith("```"):
            text = re.sub(r"^```(?:json)?\s*\n?", "", text)
            text = re.sub(r"\n?```\s*$", "", text)
        return json.loads(text)

    # --- Fallback Results -------------------------------------------------------

    def _empty_result(self, completeness: float, sources: List[str]) -> Dict[str, Any]:
        """Return empty result when no filings are available."""
        return {
            "new_risks": [],
            "removed_risks": [],
            "changed_risks": [],
            "risk_score": 0.0,
            "risk_score_delta": 0.0,
            "top_emerging_threats": [],
            "summary": f"No SEC filing risk factor data available for {self.ticker}.",
            "current_risk_inventory": [],
            "filings_compared": [],
            "has_diff": False,
            "extraction_methods": [],
            "data_completeness": completeness,
            "data_sources_used": sources,
            "error": "No SEC filings with risk factor sections found.",
        }

    def _inventory_only_result(
        self,
        inventory: List[Dict[str, Any]],
        filings_compared: List[Dict[str, Any]],
        extraction_methods: List[str],
        completeness: float,
        sources: List[str],
    ) -> Dict[str, Any]:
        """Return inventory-only result when only 1 filing is available."""
        return {
            "new_risks": [],
            "removed_risks": [],
            "changed_risks": [],
            "risk_score": 0.0,
            "risk_score_delta": 0.0,
            "top_emerging_threats": [],
            "summary": f"Single filing available for {self.ticker}; risk inventory only (no diff).",
            "current_risk_inventory": inventory,
            "filings_compared": filings_compared,
            "has_diff": False,
            "extraction_methods": extraction_methods,
            "data_completeness": completeness,
            "data_sources_used": sources,
        }

    def _pass1_fallback(
        self,
        inventory: List[Dict[str, Any]],
        filings_compared: List[Dict[str, Any]],
        extraction_methods: List[str],
        completeness: float,
        sources: List[str],
    ) -> Dict[str, Any]:
        """Fallback when Pass 2 fails -- return inventory with no diff."""
        return {
            "new_risks": [],
            "removed_risks": [],
            "changed_risks": [],
            "risk_score": 0.0,
            "risk_score_delta": 0.0,
            "top_emerging_threats": [],
            "summary": f"Risk inventory available for {self.ticker} but diff comparison failed.",
            "current_risk_inventory": inventory,
            "filings_compared": filings_compared,
            "has_diff": False,
            "extraction_methods": extraction_methods,
            "data_completeness": completeness,
            "data_sources_used": sources,
            "pass2_failed": True,
        }
