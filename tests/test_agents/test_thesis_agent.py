"""Tests for ThesisAgent — models, data gate, prompts, guardrails."""

import pytest
from pydantic import ValidationError
from src.models import TensionPoint, ManagementQuestion, ThesisCase, ThesisOutput
from src.agents.thesis_agent import ThesisAgent
from src.llm_guardrails import validate_thesis_output


class TestThesisModels:
    """Pydantic model validation tests."""

    def test_tension_point_valid(self):
        tp = TensionPoint(
            topic="Revenue Sustainability",
            bull_view="Strong recurring revenue base with 95% retention.",
            bear_view="Growth is decelerating and new customer acquisition costs are rising.",
            evidence=["NRR at 95%", "CAC up 20% YoY"],
            resolution_catalyst="Next quarter's earnings will show if retention holds.",
        )
        assert tp.topic == "Revenue Sustainability"
        assert len(tp.evidence) == 2

    def test_management_question_valid(self):
        mq = ManagementQuestion(
            role="CEO",
            question="What is your strategy for international expansion?",
            context="Revenue from international markets has grown 40% but is still only 15% of total.",
        )
        assert mq.role == "CEO"

    def test_management_question_accepts_any_role_string(self):
        mq = ManagementQuestion(
            role="CTO",
            question="What about tech debt?",
            context="Context here.",
        )
        # Model accepts any string for role — no enum constraint
        assert mq.role == "CTO"

    def test_thesis_case_valid(self):
        tc = ThesisCase(
            thesis="Strong fundamentals and accelerating growth justify premium valuation.",
            key_drivers=["Revenue growth", "Margin expansion", "TAM expansion"],
            catalysts=["Q2 earnings beat", "New product launch in H2"],
        )
        assert len(tc.key_drivers) == 3

    def test_thesis_output_valid(self):
        output = ThesisOutput(
            bull_case=ThesisCase(
                thesis="Bull thesis.",
                key_drivers=["Driver 1"],
                catalysts=["Catalyst 1"],
            ),
            bear_case=ThesisCase(
                thesis="Bear thesis.",
                key_drivers=["Driver 1"],
                catalysts=["Catalyst 1"],
            ),
            tension_points=[
                TensionPoint(
                    topic="Growth",
                    bull_view="Growing fast.",
                    bear_view="Growth slowing.",
                    evidence=["Rev +20%"],
                    resolution_catalyst="Next earnings.",
                )
            ],
            management_questions=[
                ManagementQuestion(
                    role="CEO",
                    question="Strategy?",
                    context="Important because...",
                )
            ],
            thesis_summary="Summary paragraph.",
            data_completeness=0.85,
            data_sources_used=["fundamentals", "news", "earnings"],
        )
        assert output.data_completeness == 0.85
        assert len(output.tension_points) == 1

    def test_thesis_output_data_completeness_clamped(self):
        """data_completeness must be between 0.0 and 1.0."""
        with pytest.raises(ValidationError):
            ThesisOutput(
                bull_case=ThesisCase(thesis="x", key_drivers=[], catalysts=[]),
                bear_case=ThesisCase(thesis="x", key_drivers=[], catalysts=[]),
                tension_points=[],
                management_questions=[],
                thesis_summary="x",
                data_completeness=1.5,
                data_sources_used=[],
            )


def _make_agent_results(
    fundamentals=True, news=True, earnings=True, market=True,
    technical=True, macro=True, options=True, leadership=True,
):
    """Build mock agent_results dict with configurable agent success."""
    results = {}
    if fundamentals:
        results["fundamentals"] = {
            "success": True,
            "data": {
                "company_name": "Apple Inc.",
                "sector": "Technology",
                "market_cap": 3000000000000,
                "revenue": 383000000000,
                "revenue_growth": 0.08,
                "net_income": 97000000000,
                "gross_margin": 0.46,
                "pe_ratio": 32.5,
                "debt_to_equity": 1.73,
                "business_description": "Designs consumer electronics and software.",
                "analyst_estimates": {"target_mean": 210, "target_high": 250},
                "insider_trading": [{"owner_name": "Tim Cook", "transaction_type": "Sale", "shares": 50000}],
                "data_source": "fmp",
            },
        }
    if news:
        results["news"] = {
            "success": True,
            "data": {
                "articles": [
                    {"title": "Apple AI push accelerates", "summary": "New AI features announced.", "sentiment": 0.6},
                    {"title": "iPhone sales slow in China", "summary": "Market share declining.", "sentiment": -0.3},
                ],
                "news_sentiment": 0.15,
                "data_source": "tavily",
            },
        }
    if earnings:
        results["earnings"] = {
            "success": True,
            "data": {
                "highlights": [{"tag": "BEAT", "text": "EPS beat by 12%"}],
                "guidance": [{"metric": "Revenue", "prior": "$90-92B", "current": "$93-95B", "direction": "raised"}],
                "tone": "confident",
                "guidance_direction": "raised",
                "qa_highlights": [{"analyst": "John", "firm": "GS", "topic": "AI spend", "question": "Capex plans?", "answer": "Increasing investment."}],
                "eps_history": [{"quarter": "Q1'26", "actual": 2.40, "estimate": 2.15, "surprise_pct": 11.63}],
                "data_source": "fmp",
            },
        }
    if market:
        results["market"] = {
            "success": True,
            "data": {
                "current_price": 195.0,
                "high_52w": 220.0,
                "low_52w": 165.0,
                "avg_volume": 55000000,
                "price_change_1m": 0.05,
                "price_change_3m": -0.02,
                "data_source": "fmp",
            },
        }
    if technical:
        results["technical"] = {
            "success": True,
            "data": {
                "rsi": 58.0,
                "macd_signal": "bullish",
                "sma_50": 190.0,
                "sma_200": 185.0,
                "support": 188.0,
                "resistance": 205.0,
                "data_source": "fmp",
            },
        }
    if macro:
        results["macro"] = {
            "success": True,
            "data": {
                "fed_funds_rate": 4.5,
                "cpi_yoy": 2.8,
                "gdp_growth": 2.1,
                "unemployment_rate": 3.9,
                "yield_curve_spread": 0.15,
                "data_source": "fred",
            },
        }
    if options:
        results["options"] = {
            "success": True,
            "data": {
                "put_call_ratio": 0.85,
                "iv_percentile": 42.0,
                "unusual_activity": [],
                "data_source": "yfinance",
            },
        }
    if leadership:
        results["leadership"] = {
            "success": True,
            "data": {
                "overall_score": 82.0,
                "grade": "B+",
                "executive_summary": "Strong, stable leadership team with long tenures.",
                "red_flags": [],
                "data_source": "llm",
            },
        }
    # Mark missing agents as failed
    all_agents = {
        "fundamentals": fundamentals, "news": news, "earnings": earnings,
        "market": market, "technical": technical, "macro": macro,
        "options": options, "leadership": leadership,
    }
    for name, present in all_agents.items():
        if not present:
            results[name] = {"success": False, "data": None, "error": "Mock disabled"}
    return results


class TestThesisDataGate:
    """Tests for minimum data requirements."""

    def test_gate_passes_with_all_data(self):
        agent = ThesisAgent("AAPL", {"llm_config": {}}, _make_agent_results())
        passes, sources = agent._check_data_gate()
        assert passes is True
        assert "fundamentals" in sources

    def test_gate_fails_without_fundamentals(self):
        agent = ThesisAgent("AAPL", {"llm_config": {}}, _make_agent_results(fundamentals=False))
        passes, sources = agent._check_data_gate()
        assert passes is False

    def test_gate_fails_without_any_secondary(self):
        results = _make_agent_results(news=False, earnings=False, market=False)
        agent = ThesisAgent("AAPL", {"llm_config": {}}, results)
        passes, sources = agent._check_data_gate()
        assert passes is False

    def test_gate_passes_with_fundamentals_and_news_only(self):
        results = _make_agent_results(earnings=False, market=False, technical=False, macro=False, options=False, leadership=False)
        agent = ThesisAgent("AAPL", {"llm_config": {}}, results)
        passes, sources = agent._check_data_gate()
        assert passes is True
        assert "news" in sources


class TestThesisDataCompleteness:
    """Tests for deterministic completeness score."""

    def test_full_data_completeness(self):
        agent = ThesisAgent("AAPL", {"llm_config": {}}, _make_agent_results())
        score = agent._compute_data_completeness()
        assert score == pytest.approx(1.0, abs=0.01)

    def test_partial_data_completeness(self):
        results = _make_agent_results(technical=False, macro=False, options=False)
        agent = ThesisAgent("AAPL", {"llm_config": {}}, results)
        score = agent._compute_data_completeness()
        # Missing: technical(0.05) + macro(0.05) + options(0.05) = 0.15
        assert score == pytest.approx(0.85, abs=0.01)

    def test_minimal_data_completeness(self):
        results = _make_agent_results(
            earnings=False, market=False, technical=False,
            macro=False, options=False, leadership=False,
        )
        agent = ThesisAgent("AAPL", {"llm_config": {}}, results)
        score = agent._compute_data_completeness()
        # Only fundamentals(0.30) + news(0.15) = 0.45
        assert score == pytest.approx(0.45, abs=0.01)


class TestThesisTieredExtraction:
    """Tests for tiered data extraction from agent results."""

    def test_extract_rich_context_includes_fundamentals(self):
        agent = ThesisAgent("AAPL", {"llm_config": {}}, _make_agent_results())
        rich, metrics = agent._extract_tiered_data()
        assert "Apple Inc." in rich
        assert "383" in rich  # revenue
        assert "Technology" in rich

    def test_extract_rich_context_includes_news(self):
        agent = ThesisAgent("AAPL", {"llm_config": {}}, _make_agent_results())
        rich, metrics = agent._extract_tiered_data()
        assert "AI push" in rich or "Apple AI" in rich

    def test_extract_metrics_includes_rsi(self):
        agent = ThesisAgent("AAPL", {"llm_config": {}}, _make_agent_results())
        rich, metrics = agent._extract_tiered_data()
        assert "RSI" in metrics or "58" in metrics

    def test_extract_handles_missing_agents(self):
        results = _make_agent_results(technical=False, macro=False, options=False, leadership=False)
        agent = ThesisAgent("AAPL", {"llm_config": {}}, results)
        rich, metrics = agent._extract_tiered_data()
        # Should not crash, just omit missing sections
        assert "Apple Inc." in rich
        assert "RSI" not in metrics


def _make_extracted_facts():
    """Build mock Pass 1 extracted facts."""
    return {
        "company_context": "Apple is a $3T technology company.",
        "key_financials": [
            "Revenue $383B, growth 8%",
            "Gross margin 46%",
            "P/E 32.5",
            "Debt/Equity 1.73",
        ],
        "recent_developments": [
            "Apple AI push accelerates with new features",
            "iPhone sales slow in China",
        ],
        "management_signals": [
            "Confident tone on earnings call",
            "Guidance raised to $93-95B",
        ],
        "macro_technical_context": [
            "RSI 58 — neutral territory",
            "Fed funds at 4.5%",
        ],
        "potential_tensions": [
            "Revenue sustainability vs growth deceleration",
            "AI investment payoff timeline",
        ],
    }


def _make_valid_thesis():
    """Build a valid thesis output dict."""
    return {
        "bull_case": {
            "thesis": "Strong fundamentals and AI investment position Apple for growth.",
            "key_drivers": ["Revenue growth at 8%", "AI product expansion"],
            "catalysts": ["Q2 earnings", "WWDC product announcements"],
        },
        "bear_case": {
            "thesis": "Slowing China sales and high valuation limit upside.",
            "key_drivers": ["China market share loss", "P/E of 32.5 is stretched"],
            "catalysts": ["Next China sales report", "Fed rate decision"],
        },
        "tension_points": [
            {
                "topic": "Revenue Sustainability",
                "bull_view": "Revenue growth of 8% shows durable demand.",
                "bear_view": "Growth is decelerating and China sales are declining.",
                "evidence": ["Revenue $383B, growth 8%", "iPhone sales slow in China"],
                "resolution_catalyst": "Next quarter China revenue breakdown.",
            },
            {
                "topic": "AI Investment Payoff",
                "bull_view": "AI features will drive upgrade cycles and services revenue.",
                "bear_view": "AI spend has uncertain ROI and competes with entrenched players.",
                "evidence": ["Apple AI push accelerates with new features", "Guidance raised to $93-95B"],
                "resolution_catalyst": "WWDC developer adoption metrics.",
            },
        ],
        "management_questions": [
            {"role": "CEO", "question": "What is the AI monetization timeline?", "context": "AI investment is a key tension."},
            {"role": "CFO", "question": "How will China revenue trends impact margins?", "context": "China is the biggest bear concern."},
        ],
        "thesis_summary": "The core debate is whether AI investment can offset China headwinds.",
        "data_completeness": 0.85,
        "data_sources_used": ["fundamentals", "news", "earnings"],
    }


class TestThesisGuardrails:
    """Tests for validate_thesis_output() in llm_guardrails.py."""

    def test_valid_thesis_passes_cleanly(self):
        thesis = _make_valid_thesis()
        facts = _make_extracted_facts()
        validated, warnings = validate_thesis_output(thesis, facts, _make_agent_results())
        assert validated["bull_case"]["thesis"] != ""
        # May have minor warnings but should not error
        assert isinstance(warnings, list)

    def test_fabricated_evidence_flagged(self):
        thesis = _make_valid_thesis()
        thesis["tension_points"][0]["evidence"] = ["Revenue $500B growing 25%"]  # Not in facts
        facts = _make_extracted_facts()
        validated, warnings = validate_thesis_output(thesis, facts, _make_agent_results())
        assert any("evidence" in w.lower() or "ungrounded" in w.lower() for w in warnings)

    def test_generic_catalyst_flagged(self):
        thesis = _make_valid_thesis()
        thesis["tension_points"][0]["resolution_catalyst"] = "Time will tell."
        facts = _make_extracted_facts()
        validated, warnings = validate_thesis_output(thesis, facts, _make_agent_results())
        assert any("catalyst" in w.lower() or "generic" in w.lower() for w in warnings)

    def test_data_completeness_overridden_deterministically(self):
        thesis = _make_valid_thesis()
        thesis["data_completeness"] = 0.99  # LLM claimed 0.99 but real is 0.85
        facts = _make_extracted_facts()
        results = _make_agent_results()
        validated, warnings = validate_thesis_output(thesis, facts, results)
        # Should be overridden to the deterministic value
        assert validated["data_completeness"] != 0.99

    def test_contradiction_with_agent_data_flagged(self):
        thesis = _make_valid_thesis()
        # Bull claims negative revenue growth — contradicts fundamentals (8% growth)
        thesis["bull_case"]["thesis"] = "Revenue is declining rapidly."
        facts = _make_extracted_facts()
        results = _make_agent_results()
        validated, warnings = validate_thesis_output(thesis, facts, results)
        # Should flag the contradiction
        assert any("contradict" in w.lower() or "mismatch" in w.lower() or "revenue" in w.lower() for w in warnings)
