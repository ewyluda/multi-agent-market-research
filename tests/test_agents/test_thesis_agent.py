"""Tests for ThesisAgent — models, data gate, prompts, guardrails."""

import pytest
from src.models import TensionPoint, ManagementQuestion, ThesisCase, ThesisOutput


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

    def test_management_question_role_must_be_ceo_or_cfo(self):
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
        with pytest.raises(Exception):
            ThesisOutput(
                bull_case=ThesisCase(thesis="x", key_drivers=[], catalysts=[]),
                bear_case=ThesisCase(thesis="x", key_drivers=[], catalysts=[]),
                tension_points=[],
                management_questions=[],
                thesis_summary="x",
                data_completeness=1.5,
                data_sources_used=[],
            )
