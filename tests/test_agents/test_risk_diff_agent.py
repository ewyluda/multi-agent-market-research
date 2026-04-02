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
