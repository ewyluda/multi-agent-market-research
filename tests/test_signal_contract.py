"""Unit tests for deterministic signal contract v2 builder."""

from src.signal_contract import build_signal_contract_v2, validate_signal_contract_v2


def _base_inputs():
    analysis = {
        "recommendation": "BUY",
        "confidence": 0.6,
        "scenarios": {
            "bull": {"probability": 0.4, "expected_return_pct": 14.0, "thesis": "Bull"},
            "base": {"probability": 0.4, "expected_return_pct": 4.0, "thesis": "Base"},
            "bear": {"probability": 0.2, "expected_return_pct": -10.0, "thesis": "Bear"},
        },
        "decision_card": {
            "entry_zone": {"low": 99.0, "high": 101.0, "reference": 100.0},
            "stop_loss": 92.0,
            "targets": [108.0, 112.0],
            "invalidation_conditions": ["Break below support"],
            "time_horizon": "MEDIUM_TERM",
        },
        "rationale_summary": "Deterministic test rationale.",
    }

    diagnostics = {
        "data_quality": {
            "agent_success_rate": 0.8,
            "news_freshness_hours": 12,
            "fallback_source_agents": ["news"],
        },
        "disagreement": {
            "bullish_count": 3,
            "bearish_count": 1,
            "agent_directions": {
                "market": "bullish",
                "technical": "bullish",
            },
        },
    }

    agent_results = {
        "market": {
            "success": True,
            "data": {
                "current_price": 100.0,
                "average_volume": 2_000_000,
                "volatility_3m": 22.0,
                "trend": "uptrend",
                "data_source": "alpha_vantage",
            },
        },
        "technical": {
            "success": True,
            "data": {
                "signals": {"strength": 42},
                "data_source": "alpha_vantage",
            },
        },
    }

    hit_rate_by_horizon = {
        "1d": {"hit_rate": 0.55, "sample_size": 50},
        "7d": {"hit_rate": 0.58, "sample_size": 120},
        "30d": {"hit_rate": 0.52, "sample_size": 20},
    }

    return analysis, diagnostics, agent_results, hit_rate_by_horizon


def test_build_signal_contract_v2_deterministic_math_rules():
    analysis, diagnostics, agent_results, hit_rate_by_horizon = _base_inputs()

    payload = build_signal_contract_v2(
        analysis=analysis,
        diagnostics=diagnostics,
        agent_results=agent_results,
        hit_rate_by_horizon=hit_rate_by_horizon,
    )

    assert payload["schema_version"] == "2.0"
    assert payload["instrument_type"] == "US_EQUITY"
    assert payload["recommendation"] == "BUY"

    assert payload["expected_return_pct"]["7d"] == 5.2
    assert round(payload["expected_return_pct"]["1d"], 6) == round(5.2 / 7.0, 6)
    assert round(payload["expected_return_pct"]["30d"], 6) == round(5.2 * 30.0 / 7.0, 6)

    assert payload["downside_risk_pct"]["7d"] == 8.0
    assert round(payload["downside_risk_pct"]["1d"], 6) == round(8.0 / 7.0, 6)
    assert round(payload["downside_risk_pct"]["30d"], 6) == round(8.0 * 30.0 / 7.0, 6)

    assert payload["hit_rate"]["7d"] == 0.58
    assert payload["hit_rate"]["30d"] == 0.58  # 30d sample < 30 falls back to 7d

    expected_ev = (5.2 * 0.58) - (8.0 * (1 - 0.58))
    assert round(payload["ev_score_7d"], 6) == round(expected_ev, 6)

    assert payload["risk"]["risk_reward_ratio_7d"] == 0.65
    assert payload["risk"]["data_quality_score"] == 72.5
    assert payload["risk"]["conflict_score"] == 25.0

    is_valid, errors = validate_signal_contract_v2(payload)
    assert is_valid is True
    assert errors == []


def test_confidence_calibration_falls_back_to_raw_when_samples_insufficient():
    analysis, diagnostics, agent_results, _ = _base_inputs()

    payload = build_signal_contract_v2(
        analysis=analysis,
        diagnostics=diagnostics,
        agent_results=agent_results,
        hit_rate_by_horizon={
            "7d": {"hit_rate": 0.95, "sample_size": 10},
        },
    )

    assert payload["confidence"]["raw"] == 0.6
    assert payload["confidence"]["calibrated"] == 0.6
    assert payload["confidence"]["uncertainty_band_pct"] == 15.0
