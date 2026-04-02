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
        mock_dp.get_sec_filing_metadata = AsyncMock(
            side_effect=[_make_mock_filing_metadata(2), []]
        )
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


# ── LLM Mock Tests & Prompt Tests ─────────────────────────────────────────────

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
        # Return 2 10-Ks for first call, empty for 10-Q call
        mock_dp.get_sec_filing_metadata = AsyncMock(
            side_effect=[_make_mock_filing_metadata(2), []]
        )
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
        # Return 1 10-K for first call, empty for 10-Q call
        mock_dp.get_sec_filing_metadata = AsyncMock(
            side_effect=[_make_mock_filing_metadata(1), []]
        )
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
        # Return 2 10-Ks for first call, empty for 10-Q call
        mock_dp.get_sec_filing_metadata = AsyncMock(
            side_effect=[_make_mock_filing_metadata(2), []]
        )
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
        # Return 2 10-Ks for first call, empty for 10-Q call
        mock_dp.get_sec_filing_metadata = AsyncMock(
            side_effect=[_make_mock_filing_metadata(2), []]
        )
        mock_dp.get_sec_filing_section = AsyncMock(return_value=_make_mock_filing_section())
        agent._data_provider = mock_dp

        async def mock_call_llm(prompt):
            raise Exception("LLM completely dead")

        agent._call_llm = mock_call_llm

        raw_data = await agent.fetch_data()
        result = await agent.analyze(raw_data)

        # All Pass 1 calls fail -> empty result
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
