"""Tests for SolutionAgent scenario normalization and prompt building behavior."""

from src.agents.solution_agent import SolutionAgent


def _make_agent():
    return SolutionAgent(
        ticker="AAPL",
        config={"llm_config": {"provider": "none"}},
        agent_results={},
    )


class TestBuildPrompt:
    """Tests for _build_prompt and calibration context injection."""

    def test_build_prompt_includes_calibration_context(self):
        """When calibration_context is provided, prompt includes HISTORICAL ACCURACY section."""
        agent = SolutionAgent("AAPL", {"llm_config": {}}, {})
        agent.calibration_context = {
            "7d": {"hit_rate": 0.72, "sample_size": 50},
            "30d": {"hit_rate": 0.65, "sample_size": 30},
        }
        prompt = agent._build_prompt(
            news_data={}, sentiment_data={}, fundamentals_data={},
            market_data={}, technical_data={}, macro_data={}, options_data={},
        )
        assert "HISTORICAL ACCURACY" in prompt
        assert "72" in prompt  # hit rate displayed
        assert "50" in prompt  # sample size displayed

    def test_build_prompt_without_calibration_omits_section(self):
        """When calibration_context is None/empty, prompt has no HISTORICAL ACCURACY section."""
        agent = SolutionAgent("AAPL", {"llm_config": {}}, {})
        agent.calibration_context = None
        prompt = agent._build_prompt(
            news_data={}, sentiment_data={}, fundamentals_data={},
            market_data={}, technical_data={}, macro_data={}, options_data={},
        )
        assert "HISTORICAL ACCURACY" not in prompt

    def test_build_prompt_contains_core_sections(self):
        """The prompt includes the major data sections regardless of calibration."""
        agent = SolutionAgent("AAPL", {"llm_config": {}}, {})
        agent.calibration_context = None
        prompt = agent._build_prompt(
            news_data={}, sentiment_data={}, fundamentals_data={},
            market_data={}, technical_data={}, macro_data={}, options_data={},
        )
        assert "FUNDAMENTALS" in prompt
        assert "MARKET DATA" in prompt
        assert "TECHNICAL ANALYSIS" in prompt
        assert "SENTIMENT ANALYSIS" in prompt
        assert "MACROECONOMIC ENVIRONMENT" in prompt
        assert "OPTIONS FLOW" in prompt
        assert "NEWS SUMMARY" in prompt
        assert "JSON format" in prompt

    def test_build_prompt_empty_calibration_dict_omits_section(self):
        """An empty calibration_context dict should not add the section."""
        agent = SolutionAgent("AAPL", {"llm_config": {}}, {})
        agent.calibration_context = {}
        prompt = agent._build_prompt(
            news_data={}, sentiment_data={}, fundamentals_data={},
            market_data={}, technical_data={}, macro_data={}, options_data={},
        )
        assert "HISTORICAL ACCURACY" not in prompt


class TestSolutionAgentScenarios:
    """Scenario normalization and fallback tests."""

    def test_scenarios_are_clamped_and_renormalized(self):
        """Probabilities are clamped into [0,1] and normalized to sum to 1."""
        agent = _make_agent()
        raw = {
            "recommendation": "BUY",
            "score": 70,
            "confidence": 0.8,
            "reasoning": "Test reasoning.",
            "risks": [],
            "opportunities": [],
            "price_targets": {},
            "scenarios": {
                "bull": {"probability": 1.4, "expected_return_pct": "18", "thesis": "Upside case"},
                "base": {"probability": 0.4, "expected_return_pct": 6, "thesis": "Base case"},
                "bear": {"probability": -0.2, "expected_return_pct": "-12.5", "thesis": "Downside case"},
            },
        }

        normalized = agent._normalize_synthesis_result(raw, market_data={})
        scenarios = normalized["scenarios"]
        total_probability = (
            scenarios["bull"]["probability"]
            + scenarios["base"]["probability"]
            + scenarios["bear"]["probability"]
        )

        assert 0.99 <= total_probability <= 1.01
        assert 0.0 <= scenarios["bull"]["probability"] <= 1.0
        assert 0.0 <= scenarios["base"]["probability"] <= 1.0
        assert 0.0 <= scenarios["bear"]["probability"] <= 1.0
        assert scenarios["bull"]["expected_return_pct"] == 18.0
        assert scenarios["bear"]["expected_return_pct"] == -12.5
        assert isinstance(normalized["scenario_summary"], str)
        assert normalized["scenario_summary"]

    def test_missing_or_invalid_scenario_fields_use_fallbacks(self):
        """Missing scenarios and invalid expected return values fall back safely."""
        agent = _make_agent()
        raw = {
            "recommendation": "HOLD",
            "score": 5,
            "confidence": 0.55,
            "reasoning": "Fallback behavior.",
            "risks": [],
            "opportunities": [],
            "price_targets": {},
            "scenarios": {
                "bull": {"probability": "bad", "expected_return_pct": "not-a-number", "thesis": ""},
            },
        }

        normalized = agent._normalize_synthesis_result(raw, market_data={})
        scenarios = normalized["scenarios"]

        assert set(scenarios.keys()) == {"bull", "base", "bear"}
        assert scenarios["bull"]["expected_return_pct"] is None
        assert isinstance(scenarios["base"]["thesis"], str)
        assert scenarios["base"]["thesis"]
        total_probability = sum(scenarios[s]["probability"] for s in ("bull", "base", "bear"))
        assert 0.99 <= total_probability <= 1.01
