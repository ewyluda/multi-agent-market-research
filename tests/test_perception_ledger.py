"""Tests for KPI extraction from agent results."""

import pytest
from src.perception_ledger import extract_kpi_snapshots


class TestKPIExtraction:
    """Tests for extract_kpi_snapshots function."""

    def test_extracts_fundamentals_valuation(self):
        agent_results = {
            "fundamentals": {
                "success": True,
                "data": {
                    "forward_pe": 22.5, "price_to_sales": 8.3, "profit_margins": 0.25,
                    "operating_margins": 0.30, "return_on_equity": 0.45, "debt_to_equity": 1.2,
                    "data_source": "openbb",
                },
            },
        }
        snapshots = extract_kpi_snapshots(agent_results, confidence=0.9)
        by_name = {s["kpi_name"]: s for s in snapshots}
        assert by_name["forward_pe"]["value"] == 22.5
        assert by_name["forward_pe"]["kpi_category"] == "valuation"
        assert by_name["price_to_sales"]["value"] == 8.3
        assert by_name["profit_margins"]["value"] == 0.25
        assert by_name["profit_margins"]["kpi_category"] == "margins"
        assert by_name["return_on_equity"]["value"] == 0.45

    def test_extracts_fundamentals_growth(self):
        agent_results = {
            "fundamentals": {"success": True, "data": {"revenue_growth": 0.15, "earnings_growth": 0.22, "data_source": "openbb"}},
        }
        snapshots = extract_kpi_snapshots(agent_results, confidence=0.9)
        by_name = {s["kpi_name"]: s for s in snapshots}
        assert by_name["revenue_growth"]["value"] == 0.15
        assert by_name["revenue_growth"]["kpi_category"] == "growth"
        assert by_name["earnings_growth"]["value"] == 0.22

    def test_extracts_transcript_guidance(self):
        agent_results = {
            "fundamentals": {"success": True, "data": {
                "transcript_metrics": {
                    "revenue_guidance": {"low": 50.0, "unit": "billion"},
                    "eps_guidance": {"low": 2.50},
                    "capex": {"value": 12.0, "unit": "billion"},
                },
                "data_source": "openbb",
            }},
        }
        snapshots = extract_kpi_snapshots(agent_results, confidence=0.9)
        by_name = {s["kpi_name"]: s for s in snapshots}
        assert by_name["revenue_guidance"]["value"] == 50.0
        assert by_name["revenue_guidance"]["kpi_category"] == "guidance"
        assert by_name["eps_guidance"]["value"] == 2.50
        assert by_name["capex_outlook"]["value"] == 12.0

    def test_extracts_technical_indicators(self):
        agent_results = {
            "technical": {"success": True, "data": {
                "indicators": {"rsi": {"value": 65.0}, "macd": {"signal_line": 1.23}, "ma_50": 150.0},
                "data_source": "openbb",
            }},
        }
        snapshots = extract_kpi_snapshots(agent_results, confidence=0.8)
        by_name = {s["kpi_name"]: s for s in snapshots}
        assert by_name["rsi"]["value"] == 65.0
        assert by_name["rsi"]["kpi_category"] == "technical"
        assert by_name["macd_signal"]["value"] == 1.23

    def test_extracts_sentiment(self):
        agent_results = {
            "sentiment": {"success": True, "data": {"overall_sentiment": 0.72, "confidence": 0.8}},
        }
        snapshots = extract_kpi_snapshots(agent_results, confidence=0.8)
        by_name = {s["kpi_name"]: s for s in snapshots}
        assert by_name["overall_sentiment"]["value"] == 0.72
        assert by_name["overall_sentiment"]["kpi_category"] == "sentiment"

    def test_extracts_macro_indicators(self):
        agent_results = {
            "macro": {"success": True, "data": {
                "indicators": {
                    "federal_funds_rate": {"current": 5.25},
                    "cpi": {"current": 3.2},
                    "real_gdp": {"current": 2.8},
                },
                "yield_curve": {"spread": 0.45},
                "data_source": "openbb",
            }},
        }
        snapshots = extract_kpi_snapshots(agent_results, confidence=0.9)
        by_name = {s["kpi_name"]: s for s in snapshots}
        assert by_name["fed_funds_rate"]["value"] == 5.25
        assert by_name["fed_funds_rate"]["kpi_category"] == "macro"
        assert by_name["cpi_yoy"]["value"] == 3.2
        assert by_name["gdp_growth"]["value"] == 2.8
        assert by_name["yield_spread"]["value"] == 0.45

    def test_extracts_options(self):
        agent_results = {
            "options": {"success": True, "data": {"put_call_ratio": 0.85, "max_pain": 175.0, "data_source": "yfinance"}},
        }
        snapshots = extract_kpi_snapshots(agent_results, confidence=0.7)
        by_name = {s["kpi_name"]: s for s in snapshots}
        assert by_name["put_call_ratio"]["value"] == 0.85
        assert by_name["max_pain"]["value"] == 175.0

    def test_extracts_market_analyst_targets(self):
        agent_results = {
            "fundamentals": {"success": True, "data": {
                "target_median_price": 200.0, "target_high_price": 250.0,
                "target_low_price": 170.0, "number_of_analyst_opinions": 35,
                "data_source": "openbb",
            }},
        }
        snapshots = extract_kpi_snapshots(agent_results, confidence=0.9)
        by_name = {s["kpi_name"]: s for s in snapshots}
        assert by_name["analyst_target_median"]["value"] == 200.0
        assert by_name["analyst_target_median"]["kpi_category"] == "analyst"
        assert by_name["analyst_count"]["value"] == 35

    def test_skips_failed_agents(self):
        agent_results = {
            "fundamentals": {"success": False, "error": "timeout"},
            "sentiment": {"success": True, "data": {"overall_sentiment": 0.5}},
        }
        snapshots = extract_kpi_snapshots(agent_results, confidence=0.8)
        names = [s["kpi_name"] for s in snapshots]
        assert "forward_pe" not in names
        assert "overall_sentiment" in names

    def test_skips_none_values(self):
        agent_results = {
            "fundamentals": {"success": True, "data": {"forward_pe": None, "profit_margins": 0.25, "data_source": "openbb"}},
        }
        snapshots = extract_kpi_snapshots(agent_results, confidence=0.9)
        names = [s["kpi_name"] for s in snapshots]
        assert "forward_pe" not in names
        assert "profit_margins" in names

    def test_all_snapshots_have_required_fields(self):
        agent_results = {
            "fundamentals": {"success": True, "data": {"forward_pe": 22.5, "data_source": "openbb"}},
        }
        snapshots = extract_kpi_snapshots(agent_results, confidence=0.9)
        for s in snapshots:
            assert "kpi_name" in s
            assert "kpi_category" in s
            assert "source_agent" in s
            assert "confidence" in s
