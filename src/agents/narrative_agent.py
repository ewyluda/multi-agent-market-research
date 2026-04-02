"""Narrative agent — two-pass LLM multi-year financial story engine."""

import asyncio
import json
import re
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple

import anthropic
from openai import OpenAI

from .base_agent import BaseAgent


class NarrativeAgent(BaseAgent):
    """Agent that weaves multi-year financial data into a coherent investment narrative.

    Hybrid agent: fetches its own historical data in fetch_data() AND consumes
    agent_results for latest analysis context. Two-pass LLM:
        Pass 1 ("The Researcher"): Extracts per-year facts and cross-year themes.
        Pass 2 ("The Storyteller"): Synthesizes narrative with year sections and chapters.

    Runs in the synthesis phase, parallel with Solution, Thesis, and EarningsReview.
    """

    def __init__(self, ticker: str, config: Dict[str, Any], agent_results: Dict[str, Any]):
        super().__init__(ticker, config)
        self.agent_results = agent_results

    async def fetch_data(self) -> Dict[str, Any]:
        """Fetch multi-year financials and transcripts from data provider."""
        dp = getattr(self, "_data_provider", None)
        if not dp:
            return {"financials": None, "transcripts": [], "agent_results": self.agent_results}

        num_years = self.config.get("NARRATIVE_YEARS", 3)
        num_quarters = num_years * 4

        financials_task = dp.get_financials(self.ticker)
        transcripts_task = dp.get_earnings_transcripts(self.ticker, num_quarters=num_quarters)

        financials, transcripts = await asyncio.gather(
            financials_task, transcripts_task, return_exceptions=True
        )

        financials = financials if isinstance(financials, dict) else None
        transcripts = transcripts if isinstance(transcripts, list) else []

        self.logger.info(
            f"Narrative: fetched financials ({bool(financials)}) and "
            f"{len(transcripts)} transcripts for {self.ticker}"
        )

        return {
            "financials": financials,
            "transcripts": transcripts,
            "agent_results": self.agent_results,
        }

    async def analyze(self, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        financials = raw_data.get("financials")
        transcripts = raw_data.get("transcripts", [])
        num_years = self.config.get("NARRATIVE_YEARS", 3)

        available_years = self._extract_available_years(financials)
        completeness = self._compute_data_completeness(financials, transcripts, num_years)
        sources = self._get_data_sources(financials, transcripts)

        if not available_years:
            return self._empty_result(completeness, sources)

        # Pass 1: Extract per-year facts
        try:
            pass1_prompt = self._build_pass1_prompt(financials, transcripts, available_years)
            pass1_response = await self._call_llm(pass1_prompt)
            extracted_facts = self._parse_llm_response(pass1_response)
        except Exception as e:
            self.logger.warning(f"Narrative Pass 1 failed for {self.ticker}: {e}")
            return self._empty_result(completeness, sources)

        # Pass 2: Synthesize narrative
        try:
            pass2_prompt = self._build_pass2_prompt(extracted_facts, self.ticker)
            pass2_response = await self._call_llm(pass2_prompt)
            narrative_raw = self._parse_llm_response(pass2_response)
        except Exception as e:
            self.logger.warning(f"Narrative Pass 2 failed for {self.ticker}: {e}, using Pass 1 fallback")
            return self._pass1_fallback(extracted_facts, available_years, completeness, sources)

        # Guardrails will be added in Task 3 (validate_narrative_output)
        narrative_raw["years_covered"] = len(available_years)
        narrative_raw["data_completeness"] = completeness
        narrative_raw["data_sources_used"] = sources
        return narrative_raw

    # --- Year Extraction ---------------------------------------------------------

    def _extract_available_years(self, financials: Optional[Dict[str, Any]]) -> List[int]:
        """Extract sorted list of unique years from income statement data."""
        if not financials:
            return []
        income = financials.get("income_statement", [])
        if not income:
            return []
        years = set()
        for record in income:
            fy = record.get("fiscal_year")
            if fy:
                years.add(int(fy))
            else:
                date_str = record.get("period_ending", "")
                if date_str:
                    try:
                        years.add(datetime.fromisoformat(date_str.replace("Z", "")).year)
                    except (ValueError, TypeError):
                        pass
        return sorted(years)

    # --- Data Completeness -------------------------------------------------------

    def _compute_data_completeness(
        self,
        financials: Optional[Dict[str, Any]],
        transcripts: List[Dict[str, Any]],
        num_years_requested: int,
    ) -> float:
        """Compute data completeness score (0.0-1.0)."""
        score = 0.0

        # Financial coverage (0.60 weight)
        years_available = len(self._extract_available_years(financials))
        if num_years_requested > 0 and years_available > 0:
            financial_coverage = min(years_available / num_years_requested, 1.0)
            score += financial_coverage * 0.60

        # Transcript coverage (0.30 weight)
        if transcripts and len(transcripts) > 0:
            expected_quarters = num_years_requested * 4
            transcript_coverage = min(len(transcripts) / expected_quarters, 1.0)
            score += transcript_coverage * 0.30

        # Fundamentals context (0.10 weight)
        fund_result = self.agent_results.get("fundamentals", {})
        if isinstance(fund_result, dict) and fund_result.get("success") and fund_result.get("data"):
            score += 0.10

        return round(score, 2)

    def _get_data_sources(
        self,
        financials: Optional[Dict[str, Any]],
        transcripts: List[Dict[str, Any]],
    ) -> List[str]:
        """Get list of data sources used."""
        sources = []
        if financials:
            sources.append("financials")
        if transcripts:
            sources.append("transcripts")
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

    # --- LLM Prompts -------------------------------------------------------------

    def _build_pass1_prompt(
        self,
        financials: Optional[Dict[str, Any]],
        transcripts: List[Dict[str, Any]],
        available_years: List[int],
    ) -> str:
        """Build Pass 1 fact extraction prompt."""
        # Format income statements
        income = financials.get("income_statement", []) if financials else []
        income_str = ""
        for record in income:
            fy = record.get("fiscal_year", "?")
            rev = record.get("revenue")
            rev_str = f"${rev/1e9:.1f}B" if rev else "N/A"
            gp = record.get("gross_profit")
            gp_str = f"${gp/1e9:.1f}B" if gp else "N/A"
            oi = record.get("operating_income")
            oi_str = f"${oi/1e9:.1f}B" if oi else "N/A"
            ni = record.get("net_income")
            ni_str = f"${ni/1e9:.1f}B" if ni else "N/A"
            rd = record.get("research_and_development")
            rd_str = f"${rd/1e9:.1f}B" if rd else "N/A"
            income_str += f"  FY{fy}: Revenue {rev_str} | Gross Profit {gp_str} | Operating Income {oi_str} | Net Income {ni_str} | R&D {rd_str}\n"

        # Format transcript excerpts (limit per transcript to keep tokens manageable)
        transcript_str = ""
        for t in transcripts[:8]:  # Cap at 8 quarters
            q, y = t.get("quarter", "?"), t.get("year", "?")
            content = t.get("content", "")[:2000]  # Truncate each transcript
            transcript_str += f"\n  --- Q{q}/{y} ---\n  {content}\n"

        # Fundamentals context
        fund_data = self._get_agent_data("fundamentals") or {}
        company = fund_data.get("company_name", self.ticker)
        sector = fund_data.get("sector", "N/A")
        desc = fund_data.get("business_description", "")

        years_range = f"{available_years[0]}-{available_years[-1]}" if len(available_years) > 1 else str(available_years[0])

        return f"""You are a senior equity research analyst extracting key facts from multi-year financial data for {self.ticker} ({company}).

IMPORTANT RULES:
- Only extract facts from the provided data. Do NOT infer events not mentioned.
- For inflection_quarters, only flag quarters where something MATERIALLY changed — not routine quarters.
- Be specific with numbers — cite revenue, margins, growth rates.

Return a JSON object with EXACTLY these keys — no markdown, no explanation, just raw JSON:

{{
  "per_year": [
    {{
      "year": 2024,
      "revenue": "$XB",
      "revenue_growth": "X%",
      "gross_margin": "X%",
      "operating_margin": "X%",
      "key_events": ["2-4 material events"],
      "management_themes": ["2-4 recurring themes from earnings calls"],
      "capital_moves": ["significant capital allocation decisions"],
      "inflection_quarters": [
        {{"quarter": "QX'YY", "event": "one sentence describing what changed"}}
      ]
    }}
  ],
  "cross_year_themes": ["3-5 themes that span multiple years"]
}}

--- COMPANY ---
{company} | Sector: {sector}
{desc}

--- INCOME STATEMENTS ({years_range}) ---
{income_str}
--- EARNINGS CALL EXCERPTS ---
{transcript_str}
"""

    def _build_pass2_prompt(self, extracted_facts: Dict[str, Any], ticker: str) -> str:
        """Build Pass 2 narrative synthesis prompt."""
        facts_json = json.dumps(extracted_facts, indent=2)
        return f"""You are a senior equity analyst who has covered {ticker} for years. Write the narrative that connects these financial results and management commentary into a coherent investment story.

Rules:
1. Every claim must trace to the extracted facts. Do not introduce new data.
2. Narrative chapters must span MULTIPLE years — single-year themes belong in year sections, not chapters.
3. Quarterly inflections: only include genuinely significant quarters (0-2 per year).
4. Year sections should be chronological (oldest to newest).
5. The company_arc should read like the opening paragraph of a long-form equity research piece.

Return a JSON object with EXACTLY these keys — no markdown, no explanation, just raw JSON:

{{
  "company_arc": "3-5 sentence overarching story connecting the years",
  "year_sections": [
    {{
      "year": 2024,
      "headline": "One-line summary of this year",
      "revenue_trajectory": "Revenue story with numbers",
      "margin_story": "Margin expansion/compression with numbers",
      "strategic_moves": ["key strategic actions"],
      "management_commentary": "Key themes from management",
      "capital_allocation": "Buybacks, dividends, capex, debt",
      "quarterly_inflections": [
        {{"quarter": "QX'YY", "headline": "One line", "details": "2-3 sentences", "impact": "positive|negative|pivotal"}}
      ]
    }}
  ],
  "narrative_chapters": [
    {{
      "title": "Thematic title spanning years",
      "years_covered": "YYYY-YYYY",
      "narrative": "3-5 sentence thematic narrative",
      "evidence": ["2-4 supporting data points from the facts"]
    }}
  ],
  "key_inflection_points": ["Top 3-5 moments that changed the trajectory"],
  "current_chapter": "1-2 sentences on where the company is now in its story"
}}

--- EXTRACTED FACTS ---

{facts_json}
"""

    # --- LLM Call ----------------------------------------------------------------

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

    # --- Response Parsing --------------------------------------------------------

    @staticmethod
    def _parse_llm_response(raw: str) -> Dict[str, Any]:
        """Parse LLM JSON response, stripping markdown fences if present."""
        text = raw.strip()
        if text.startswith("```"):
            text = re.sub(r"^```(?:json)?\s*\n?", "", text)
            text = re.sub(r"\n?```\s*$", "", text)
        return json.loads(text)

    # --- Fallback Results --------------------------------------------------------

    def _empty_result(self, completeness: float, sources: List[str]) -> Dict[str, Any]:
        """Return empty result when no historical data is available."""
        return {
            "company_arc": f"Insufficient historical data to construct a financial narrative for {self.ticker}.",
            "year_sections": [],
            "narrative_chapters": [],
            "key_inflection_points": [],
            "current_chapter": "",
            "years_covered": 0,
            "data_completeness": completeness,
            "data_sources_used": sources,
            "error": "No multi-year financial data available.",
        }

    def _pass1_fallback(
        self,
        extracted_facts: Dict[str, Any],
        available_years: List[int],
        completeness: float,
        sources: List[str],
    ) -> Dict[str, Any]:
        """Fallback when Pass 2 fails — surface extracted facts as year sections."""
        year_sections = []
        for py in extracted_facts.get("per_year", []):
            year_sections.append({
                "year": py.get("year", 0),
                "headline": f"FY{py.get('year', '?')}: Revenue {py.get('revenue', 'N/A')}",
                "revenue_trajectory": f"Revenue: {py.get('revenue', 'N/A')}, growth: {py.get('revenue_growth', 'N/A')}",
                "margin_story": f"Gross margin: {py.get('gross_margin', 'N/A')}, operating margin: {py.get('operating_margin', 'N/A')}",
                "strategic_moves": py.get("key_events", []),
                "management_commentary": "; ".join(py.get("management_themes", [])),
                "capital_allocation": "; ".join(py.get("capital_moves", [])),
                "quarterly_inflections": [],
            })
        return {
            "company_arc": f"Partial narrative for {self.ticker} — fact extraction succeeded but narrative synthesis failed.",
            "year_sections": year_sections,
            "narrative_chapters": [],
            "key_inflection_points": [],
            "current_chapter": "",
            "years_covered": len(available_years),
            "data_completeness": completeness,
            "data_sources_used": sources,
            "extracted_facts": extracted_facts,
            "pass2_failed": True,
        }
