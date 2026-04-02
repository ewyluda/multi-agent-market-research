# Risk Diff Agent Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a two-pass LLM hybrid agent that fetches SEC 10-K/10-Q filing risk factor sections via FMP metadata + EDGAR full text, compares them across periods to detect new, removed, escalated, and de-escalated risks, and produces both a risk inventory (always) and a period-over-period diff (when 2+ filings available).

**Architecture:** RiskDiffAgent inherits BaseAgent, takes agent_results in constructor and also fetches its own filing data in `fetch_data()` via `_data_provider` (FMP for metadata, EDGAR for HTML). HTML parsing uses BeautifulSoup + regex fast path with LLM fallback. Two-pass LLM: Pass 1 ("The Cataloger") extracts risk inventory per filing concurrently, Pass 2 ("The Comparator") diffs inventories. Data gate: 0 filings = empty, 1 = inventory only, 2+ = full diff. Runs parallel with solution+thesis+earnings_review+narrative+tag_extractor in synthesis phase via asyncio.gather().

**Tech Stack:** Python, Pydantic, beautifulsoup4, aiohttp, anthropic/openai SDKs, pytest

**Spec:** `docs/superpowers/specs/2026-04-02-risk-diff-agent-design.md`

---

### Task 1: Pydantic Models + beautifulsoup4 dependency

**Files:**
- Modify: `src/models.py`
- Modify: `requirements.txt`
- Create: `tests/test_agents/test_risk_diff_agent.py`

- [ ] **Step 1: Create test file with model validation tests**

Create `tests/test_agents/test_risk_diff_agent.py`:

```python
"""Tests for RiskDiffAgent — models, EDGAR integration, HTML parsing, LLM flow, guardrails."""

import pytest
from pydantic import ValidationError
from src.models import RiskTopic, RiskChange, RiskDiffOutput


class TestRiskDiffModels:
    """Pydantic model validation tests."""

    def test_risk_topic_valid(self):
        rt = RiskTopic(
            topic="Supply Chain Concentration",
            severity="high",
            summary="Company depends on 3 suppliers for 80% of components.",
            text_excerpt="We rely on a limited number of suppliers...",
        )
        assert rt.severity == "high"
        assert rt.topic == "Supply Chain Concentration"

    def test_risk_change_valid(self):
        rc = RiskChange(
            risk_topic="Supply Chain Concentration",
            change_type="new",
            severity="high",
            current_text_excerpt="We now rely on a single supplier...",
            prior_text_excerpt="",
            analysis="New single-source dependency introduces material risk.",
        )
        assert rc.change_type == "new"
        assert rc.prior_text_excerpt == ""

    def test_risk_change_escalated(self):
        rc = RiskChange(
            risk_topic="Regulatory Risk",
            change_type="escalated",
            severity="high",
            current_text_excerpt="Material adverse effect on operations is likely...",
            prior_text_excerpt="Could impact our results...",
            analysis="Language escalated from 'could impact' to 'material adverse effect'.",
        )
        assert rc.change_type == "escalated"

    def test_risk_diff_output_full_diff(self):
        output = RiskDiffOutput(
            new_risks=[
                RiskChange(
                    risk_topic="AI Regulation",
                    change_type="new",
                    severity="medium",
                    current_text_excerpt="New AI regulations may...",
                    prior_text_excerpt="",
                    analysis="Newly disclosed risk from emerging AI regulation.",
                )
            ],
            removed_risks=[],
            changed_risks=[],
            risk_score=65.0,
            risk_score_delta=5.0,
            top_emerging_threats=["AI regulation exposure", "China supply chain"],
            summary="Risk profile moderately elevated due to new AI regulatory disclosure.",
            current_risk_inventory=[
                RiskTopic(
                    topic="AI Regulation",
                    severity="medium",
                    summary="New AI rules could affect operations.",
                    text_excerpt="New AI regulations may...",
                )
            ],
            filings_compared=[
                {"type": "10-K", "date": "2025-02-15", "accession_number": "0001234-25-000001"},
                {"type": "10-K", "date": "2024-02-15", "accession_number": "0001234-24-000001"},
            ],
            has_diff=True,
            extraction_methods=["pattern", "pattern"],
            data_completeness=0.85,
            data_sources_used=["fmp_filings", "edgar_html"],
        )
        assert output.has_diff is True
        assert len(output.new_risks) == 1
        assert output.risk_score == 65.0

    def test_risk_diff_output_inventory_only(self):
        output = RiskDiffOutput(
            new_risks=[],
            removed_risks=[],
            changed_risks=[],
            risk_score=50.0,
            risk_score_delta=0.0,
            top_emerging_threats=[],
            summary="Single filing available; risk inventory only.",
            current_risk_inventory=[
                RiskTopic(
                    topic="Market Competition",
                    severity="medium",
                    summary="Intense competition in key markets.",
                    text_excerpt="We face intense competition...",
                )
            ],
            filings_compared=[
                {"type": "10-K", "date": "2025-02-15", "accession_number": "0001234-25-000001"},
            ],
            has_diff=False,
            extraction_methods=["pattern"],
            data_completeness=0.40,
            data_sources_used=["fmp_filings", "edgar_html"],
        )
        assert output.has_diff is False
        assert len(output.new_risks) == 0
        assert output.risk_score_delta == 0.0

    def test_risk_diff_output_completeness_bounds(self):
        with pytest.raises(ValidationError):
            RiskDiffOutput(
                new_risks=[], removed_risks=[], changed_risks=[],
                risk_score=50.0, risk_score_delta=0.0,
                top_emerging_threats=[], summary="x",
                current_risk_inventory=[],
                filings_compared=[], has_diff=False,
                extraction_methods=[], data_completeness=1.5,
                data_sources_used=[],
            )

    def test_risk_diff_output_empty(self):
        output = RiskDiffOutput(
            new_risks=[], removed_risks=[], changed_risks=[],
            risk_score=0.0, risk_score_delta=0.0,
            top_emerging_threats=[], summary="No filings available.",
            current_risk_inventory=[],
            filings_compared=[], has_diff=False,
            extraction_methods=[], data_completeness=0.0,
            data_sources_used=[],
        )
        assert output.data_completeness == 0.0
        assert output.current_risk_inventory == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_agents/test_risk_diff_agent.py -v`
Expected: FAIL — `ImportError: cannot import name 'RiskTopic' from 'src.models'`

- [ ] **Step 3: Add Pydantic models to src/models.py**

Add at the end of `src/models.py`, after the Tag Extractor Agent models section:

```python
# ── Risk Diff Agent models ───────────────────────────────────────────────────


class RiskTopic(BaseModel):
    """A single risk topic from a SEC filing risk factors section."""
    topic: str = Field(..., description="Risk topic name, e.g. 'Supply Chain Concentration'")
    severity: str = Field(..., description="Severity: high, medium, or low")
    summary: str = Field(..., description="2-3 sentence description of the risk")
    text_excerpt: str = Field(..., description="Brief excerpt from the filing text")


class RiskChange(BaseModel):
    """A detected change in risk between two filing periods."""
    risk_topic: str = Field(..., description="Risk topic name")
    change_type: str = Field(..., description="Change type: new, removed, escalated, de-escalated, reworded")
    severity: str = Field(..., description="Severity: high, medium, or low")
    current_text_excerpt: str = Field(..., description="Excerpt from current filing")
    prior_text_excerpt: str = Field(default="", description="Excerpt from prior filing (empty if new)")
    analysis: str = Field(..., description="Why this change matters for investors")


class RiskDiffOutput(BaseModel):
    """Complete risk diff output — risk inventory + period-over-period changes."""
    # Diff results (empty if only 1 filing available)
    new_risks: List[RiskChange] = Field(default=[], description="Risks not present in prior filing")
    removed_risks: List[RiskChange] = Field(default=[], description="Risks removed since prior filing")
    changed_risks: List[RiskChange] = Field(default=[], description="Risks that changed severity or language")
    risk_score: float = Field(default=0.0, description="Composite risk score 0-100")
    risk_score_delta: float = Field(default=0.0, description="Change from prior period")
    top_emerging_threats: List[str] = Field(default=[], description="3-5 most actionable new/escalated risks")
    summary: str = Field(default="", description="2-3 sentence risk landscape summary")

    # Risk inventory (always populated from latest filing)
    current_risk_inventory: List[RiskTopic] = Field(default=[], description="Risk topics from latest filing")

    # Metadata
    filings_compared: List[Dict[str, Any]] = Field(default=[], description="Filing metadata per filing used")
    has_diff: bool = Field(default=False, description="True if 2+ filings were compared")
    extraction_methods: List[str] = Field(default=[], description="'pattern' or 'llm_fallback' per filing")
    data_completeness: float = Field(default=0.0, ge=0.0, le=1.0, description="0.0-1.0 data quality score")
    data_sources_used: List[str] = Field(default=[], description="Data sources that contributed")
```

- [ ] **Step 4: Add beautifulsoup4 to requirements.txt**

Add to `requirements.txt` after the last line:

```
beautifulsoup4>=4.12.0
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m pytest tests/test_agents/test_risk_diff_agent.py::TestRiskDiffModels -v`
Expected: All 8 tests PASS

- [ ] **Step 6: Commit**

```bash
git add src/models.py requirements.txt tests/test_agents/test_risk_diff_agent.py
git commit -m "feat(risk-diff): add Pydantic models for RiskDiffOutput schema + beautifulsoup4 dep"
```

---

### Task 2: EDGAR Integration in data_provider.py

**Files:**
- Modify: `src/data_provider.py`
- Modify: `tests/test_agents/test_risk_diff_agent.py`

- [ ] **Step 1: Write EDGAR integration tests**

Append to `tests/test_agents/test_risk_diff_agent.py`:

```python
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock
import aiohttp
import json as json_module
from src.data_provider import OpenBBDataProvider


MOCK_COMPANY_TICKERS_JSON = {
    "0": {"cik_str": 320193, "ticker": "AAPL", "title": "Apple Inc."},
    "1": {"cik_str": 789019, "ticker": "MSFT", "title": "MICROSOFT CORP"},
    "2": {"cik_str": 1018724, "ticker": "AMZN", "title": "AMAZON COM INC"},
}

MOCK_FMP_FILINGS_RESPONSE = [
    {
        "symbol": "AAPL",
        "fillingDate": "2025-02-15",
        "acceptedDate": "2025-02-15 06:30:00",
        "cik": "0000320193",
        "type": "10-K",
        "link": "https://www.sec.gov/Archives/edgar/data/320193/000032019325000001/aapl-20250101.htm",
        "finalLink": "https://www.sec.gov/Archives/edgar/data/320193/000032019325000001/aapl-20250101.htm",
    },
    {
        "symbol": "AAPL",
        "fillingDate": "2024-02-15",
        "acceptedDate": "2024-02-15 06:30:00",
        "cik": "0000320193",
        "type": "10-K",
        "link": "https://www.sec.gov/Archives/edgar/data/320193/000032019324000001/aapl-20240101.htm",
        "finalLink": "https://www.sec.gov/Archives/edgar/data/320193/000032019324000001/aapl-20240101.htm",
    },
]

MOCK_FILING_HTML = """
<html><body>
<h2>Item 1. Business</h2>
<p>We design and sell consumer electronics.</p>
<h2>Item 1A. Risk Factors</h2>
<p>The following risk factors could materially affect our business:</p>
<p><b>Supply Chain Risks.</b> We rely on a limited number of suppliers for key components.
A disruption in supply could have a material adverse effect on our results of operations.</p>
<p><b>Regulatory Risks.</b> Changes in laws and regulations could impact our operations.
We are subject to various government regulations in the jurisdictions in which we operate.</p>
<p><b>Competition.</b> We face intense competition in all our product categories.
Our competitors may develop superior products or achieve lower costs.</p>
<h2>Item 1B. Unresolved Staff Comments</h2>
<p>None.</p>
</body></html>
"""

MOCK_FILING_HTML_NO_RISK_SECTION = """
<html><body>
<h2>Item 1. Business</h2>
<p>We design and sell consumer electronics.</p>
<h2>Item 2. Properties</h2>
<p>Our headquarters is in Cupertino.</p>
</body></html>
"""


class TestResolveCik:
    """Tests for _resolve_cik() in data provider."""

    @pytest.mark.asyncio
    async def test_resolve_cik_found(self):
        dp = OpenBBDataProvider({"SEC_EDGAR_USER_AGENT": "Test/1.0 (test@test.com)"})

        mock_resp = AsyncMock()
        mock_resp.status = 200
        mock_resp.json = AsyncMock(return_value=MOCK_COMPANY_TICKERS_JSON)
        mock_resp.__aenter__ = AsyncMock(return_value=mock_resp)
        mock_resp.__aexit__ = AsyncMock(return_value=False)

        mock_session = AsyncMock()
        mock_session.get = MagicMock(return_value=mock_resp)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        with patch("aiohttp.ClientSession", return_value=mock_session):
            cik = await dp._resolve_cik("AAPL")

        assert cik == "0000320193"

    @pytest.mark.asyncio
    async def test_resolve_cik_not_found(self):
        dp = OpenBBDataProvider({"SEC_EDGAR_USER_AGENT": "Test/1.0 (test@test.com)"})

        mock_resp = AsyncMock()
        mock_resp.status = 200
        mock_resp.json = AsyncMock(return_value=MOCK_COMPANY_TICKERS_JSON)
        mock_resp.__aenter__ = AsyncMock(return_value=mock_resp)
        mock_resp.__aexit__ = AsyncMock(return_value=False)

        mock_session = AsyncMock()
        mock_session.get = MagicMock(return_value=mock_resp)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        with patch("aiohttp.ClientSession", return_value=mock_session):
            cik = await dp._resolve_cik("ZZZZ")

        assert cik is None

    @pytest.mark.asyncio
    async def test_resolve_cik_cached(self):
        dp = OpenBBDataProvider({"SEC_EDGAR_USER_AGENT": "Test/1.0 (test@test.com)"})
        # Pre-populate cache
        dp._cik_cache = {"AAPL": "0000320193"}

        cik = await dp._resolve_cik("AAPL")
        assert cik == "0000320193"


class TestGetSecFilingMetadata:
    """Tests for get_sec_filing_metadata() in data provider."""

    @pytest.mark.asyncio
    async def test_get_filing_metadata_success(self):
        dp = OpenBBDataProvider({
            "FMP_API_KEY": "test_key",
            "SEC_EDGAR_USER_AGENT": "Test/1.0 (test@test.com)",
        })

        mock_resp = AsyncMock()
        mock_resp.status = 200
        mock_resp.json = AsyncMock(return_value=MOCK_FMP_FILINGS_RESPONSE)
        mock_resp.__aenter__ = AsyncMock(return_value=mock_resp)
        mock_resp.__aexit__ = AsyncMock(return_value=False)

        mock_session = AsyncMock()
        mock_session.get = MagicMock(return_value=mock_resp)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        with patch("aiohttp.ClientSession", return_value=mock_session):
            filings = await dp.get_sec_filing_metadata("AAPL", filing_type="10-K", limit=3)

        assert len(filings) == 2
        assert filings[0]["filing_type"] == "10-K"
        assert filings[0]["filing_date"] == "2025-02-15"
        assert "filing_url" in filings[0]

    @pytest.mark.asyncio
    async def test_get_filing_metadata_no_api_key(self):
        dp = OpenBBDataProvider({"SEC_EDGAR_USER_AGENT": "Test/1.0 (test@test.com)"})
        filings = await dp.get_sec_filing_metadata("AAPL")
        assert filings == []


class TestParseRiskSection:
    """Tests for _parse_risk_section() static method."""

    def test_parse_risk_section_success(self):
        dp = OpenBBDataProvider({})
        result = dp._parse_risk_section(MOCK_FILING_HTML)
        assert result is not None
        assert "Supply Chain" in result
        assert "Competition" in result
        assert "Unresolved Staff Comments" not in result

    def test_parse_risk_section_no_match(self):
        dp = OpenBBDataProvider({})
        result = dp._parse_risk_section(MOCK_FILING_HTML_NO_RISK_SECTION)
        assert result is None

    def test_parse_risk_section_empty_html(self):
        dp = OpenBBDataProvider({})
        result = dp._parse_risk_section("")
        assert result is None

    def test_parse_risk_section_too_short(self):
        dp = OpenBBDataProvider({})
        html = "<html><body><h2>Item 1A. Risk Factors</h2><p>Short.</p><h2>Item 1B.</h2></body></html>"
        result = dp._parse_risk_section(html)
        assert result is None  # Too short (<200 chars)


class TestGetSecFilingSection:
    """Tests for get_sec_filing_section()."""

    @pytest.mark.asyncio
    async def test_get_filing_section_pattern_path(self):
        dp = OpenBBDataProvider({"SEC_EDGAR_USER_AGENT": "Test/1.0 (test@test.com)"})

        mock_resp = AsyncMock()
        mock_resp.status = 200
        mock_resp.text = AsyncMock(return_value=MOCK_FILING_HTML)
        mock_resp.__aenter__ = AsyncMock(return_value=mock_resp)
        mock_resp.__aexit__ = AsyncMock(return_value=False)

        mock_session = AsyncMock()
        mock_session.get = MagicMock(return_value=mock_resp)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        with patch("aiohttp.ClientSession", return_value=mock_session):
            result = await dp.get_sec_filing_section(
                "AAPL",
                "https://www.sec.gov/Archives/edgar/data/320193/filing.htm",
                section="1A",
            )

        assert result is not None
        assert result["extraction_method"] == "pattern"
        assert result["char_count"] > 200
        assert "Supply Chain" in result["section_text"]

    @pytest.mark.asyncio
    async def test_get_filing_section_http_error(self):
        dp = OpenBBDataProvider({"SEC_EDGAR_USER_AGENT": "Test/1.0 (test@test.com)"})

        mock_resp = AsyncMock()
        mock_resp.status = 404
        mock_resp.__aenter__ = AsyncMock(return_value=mock_resp)
        mock_resp.__aexit__ = AsyncMock(return_value=False)

        mock_session = AsyncMock()
        mock_session.get = MagicMock(return_value=mock_resp)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        with patch("aiohttp.ClientSession", return_value=mock_session):
            result = await dp.get_sec_filing_section(
                "AAPL",
                "https://www.sec.gov/Archives/edgar/data/320193/filing.htm",
                section="1A",
            )

        assert result is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_agents/test_risk_diff_agent.py::TestResolveCik tests/test_agents/test_risk_diff_agent.py::TestGetSecFilingMetadata tests/test_agents/test_risk_diff_agent.py::TestParseRiskSection tests/test_agents/test_risk_diff_agent.py::TestGetSecFilingSection -v`
Expected: FAIL — `AttributeError: 'OpenBBDataProvider' object has no attribute '_resolve_cik'`

- [ ] **Step 3: Implement EDGAR methods in data_provider.py**

Add at the end of `src/data_provider.py` (after `_sync_get_peers`), plus add `import re` at the top if not present:

```python
    # ------------------------------------------------------------------
    # SEC EDGAR Integration
    # ------------------------------------------------------------------

    TTL_SEC_FILINGS = 86400  # 24 hours

    async def _resolve_cik(self, ticker: str) -> Optional[str]:
        """Resolve ticker to zero-padded SEC CIK number.

        Uses https://www.sec.gov/files/company_tickers.json — a free,
        unthrottled endpoint mapping tickers to CIK numbers.

        Returns:
            Zero-padded CIK string (e.g. '0000320193'), or None if not found.
        """
        # Check in-memory CIK cache
        if not hasattr(self, "_cik_cache"):
            self._cik_cache: Dict[str, str] = {}
        ticker_upper = ticker.upper()
        if ticker_upper in self._cik_cache:
            return self._cik_cache[ticker_upper]

        url = "https://www.sec.gov/files/company_tickers.json"
        user_agent = self._config.get(
            "SEC_EDGAR_USER_AGENT",
            "MarketResearch/1.0 (research@example.com)",
        )
        try:
            async with aiohttp.ClientSession() as session:
                headers = {"User-Agent": user_agent}
                async with session.get(
                    url, headers=headers, timeout=aiohttp.ClientTimeout(total=10)
                ) as resp:
                    if resp.status != 200:
                        logger.warning("SEC company_tickers.json returned %d", resp.status)
                        return None
                    data = await resp.json()
                    for entry in data.values():
                        if entry.get("ticker", "").upper() == ticker_upper:
                            cik_raw = entry.get("cik_str")
                            if cik_raw is not None:
                                cik_padded = str(cik_raw).zfill(10)
                                self._cik_cache[ticker_upper] = cik_padded
                                return cik_padded
        except Exception as e:
            logger.warning("CIK resolution failed for %s: %s", ticker, e)
        return None

    async def get_sec_filing_metadata(
        self,
        ticker: str,
        filing_type: str = "10-K",
        limit: int = 3,
    ) -> List[Dict[str, Any]]:
        """Fetch SEC filing metadata from FMP.

        Uses ``/stable/sec-filings?symbol={ticker}&type={filing_type}&limit={limit}``.

        Returns:
            List of dicts with keys: filing_type, filing_date, filing_url, accession_number.
            Empty list on failure.
        """
        ck = self._cache_key("sec_filing_metadata", ticker, filing_type=filing_type, limit=limit)
        cached = self._cache_get(ck)
        if cached is not None:
            return cached

        fmp_key = self._config.get("FMP_API_KEY", "")
        if not fmp_key:
            logger.warning("No FMP_API_KEY — cannot fetch SEC filing metadata")
            return []

        url = (
            f"https://financialmodelingprep.com/stable/sec-filings"
            f"?symbol={ticker.upper()}&type={filing_type}&limit={limit}&apikey={fmp_key}"
        )
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    url, timeout=aiohttp.ClientTimeout(total=15)
                ) as resp:
                    if resp.status != 200:
                        logger.warning("FMP sec-filings returned %d for %s", resp.status, ticker)
                        return []
                    raw = await resp.json()
                    if not isinstance(raw, list):
                        return []

                    filings = []
                    for item in raw:
                        filing_url = item.get("finalLink") or item.get("link", "")
                        filings.append({
                            "filing_type": item.get("type", filing_type),
                            "filing_date": item.get("fillingDate", ""),
                            "filing_url": filing_url,
                            "accession_number": item.get("cik", ""),
                        })
                    self._cache_put(ck, filings, self.TTL_SEC_FILINGS)
                    return filings
        except Exception as e:
            logger.warning("FMP sec-filings fetch failed for %s: %s", ticker, e)
            return []

    async def get_sec_filing_section(
        self,
        ticker: str,
        filing_url: str,
        section: str = "1A",
    ) -> Optional[Dict[str, Any]]:
        """Fetch a SEC filing HTML and extract a section (default: Item 1A Risk Factors).

        Two-tier extraction:
            1. Fast path: BeautifulSoup + regex for section headers.
            2. Returns None if fast path fails (caller handles LLM fallback).

        Returns:
            Dict with section_text, extraction_method, char_count — or None on failure.
        """
        user_agent = self._config.get(
            "SEC_EDGAR_USER_AGENT",
            "MarketResearch/1.0 (research@example.com)",
        )
        try:
            async with aiohttp.ClientSession() as session:
                headers = {"User-Agent": user_agent}
                async with session.get(
                    filing_url,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=30),
                ) as resp:
                    if resp.status != 200:
                        logger.warning(
                            "EDGAR filing fetch returned %d for %s (%s)",
                            resp.status, ticker, filing_url,
                        )
                        return None
                    html = await resp.text()
        except Exception as e:
            logger.warning("EDGAR filing fetch failed for %s: %s", ticker, e)
            return None

        # Fast path: pattern matching
        section_text = self._parse_risk_section(html)
        if section_text:
            return {
                "section_text": section_text,
                "extraction_method": "pattern",
                "char_count": len(section_text),
            }

        # Fast path failed — return None so caller can try LLM fallback
        # Also provide stripped text for the LLM fallback
        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html, "html.parser")
            clean_text = soup.get_text(separator="\n")
            # Truncate to 30K chars for LLM fallback
            return {
                "section_text": None,
                "extraction_method": "needs_llm_fallback",
                "char_count": 0,
                "raw_text_for_fallback": clean_text[:30000],
            }
        except Exception:
            return None

    @staticmethod
    def _parse_risk_section(html: str) -> Optional[str]:
        """Extract Item 1A Risk Factors section from filing HTML.

        Uses BeautifulSoup to get plain text, then regex to find
        the section boundaries.

        Returns:
            Extracted section text, or None if parsing fails.
        """
        if not html or len(html) < 100:
            return None
        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html, "html.parser")
            text = soup.get_text(separator="\n")

            # Find Item 1A header
            import re as _re
            pattern = r"(?:Item\s*1A[\.\s\-\u2014:]*Risk\s*Factors)"
            match = _re.search(pattern, text, _re.IGNORECASE)
            if not match:
                return None

            start = match.start()

            # Find next Item header (Item 1B, Item 2, etc.)
            end_pattern = r"(?:Item\s*(?:1B|2)[\.\s\-\u2014:])"
            end_match = _re.search(end_pattern, text[start + 100:], _re.IGNORECASE)
            end = (start + 100 + end_match.start()) if end_match else start + 50000

            section = text[start:end].strip()
            return section if len(section) > 200 else None
        except Exception:
            return None
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_agents/test_risk_diff_agent.py::TestResolveCik tests/test_agents/test_risk_diff_agent.py::TestGetSecFilingMetadata tests/test_agents/test_risk_diff_agent.py::TestParseRiskSection tests/test_agents/test_risk_diff_agent.py::TestGetSecFilingSection -v`
Expected: All 11 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/data_provider.py tests/test_agents/test_risk_diff_agent.py
git commit -m "feat(risk-diff): add EDGAR integration — _resolve_cik, get_sec_filing_metadata, get_sec_filing_section, _parse_risk_section"
```

---

### Task 3: RiskDiffAgent Skeleton — Data Fetching, HTML Parsing, Two-Pass LLM

**Files:**
- Create: `src/agents/risk_diff_agent.py`
- Modify: `tests/test_agents/test_risk_diff_agent.py`

- [ ] **Step 1: Write agent data fetching and completeness tests**

Append to `tests/test_agents/test_risk_diff_agent.py`:

```python
from src.agents.risk_diff_agent import RiskDiffAgent


def _make_agent_results():
    """Build mock agent_results for context."""
    return {
        "fundamentals": {
            "success": True,
            "data": {
                "company_name": "Apple Inc.",
                "sector": "Technology",
                "revenue": 383e9,
            },
        },
    }


def _make_mock_filing_metadata(count=2):
    """Build mock filing metadata list."""
    filings = []
    for i in range(count):
        year = 2025 - i
        filings.append({
            "filing_type": "10-K",
            "filing_date": f"{year}-02-15",
            "filing_url": f"https://www.sec.gov/Archives/edgar/data/320193/{year}/filing.htm",
            "accession_number": f"0000320193-{year}-000001",
        })
    return filings


def _make_mock_filing_section(text=None):
    """Build mock filing section result."""
    section_text = text or (
        "Item 1A. Risk Factors\n\n"
        "Supply Chain Risks. We rely on a limited number of suppliers for key components. "
        "A disruption in supply could have a material adverse effect on our results.\n\n"
        "Regulatory Risks. Changes in laws and regulations could impact our operations. "
        "We are subject to various government regulations.\n\n"
        "Competition. We face intense competition in all our product categories."
    )
    return {
        "section_text": section_text,
        "extraction_method": "pattern",
        "char_count": len(section_text),
    }


class TestRiskDiffDataFetching:
    """Tests for RiskDiffAgent fetch_data()."""

    @pytest.mark.asyncio
    async def test_fetch_data_calls_data_provider(self):
        agent = RiskDiffAgent("AAPL", {"llm_config": {}}, _make_agent_results())
        mock_dp = MagicMock()
        mock_dp.get_sec_filing_metadata = AsyncMock(return_value=_make_mock_filing_metadata(2))
        mock_dp.get_sec_filing_section = AsyncMock(return_value=_make_mock_filing_section())
        agent._data_provider = mock_dp

        result = await agent.fetch_data()

        assert mock_dp.get_sec_filing_metadata.call_count >= 1
        assert "filings" in result
        assert len(result["filings"]) == 2

    @pytest.mark.asyncio
    async def test_fetch_data_no_data_provider(self):
        agent = RiskDiffAgent("AAPL", {"llm_config": {}}, _make_agent_results())
        result = await agent.fetch_data()
        assert result["filings"] == []

    @pytest.mark.asyncio
    async def test_fetch_data_no_filings_found(self):
        agent = RiskDiffAgent("AAPL", {"llm_config": {}}, _make_agent_results())
        mock_dp = MagicMock()
        mock_dp.get_sec_filing_metadata = AsyncMock(return_value=[])
        agent._data_provider = mock_dp

        result = await agent.fetch_data()
        assert result["filings"] == []


class TestRiskDiffCompleteness:
    """Tests for data completeness scoring."""

    def test_full_completeness(self):
        agent = RiskDiffAgent("AAPL", {"llm_config": {}}, _make_agent_results())
        filings = [
            {"filing_type": "10-K", "risk_text": "text", "filing_date": "2025-02-15"},
            {"filing_type": "10-K", "risk_text": "text", "filing_date": "2024-02-15"},
            {"filing_type": "10-Q", "risk_text": "text", "filing_date": "2025-05-15"},
        ]
        score = agent._compute_data_completeness(filings)
        assert score == pytest.approx(1.0, abs=0.01)

    def test_two_10k_no_10q(self):
        agent = RiskDiffAgent("AAPL", {"llm_config": {}}, _make_agent_results())
        filings = [
            {"filing_type": "10-K", "risk_text": "text", "filing_date": "2025-02-15"},
            {"filing_type": "10-K", "risk_text": "text", "filing_date": "2024-02-15"},
        ]
        score = agent._compute_data_completeness(filings)
        # 0.40 + 0.30 + 0.15 (fundamentals context) = 0.85
        assert score == pytest.approx(0.85, abs=0.02)

    def test_single_10k_only(self):
        agent = RiskDiffAgent("AAPL", {"llm_config": {}}, _make_agent_results())
        filings = [
            {"filing_type": "10-K", "risk_text": "text", "filing_date": "2025-02-15"},
        ]
        score = agent._compute_data_completeness(filings)
        # 0.40 + 0.15 = 0.55
        assert score == pytest.approx(0.55, abs=0.02)

    def test_no_filings(self):
        agent = RiskDiffAgent("AAPL", {"llm_config": {}}, _make_agent_results())
        score = agent._compute_data_completeness([])
        # Only fundamentals context = 0.15
        assert score == pytest.approx(0.15, abs=0.02)

    def test_no_context(self):
        agent = RiskDiffAgent("AAPL", {"llm_config": {}}, {})
        score = agent._compute_data_completeness([])
        assert score == pytest.approx(0.0, abs=0.01)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_agents/test_risk_diff_agent.py::TestRiskDiffDataFetching tests/test_agents/test_risk_diff_agent.py::TestRiskDiffCompleteness -v`
Expected: FAIL — `ImportError: cannot import name 'RiskDiffAgent'`

- [ ] **Step 3: Implement RiskDiffAgent**

Create `src/agents/risk_diff_agent.py`:

```python
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
        - 0 filings parsed → empty result
        - 1 filing parsed → risk inventory only (has_diff=False)
        - 2+ filings parsed → full diff

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

        # Data gate: 0 filings → empty
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

        # Data gate: 1 filing → inventory only
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

            return diff_result

        except Exception as e:
            self.logger.warning(f"RiskDiff Pass 2 failed for {self.ticker}: {e}, using Pass 1 fallback")
            return self._pass1_fallback(
                current_inventory, filings_compared, extraction_methods,
                completeness, sources,
            )

    # ─── Pass 1: Risk Inventory ─────────────────────────────────────────────

    async def _run_pass1(self, filing: Dict[str, Any]) -> Dict[str, Any]:
        """Pass 1 — extract risk inventory from one filing's risk section."""
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

    # ─── Pass 2: Risk Diff ──────────────────────────────────────────────────

    async def _run_pass2(
        self,
        current_inventory: Dict[str, Any],
        prior_inventory: Dict[str, Any],
        supplementary_10q: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Pass 2 — diff two risk inventories."""
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

    # ─── LLM Fallback for HTML Parsing ──────────────────────────────────────

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

    # ─── Data Completeness ──────────────────────────────────────────────────

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

    # ─── LLM Call ───────────────────────────────────────────────────────────

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

    # ─── Response Parsing ───────────────────────────────────────────────────

    @staticmethod
    def _parse_llm_response(raw: str) -> Dict[str, Any]:
        """Parse LLM JSON response, stripping markdown fences if present."""
        text = raw.strip()
        if text.startswith("```"):
            text = re.sub(r"^```(?:json)?\s*\n?", "", text)
            text = re.sub(r"\n?```\s*$", "", text)
        return json.loads(text)

    # ─── Fallback Results ───────────────────────────────────────────────────

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
        """Fallback when Pass 2 fails — return inventory with no diff."""
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_agents/test_risk_diff_agent.py::TestRiskDiffDataFetching tests/test_agents/test_risk_diff_agent.py::TestRiskDiffCompleteness -v`
Expected: All 8 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/agents/risk_diff_agent.py tests/test_agents/test_risk_diff_agent.py
git commit -m "feat(risk-diff): add RiskDiffAgent with hybrid EDGAR fetch, two-pass LLM, data completeness"
```

---

### Task 4: Guardrails — validate_risk_diff_output()

**Files:**
- Modify: `src/llm_guardrails.py`
- Modify: `tests/test_agents/test_risk_diff_agent.py`
- Modify: `src/agents/risk_diff_agent.py`

- [ ] **Step 1: Write guardrail tests**

Append to `tests/test_agents/test_risk_diff_agent.py`:

```python
from src.llm_guardrails import validate_risk_diff_output


def _make_valid_risk_diff():
    """Build a valid risk diff output dict."""
    return {
        "new_risks": [
            {
                "risk_topic": "AI Regulation",
                "change_type": "new",
                "severity": "medium",
                "current_text_excerpt": "New AI regulations may...",
                "prior_text_excerpt": "",
                "analysis": "Newly disclosed risk.",
            }
        ],
        "removed_risks": [],
        "changed_risks": [
            {
                "risk_topic": "Supply Chain",
                "change_type": "escalated",
                "severity": "high",
                "current_text_excerpt": "Material adverse effect...",
                "prior_text_excerpt": "Could impact...",
                "analysis": "Language escalated.",
            }
        ],
        "risk_score": 65.0,
        "risk_score_delta": 5.0,
        "top_emerging_threats": ["AI regulation", "Supply chain escalation"],
        "summary": "Risk profile moderately elevated.",
        "current_risk_inventory": [
            {"topic": "AI Regulation", "severity": "medium", "summary": "x", "text_excerpt": "x"},
            {"topic": "Supply Chain", "severity": "high", "summary": "x", "text_excerpt": "x"},
        ],
        "filings_compared": [
            {"type": "10-K", "date": "2025-02-15", "accession_number": "x"},
            {"type": "10-K", "date": "2024-02-15", "accession_number": "y"},
        ],
        "has_diff": True,
        "extraction_methods": ["pattern", "pattern"],
        "data_completeness": 0.85,
        "data_sources_used": ["fmp_filings", "edgar_html"],
    }


class TestRiskDiffGuardrails:
    """Tests for validate_risk_diff_output() in llm_guardrails.py."""

    def test_valid_output_passes(self):
        output = _make_valid_risk_diff()
        validated, warnings = validate_risk_diff_output(output)
        assert validated["risk_score"] == 65.0
        assert isinstance(warnings, list)

    def test_risk_score_clamped_high(self):
        output = _make_valid_risk_diff()
        output["risk_score"] = 150.0
        validated, warnings = validate_risk_diff_output(output)
        assert validated["risk_score"] == 100.0
        assert any("risk_score" in w.lower() for w in warnings)

    def test_risk_score_clamped_low(self):
        output = _make_valid_risk_diff()
        output["risk_score"] = -10.0
        validated, warnings = validate_risk_diff_output(output)
        assert validated["risk_score"] == 0.0
        assert any("risk_score" in w.lower() for w in warnings)

    def test_risk_score_delta_clamped(self):
        output = _make_valid_risk_diff()
        output["risk_score_delta"] = 80.0
        validated, warnings = validate_risk_diff_output(output)
        assert validated["risk_score_delta"] == 50.0
        assert any("delta" in w.lower() for w in warnings)

    def test_invalid_change_type_flagged(self):
        output = _make_valid_risk_diff()
        output["new_risks"][0]["change_type"] = "invented_type"
        validated, warnings = validate_risk_diff_output(output)
        assert any("change_type" in w.lower() for w in warnings)

    def test_invalid_severity_flagged(self):
        output = _make_valid_risk_diff()
        output["changed_risks"][0]["severity"] = "critical"
        validated, warnings = validate_risk_diff_output(output)
        assert any("severity" in w.lower() for w in warnings)

    def test_no_diff_but_has_risks_flagged(self):
        output = _make_valid_risk_diff()
        output["has_diff"] = False
        # Should warn because has_diff=False but diff fields are non-empty
        validated, warnings = validate_risk_diff_output(output)
        assert any("has_diff" in w.lower() or "consistency" in w.lower() for w in warnings)

    def test_no_diff_clean(self):
        output = _make_valid_risk_diff()
        output["has_diff"] = False
        output["new_risks"] = []
        output["removed_risks"] = []
        output["changed_risks"] = []
        validated, warnings = validate_risk_diff_output(output)
        # Should not warn about diff consistency
        assert not any("has_diff" in w.lower() for w in warnings)

    def test_data_completeness_preserved(self):
        output = _make_valid_risk_diff()
        output["data_completeness"] = 0.85
        validated, warnings = validate_risk_diff_output(output)
        assert validated["data_completeness"] == 0.85
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_agents/test_risk_diff_agent.py::TestRiskDiffGuardrails -v`
Expected: FAIL — `ImportError: cannot import name 'validate_risk_diff_output'`

- [ ] **Step 3: Implement validate_risk_diff_output()**

Add at the end of `src/llm_guardrails.py`:

```python


# ─── Risk Diff Output ─────────────────────────────────────────────────────


VALID_CHANGE_TYPES = {"new", "removed", "escalated", "de-escalated", "reworded"}
VALID_SEVERITIES = {"high", "medium", "low"}


def validate_risk_diff_output(
    risk_diff: Dict[str, Any],
) -> Tuple[Dict[str, Any], List[str]]:
    """Validate risk diff agent output.

    Checks:
        1. Risk score bounds — clamp risk_score to [0, 100].
        2. Risk score delta bounds — clamp risk_score_delta to [-50, +50].
        3. Change type validation — verify all change_type values are valid.
        4. Severity validation — verify all severity values are valid.
        5. Diff consistency — if has_diff=False, warn if diff fields are non-empty.

    Returns:
        (validated_risk_diff, warnings)
    """
    warnings: List[str] = []
    validated = dict(risk_diff)

    # 1. Risk score bounds
    risk_score = _safe_float(validated.get("risk_score", 0))
    if risk_score is not None:
        if risk_score < 0 or risk_score > 100:
            warnings.append(
                f"risk_score {risk_score} out of bounds [0, 100], clamped to {_clamp(risk_score, 0, 100)}"
            )
            risk_score = _clamp(risk_score, 0, 100)
        validated["risk_score"] = risk_score

    # 2. Risk score delta bounds
    delta = _safe_float(validated.get("risk_score_delta", 0))
    if delta is not None:
        if delta < -50 or delta > 50:
            warnings.append(
                f"risk_score_delta {delta} out of bounds [-50, +50], clamped to {_clamp(delta, -50, 50)}"
            )
            delta = _clamp(delta, -50, 50)
        validated["risk_score_delta"] = delta

    # 3. Change type validation
    for list_key in ("new_risks", "removed_risks", "changed_risks"):
        for item in validated.get(list_key, []):
            ct = item.get("change_type", "")
            if ct and ct not in VALID_CHANGE_TYPES:
                warnings.append(
                    f"Invalid change_type '{ct}' in {list_key}. "
                    f"Expected one of: {sorted(VALID_CHANGE_TYPES)}"
                )

    # 4. Severity validation
    for list_key in ("new_risks", "removed_risks", "changed_risks", "current_risk_inventory"):
        for item in validated.get(list_key, []):
            sev = item.get("severity", "")
            if sev and sev not in VALID_SEVERITIES:
                warnings.append(
                    f"Invalid severity '{sev}' in {list_key}. "
                    f"Expected one of: {sorted(VALID_SEVERITIES)}"
                )

    # 5. Diff consistency
    has_diff = validated.get("has_diff", False)
    if not has_diff:
        has_diff_data = (
            len(validated.get("new_risks", [])) > 0
            or len(validated.get("removed_risks", [])) > 0
            or len(validated.get("changed_risks", [])) > 0
        )
        if has_diff_data:
            warnings.append(
                "has_diff is False but diff fields (new_risks, removed_risks, changed_risks) "
                "are non-empty. This is inconsistent."
            )

    return validated, warnings
```

- [ ] **Step 4: Wire guardrails into RiskDiffAgent**

In `src/agents/risk_diff_agent.py`, in the `analyze()` method, add guardrails after constructing the diff_result (right before `return diff_result`):

Replace the end of the Pass 2 try block in `analyze()`:

```python
            diff_result["current_risk_inventory"] = current_inventory
            diff_result["filings_compared"] = filings_compared
            diff_result["has_diff"] = True
            diff_result["extraction_methods"] = extraction_methods
            diff_result["data_completeness"] = completeness
            diff_result["data_sources_used"] = sources

            return diff_result
```

With:

```python
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
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m pytest tests/test_agents/test_risk_diff_agent.py::TestRiskDiffGuardrails -v`
Expected: All 9 tests PASS

- [ ] **Step 6: Commit**

```bash
git add src/llm_guardrails.py src/agents/risk_diff_agent.py tests/test_agents/test_risk_diff_agent.py
git commit -m "feat(risk-diff): add validate_risk_diff_output() guardrails — score bounds, change types, severity, diff consistency"
```

---

### Task 5: Orchestrator Integration (6-way gather)

**Files:**
- Modify: `src/orchestrator.py`
- Modify: `tests/test_orchestrator.py`

- [ ] **Step 1: Write orchestrator integration tests**

Append to `tests/test_orchestrator.py`:

```python
class TestRiskDiffIntegration:
    """Tests for risk diff agent integration in synthesis phase."""

    def test_risk_diff_in_registry(self, test_config):
        orch = Orchestrator(config=test_config)
        assert "risk_diff" in orch.AGENT_REGISTRY

    def test_risk_diff_not_in_default_agents(self, test_config):
        orch = Orchestrator(config=test_config)
        assert "risk_diff" not in orch.DEFAULT_AGENTS

    @pytest.mark.asyncio
    async def test_risk_diff_runs_parallel_in_synthesis(self, test_config, tmp_path):
        db_path = str(tmp_path / "test.db")
        db_manager = DatabaseManager(db_path)
        orch = Orchestrator(config=test_config, db_manager=db_manager)

        mock_risk_diff_data = {
            "new_risks": [],
            "removed_risks": [],
            "changed_risks": [],
            "risk_score": 50.0,
            "risk_score_delta": 0.0,
            "top_emerging_threats": [],
            "summary": "Test risk diff.",
            "current_risk_inventory": [],
            "filings_compared": [],
            "has_diff": False,
            "extraction_methods": [],
            "data_completeness": 0.0,
            "data_sources_used": [],
        }

        with (
            patch("src.orchestrator.NewsAgent") as MockNews,
            patch("src.orchestrator.MarketAgent") as MockMarket,
            patch("src.orchestrator.FundamentalsAgent") as MockFund,
            patch("src.orchestrator.TechnicalAgent") as MockTech,
            patch("src.orchestrator.MacroAgent") as MockMacro,
            patch("src.orchestrator.OptionsAgent") as MockOptions,
            patch("src.orchestrator.EarningsAgent") as MockEarnings,
            patch("src.orchestrator.LeadershipAgent") as MockLeadership,
            patch("src.orchestrator.SentimentAgent") as MockSent,
            patch("src.orchestrator.SolutionAgent") as MockSolution,
            patch("src.orchestrator.ThesisAgent") as MockThesis,
            patch("src.orchestrator.EarningsReviewAgent") as MockReview,
            patch("src.orchestrator.NarrativeAgent") as MockNarrative,
            patch("src.orchestrator.TagExtractorAgent") as MockTagExtractor,
            patch("src.orchestrator.RiskDiffAgent") as MockRiskDiff,
        ):
            for mock_cls, name in [
                (MockNews, "news"), (MockMarket, "market"),
                (MockFund, "fundamentals"), (MockTech, "technical"),
                (MockMacro, "macro"), (MockOptions, "options"),
                (MockEarnings, "earnings"), (MockLeadership, "leadership"),
            ]:
                mock_cls.return_value.execute = AsyncMock(return_value=_make_agent_result(name))

            MockSent.return_value.set_context_data = MagicMock()
            MockSent.return_value.execute = AsyncMock(return_value=_make_agent_result("sentiment"))
            MockSolution.return_value.execute = AsyncMock(return_value=_make_solution_result())
            MockThesis.return_value.execute = AsyncMock(return_value={"success": True, "data": {"thesis_summary": "Test."}})
            MockReview.return_value.execute = AsyncMock(return_value={"success": True, "data": {"executive_summary": "Test."}})
            MockNarrative.return_value.execute = AsyncMock(return_value={"success": True, "data": {"company_arc": "Test."}})
            MockTagExtractor.return_value.execute = AsyncMock(return_value={"success": True, "data": {"tags": []}})
            MockRiskDiff.return_value.execute = AsyncMock(return_value={"success": True, "data": mock_risk_diff_data})

            result = await orch.analyze_ticker("AAPL")

        assert result["success"] is True
        assert "risk_diff" in result["analysis"]
        assert result["analysis"]["risk_diff"]["summary"] == "Test risk diff."

    @pytest.mark.asyncio
    async def test_risk_diff_failure_is_nonblocking(self, test_config, tmp_path):
        db_path = str(tmp_path / "test.db")
        db_manager = DatabaseManager(db_path)
        orch = Orchestrator(config=test_config, db_manager=db_manager)

        with (
            patch("src.orchestrator.NewsAgent") as MockNews,
            patch("src.orchestrator.MarketAgent") as MockMarket,
            patch("src.orchestrator.FundamentalsAgent") as MockFund,
            patch("src.orchestrator.TechnicalAgent") as MockTech,
            patch("src.orchestrator.MacroAgent") as MockMacro,
            patch("src.orchestrator.OptionsAgent") as MockOptions,
            patch("src.orchestrator.EarningsAgent") as MockEarnings,
            patch("src.orchestrator.LeadershipAgent") as MockLeadership,
            patch("src.orchestrator.SentimentAgent") as MockSent,
            patch("src.orchestrator.SolutionAgent") as MockSolution,
            patch("src.orchestrator.ThesisAgent") as MockThesis,
            patch("src.orchestrator.EarningsReviewAgent") as MockReview,
            patch("src.orchestrator.NarrativeAgent") as MockNarrative,
            patch("src.orchestrator.TagExtractorAgent") as MockTagExtractor,
            patch("src.orchestrator.RiskDiffAgent") as MockRiskDiff,
        ):
            for mock_cls, name in [
                (MockNews, "news"), (MockMarket, "market"),
                (MockFund, "fundamentals"), (MockTech, "technical"),
                (MockMacro, "macro"), (MockOptions, "options"),
                (MockEarnings, "earnings"), (MockLeadership, "leadership"),
            ]:
                mock_cls.return_value.execute = AsyncMock(return_value=_make_agent_result(name))

            MockSent.return_value.set_context_data = MagicMock()
            MockSent.return_value.execute = AsyncMock(return_value=_make_agent_result("sentiment"))
            MockSolution.return_value.execute = AsyncMock(return_value=_make_solution_result())
            MockThesis.return_value.execute = AsyncMock(return_value={"success": True, "data": {"thesis_summary": "Test."}})
            MockReview.return_value.execute = AsyncMock(return_value={"success": True, "data": {"executive_summary": "Test."}})
            MockNarrative.return_value.execute = AsyncMock(return_value={"success": True, "data": {"company_arc": "Test."}})
            MockTagExtractor.return_value.execute = AsyncMock(return_value={"success": True, "data": {"tags": []}})
            MockRiskDiff.return_value.execute = AsyncMock(side_effect=Exception("EDGAR exploded"))

            result = await orch.analyze_ticker("AAPL")

        assert result["success"] is True
        assert result["analysis"].get("risk_diff") is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_orchestrator.py::TestRiskDiffIntegration -v`
Expected: FAIL — `cannot import name 'RiskDiffAgent'` or registry missing

- [ ] **Step 3: Add import and registry entry**

In `src/orchestrator.py`, add after the TagExtractorAgent import:

```python
from .agents.risk_diff_agent import RiskDiffAgent
```

Add to `AGENT_REGISTRY`:

```python
"risk_diff": {"class": RiskDiffAgent, "requires": []},
```

- [ ] **Step 4: Add _run_risk_diff_agent() method**

Add after `_run_tag_extractor_agent()` in `src/orchestrator.py`:

```python
    async def _run_risk_diff_agent(
        self,
        ticker: str,
        agent_results: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        """Run risk diff agent for SEC filing risk factor changes (non-blocking)."""
        try:
            risk_diff_agent = RiskDiffAgent(ticker, self.config, agent_results)
            self._inject_shared_resources(risk_diff_agent)
            timeout = self.config.get("AGENT_TIMEOUT", 30)
            result = await asyncio.wait_for(
                risk_diff_agent.execute(),
                timeout=timeout,
            )
            if result.get("success"):
                return result.get("data")
            else:
                self.logger.warning(f"Risk diff agent failed for {ticker}: {result.get('error')}")
                return None
        except asyncio.TimeoutError:
            self.logger.warning(f"Risk diff agent timed out for {ticker}")
            return None
        except Exception as e:
            self.logger.warning(f"Risk diff agent error for {ticker}: {e}")
            return None
```

- [ ] **Step 5: Expand asyncio.gather() to 6 agents**

In `analyze_ticker()`, replace:

```python
            final_analysis, thesis_result, earnings_review_result, narrative_result, tag_result = await asyncio.gather(
                self._run_solution_agent(ticker, agent_results),
                self._run_thesis_agent(ticker, agent_results),
                self._run_earnings_review_agent(ticker, agent_results),
                self._run_narrative_agent(ticker, agent_results),
                self._run_tag_extractor_agent(ticker, agent_results),
            )
            if thesis_result:
                final_analysis["thesis"] = thesis_result
            if earnings_review_result:
                final_analysis["earnings_review"] = earnings_review_result
            if narrative_result:
                final_analysis["narrative"] = narrative_result
```

With:

```python
            final_analysis, thesis_result, earnings_review_result, narrative_result, tag_result, risk_diff_result = await asyncio.gather(
                self._run_solution_agent(ticker, agent_results),
                self._run_thesis_agent(ticker, agent_results),
                self._run_earnings_review_agent(ticker, agent_results),
                self._run_narrative_agent(ticker, agent_results),
                self._run_tag_extractor_agent(ticker, agent_results),
                self._run_risk_diff_agent(ticker, agent_results),
            )
            if thesis_result:
                final_analysis["thesis"] = thesis_result
            if earnings_review_result:
                final_analysis["earnings_review"] = earnings_review_result
            if narrative_result:
                final_analysis["narrative"] = narrative_result
            if risk_diff_result:
                final_analysis["risk_diff"] = risk_diff_result
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `python -m pytest tests/test_orchestrator.py -v`
Expected: All tests PASS (existing + 4 new)

- [ ] **Step 7: Commit**

```bash
git add src/orchestrator.py tests/test_orchestrator.py
git commit -m "feat(risk-diff): integrate RiskDiffAgent into orchestrator synthesis phase (6-way gather)"
```

---

### Task 6: LLM Mock Tests & Prompt Tests

**Files:**
- Modify: `tests/test_agents/test_risk_diff_agent.py`

- [ ] **Step 1: Write LLM mock tests and full flow tests**

Append to `tests/test_agents/test_risk_diff_agent.py`:

```python
import json as json_module


MOCK_PASS1_RESPONSE = json_module.dumps({
    "risks": [
        {
            "topic": "Supply Chain Concentration",
            "severity": "high",
            "summary": "Company relies on limited suppliers for key components.",
            "text_excerpt": "We rely on a limited number of suppliers...",
        },
        {
            "topic": "Regulatory Risk",
            "severity": "medium",
            "summary": "Subject to evolving government regulations.",
            "text_excerpt": "Changes in laws and regulations could impact...",
        },
        {
            "topic": "Market Competition",
            "severity": "medium",
            "summary": "Faces intense competition across product categories.",
            "text_excerpt": "We face intense competition...",
        },
    ]
})

MOCK_PASS1_RESPONSE_PRIOR = json_module.dumps({
    "risks": [
        {
            "topic": "Supply Chain Concentration",
            "severity": "medium",
            "summary": "Reliance on a few suppliers for components.",
            "text_excerpt": "We source components from select suppliers...",
        },
        {
            "topic": "Regulatory Risk",
            "severity": "medium",
            "summary": "Subject to government regulations.",
            "text_excerpt": "We are subject to various regulations...",
        },
        {
            "topic": "Foreign Currency Risk",
            "severity": "low",
            "summary": "Exposure to currency fluctuations.",
            "text_excerpt": "Our international operations expose us to currency risk...",
        },
    ]
})

MOCK_PASS2_RESPONSE = json_module.dumps({
    "new_risks": [
        {
            "risk_topic": "Market Competition",
            "change_type": "new",
            "severity": "medium",
            "current_text_excerpt": "We face intense competition...",
            "prior_text_excerpt": "",
            "analysis": "New explicit competition disclosure added to risk factors.",
        }
    ],
    "removed_risks": [
        {
            "risk_topic": "Foreign Currency Risk",
            "change_type": "removed",
            "severity": "low",
            "current_text_excerpt": "",
            "prior_text_excerpt": "Our international operations expose us to currency risk...",
            "analysis": "Currency risk disclosure removed, possibly folded into another section.",
        }
    ],
    "changed_risks": [
        {
            "risk_topic": "Supply Chain Concentration",
            "change_type": "escalated",
            "severity": "high",
            "current_text_excerpt": "We rely on a limited number of suppliers...",
            "prior_text_excerpt": "We source components from select suppliers...",
            "analysis": "Language escalated from 'select suppliers' to 'limited number', severity raised to high.",
        }
    ],
    "risk_score": 62,
    "risk_score_delta": 8,
    "top_emerging_threats": [
        "Supply chain concentration escalated to high severity",
        "New competition risk disclosure",
    ],
    "summary": "Risk profile moderately elevated. Supply chain risk language escalated and a new competition disclosure was added, while currency risk was removed.",
})


class TestRiskDiffLLMFlow:
    """Tests for the full two-pass LLM flow with mocked LLM calls."""

    @pytest.mark.asyncio
    async def test_full_diff_flow(self):
        agent = RiskDiffAgent("AAPL", {"llm_config": {"provider": "anthropic", "api_key": "test"}}, _make_agent_results())
        mock_dp = MagicMock()
        mock_dp.get_sec_filing_metadata = AsyncMock(return_value=_make_mock_filing_metadata(2))
        mock_dp.get_sec_filing_section = AsyncMock(return_value=_make_mock_filing_section())
        agent._data_provider = mock_dp

        # Mock LLM calls: Pass 1 current, Pass 1 prior, Pass 2
        call_count = 0

        async def mock_call_llm(prompt):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return MOCK_PASS1_RESPONSE
            elif call_count == 2:
                return MOCK_PASS1_RESPONSE_PRIOR
            else:
                return MOCK_PASS2_RESPONSE

        agent._call_llm = mock_call_llm

        raw_data = await agent.fetch_data()
        result = await agent.analyze(raw_data)

        assert result["has_diff"] is True
        assert len(result["new_risks"]) == 1
        assert len(result["removed_risks"]) == 1
        assert len(result["changed_risks"]) == 1
        assert result["risk_score"] == 62
        assert result["risk_score_delta"] == 8
        assert len(result["current_risk_inventory"]) == 3
        assert len(result["filings_compared"]) == 2

    @pytest.mark.asyncio
    async def test_inventory_only_flow(self):
        agent = RiskDiffAgent("AAPL", {"llm_config": {"provider": "anthropic", "api_key": "test"}}, _make_agent_results())
        mock_dp = MagicMock()
        mock_dp.get_sec_filing_metadata = AsyncMock(return_value=_make_mock_filing_metadata(1))
        mock_dp.get_sec_filing_section = AsyncMock(return_value=_make_mock_filing_section())
        agent._data_provider = mock_dp

        async def mock_call_llm(prompt):
            return MOCK_PASS1_RESPONSE

        agent._call_llm = mock_call_llm

        raw_data = await agent.fetch_data()
        result = await agent.analyze(raw_data)

        assert result["has_diff"] is False
        assert len(result["current_risk_inventory"]) == 3
        assert result["new_risks"] == []
        assert result["removed_risks"] == []
        assert result["changed_risks"] == []

    @pytest.mark.asyncio
    async def test_pass2_failure_fallback(self):
        agent = RiskDiffAgent("AAPL", {"llm_config": {"provider": "anthropic", "api_key": "test"}}, _make_agent_results())
        mock_dp = MagicMock()
        mock_dp.get_sec_filing_metadata = AsyncMock(return_value=_make_mock_filing_metadata(2))
        mock_dp.get_sec_filing_section = AsyncMock(return_value=_make_mock_filing_section())
        agent._data_provider = mock_dp

        call_count = 0

        async def mock_call_llm(prompt):
            nonlocal call_count
            call_count += 1
            if call_count <= 2:
                return MOCK_PASS1_RESPONSE
            else:
                raise Exception("LLM failed on Pass 2")

        agent._call_llm = mock_call_llm

        raw_data = await agent.fetch_data()
        result = await agent.analyze(raw_data)

        # Should fall back to inventory-only with pass2_failed flag
        assert result["has_diff"] is False
        assert result.get("pass2_failed") is True
        assert len(result["current_risk_inventory"]) == 3

    @pytest.mark.asyncio
    async def test_no_filings_empty_result(self):
        agent = RiskDiffAgent("AAPL", {"llm_config": {}}, _make_agent_results())
        mock_dp = MagicMock()
        mock_dp.get_sec_filing_metadata = AsyncMock(return_value=[])
        agent._data_provider = mock_dp

        raw_data = await agent.fetch_data()
        result = await agent.analyze(raw_data)

        assert result["has_diff"] is False
        assert result["data_completeness"] == pytest.approx(0.15, abs=0.02)
        assert "error" in result

    @pytest.mark.asyncio
    async def test_all_pass1_failures_empty(self):
        agent = RiskDiffAgent("AAPL", {"llm_config": {"provider": "anthropic", "api_key": "test"}}, _make_agent_results())
        mock_dp = MagicMock()
        mock_dp.get_sec_filing_metadata = AsyncMock(return_value=_make_mock_filing_metadata(2))
        mock_dp.get_sec_filing_section = AsyncMock(return_value=_make_mock_filing_section())
        agent._data_provider = mock_dp

        async def mock_call_llm(prompt):
            raise Exception("LLM completely dead")

        agent._call_llm = mock_call_llm

        raw_data = await agent.fetch_data()
        result = await agent.analyze(raw_data)

        # All Pass 1 calls fail → empty result
        assert result["has_diff"] is False
        assert result["current_risk_inventory"] == []


class TestRiskDiffPrompts:
    """Tests for prompt construction."""

    def test_pass1_prompt_contains_ticker(self):
        agent = RiskDiffAgent("AAPL", {"llm_config": {}}, _make_agent_results())
        filing = {"filing_type": "10-K", "filing_date": "2025-02-15"}
        prompt = agent._build_pass1_prompt("Risk text here", filing)
        assert "AAPL" in prompt
        assert "10-K" in prompt
        assert "2025-02-15" in prompt
        assert "Risk text here" in prompt

    def test_pass2_prompt_contains_inventories(self):
        agent = RiskDiffAgent("AAPL", {"llm_config": {}}, _make_agent_results())
        current = {"risks": [{"topic": "Test Risk"}]}
        prior = {"risks": [{"topic": "Old Risk"}]}
        prompt = agent._build_pass2_prompt(current, prior)
        assert "AAPL" in prompt
        assert "Test Risk" in prompt
        assert "Old Risk" in prompt

    def test_pass2_prompt_includes_supplementary(self):
        agent = RiskDiffAgent("AAPL", {"llm_config": {}}, _make_agent_results())
        current = {"risks": []}
        prior = {"risks": []}
        supplement = {"risks": [{"topic": "Quarterly Risk"}]}
        prompt = agent._build_pass2_prompt(current, prior, supplement)
        assert "Quarterly Risk" in prompt
        assert "Supplementary" in prompt or "10-Q" in prompt
```

- [ ] **Step 2: Run tests to verify they pass**

Run: `python -m pytest tests/test_agents/test_risk_diff_agent.py::TestRiskDiffLLMFlow tests/test_agents/test_risk_diff_agent.py::TestRiskDiffPrompts -v`
Expected: All 8 tests PASS

- [ ] **Step 3: Commit**

```bash
git add tests/test_agents/test_risk_diff_agent.py
git commit -m "test(risk-diff): add LLM mock tests for two-pass flow, fallbacks, and prompt construction"
```

---

### Task 7: Full Test Suite Verification

**Files:**
- None (verification only)

- [ ] **Step 1: Run all risk diff agent tests**

Run: `python -m pytest tests/test_agents/test_risk_diff_agent.py -v`
Expected: All tests PASS (models + EDGAR + data fetching + completeness + guardrails + LLM flow + prompts)

- [ ] **Step 2: Run orchestrator tests**

Run: `python -m pytest tests/test_orchestrator.py -v`
Expected: All tests PASS (existing + risk diff integration)

- [ ] **Step 3: Run full test suite**

Run: `python -m pytest tests/ -v --timeout=30`
Expected: All tests PASS, no regressions

- [ ] **Step 4: Verify import chain**

Run: `python -c "from src.agents.risk_diff_agent import RiskDiffAgent; from src.models import RiskTopic, RiskChange, RiskDiffOutput; from src.llm_guardrails import validate_risk_diff_output; print('All imports OK')"`
Expected: `All imports OK`

- [ ] **Step 5: Final commit (if any fixups needed)**

```bash
git add -A
git commit -m "fix(risk-diff): test suite fixups after full verification"
```
