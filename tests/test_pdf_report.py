"""Tests for PDF report generation."""

import pytest

from src.pdf_report import PDFReportGenerator


@pytest.fixture
def sample_analysis_data():
    """Realistic analysis data matching db_manager.get_analysis_with_agents() structure."""
    return {
        "id": 1,
        "ticker": "AAPL",
        "timestamp": "2025-02-07T12:00:00",
        "recommendation": "BUY",
        "confidence_score": 0.78,
        "overall_sentiment_score": 0.35,
        "solution_agent_reasoning": (
            "1. Fundamentals are strong with a health score of 75/100 and solid earnings.\n"
            "2. The equity research report highlights a strong competitive moat.\n"
            "3. Market conditions show a clear uptrend with increasing volume.\n"
            "4. Sentiment is positive driven by strong earnings and AI growth.\n"
            "5. Technical signals are bullish with RSI at 62 and MACD positive.\n"
            "6. Options flow shows neutral put/call ratio with no unusual activity.\n"
            "7. Macro environment is supportive with low unemployment.\n"
            "8. Earnings trends show consistent beats.\n"
            "9. Key risks include valuation and macro headwinds.\n"
            "10. Risk/reward is favorable at current levels.\n"
            "11. Final recommendation is BUY with medium position size."
        ),
        "duration_seconds": 32.5,
        "agents": [
            {
                "agent_type": "market",
                "success": True,
                "data": {
                    "current_price": 183.15,
                    "trend": "uptrend",
                    "data_source": "alpha_vantage",
                    "summary": "AAPL is in a clear uptrend with increasing volume.",
                },
                "duration_seconds": 2.1,
                "error": None,
            },
            {
                "agent_type": "technical",
                "success": True,
                "data": {
                    "indicators": {
                        "rsi": {"value": 62.5, "interpretation": "neutral"},
                        "macd": {"interpretation": "bullish crossover"},
                    },
                    "signals": {"overall": "bullish", "strength": 65},
                    "data_source": "alpha_vantage",
                    "summary": "Technical signals are bullish with RSI at 62.5.",
                },
                "duration_seconds": 3.2,
                "error": None,
            },
            {
                "agent_type": "options",
                "success": True,
                "data": {
                    "put_call_ratio": 0.85,
                    "put_call_oi_ratio": 1.1,
                    "max_pain": 180.0,
                    "overall_signal": "neutral",
                    "data_source": "yfinance",
                    "summary": "Options flow is neutral with P/C ratio of 0.85.",
                },
                "duration_seconds": 1.8,
                "error": None,
            },
            {
                "agent_type": "fundamentals",
                "success": True,
                "data": {
                    "company_name": "Apple Inc",
                    "health_score": 75,
                    "pe_ratio": 28.5,
                    "data_source": "alpha_vantage",
                    "summary": "Apple has strong fundamentals with health score 75/100.",
                },
                "duration_seconds": 4.5,
                "error": None,
            },
            {
                "agent_type": "sentiment",
                "success": True,
                "data": {
                    "overall_sentiment": 0.35,
                    "confidence": 0.75,
                    "summary": "Sentiment is positive driven by earnings beats.",
                },
                "duration_seconds": 5.0,
                "error": None,
            },
            {
                "agent_type": "macro",
                "success": True,
                "data": {
                    "economic_cycle": "expansion",
                    "risk_environment": "moderate",
                    "data_source": "alpha_vantage",
                    "summary": "Macro environment is supportive with low unemployment.",
                },
                "duration_seconds": 2.0,
                "error": None,
            },
            {
                "agent_type": "news",
                "success": True,
                "data": {
                    "total_count": 15,
                    "key_headlines": [{"title": "Apple Reports Record Revenue"}],
                    "data_source": "alpha_vantage",
                    "summary": "15 articles found, mostly positive coverage.",
                },
                "duration_seconds": 1.5,
                "error": None,
            },
        ],
        "sentiment_factors": {
            "earnings": {"score": 0.5, "weight": 0.3, "contribution": 0.15},
            "guidance": {"score": 0.3, "weight": 0.4, "contribution": 0.12},
            "stock_reactions": {"score": 0.4, "weight": 0.2, "contribution": 0.08},
            "strategic_news": {"score": 0.2, "weight": 0.1, "contribution": 0.02},
        },
    }


@pytest.fixture
def generator():
    """Create a PDFReportGenerator instance."""
    return PDFReportGenerator()


class TestPDFReportGenerator:
    """Tests for PDFReportGenerator.generate()."""

    def test_generate_returns_pdf_bytes(self, generator, sample_analysis_data):
        """Full analysis data produces non-empty bytes starting with PDF header."""
        result = generator.generate(sample_analysis_data)
        assert isinstance(result, bytes)
        assert len(result) > 0
        assert result[:5] == b"%PDF-"

    def test_generate_with_minimal_data(self, generator):
        """Minimal data (just ticker and timestamp) still produces valid PDF."""
        minimal = {
            "id": 1,
            "ticker": "TEST",
            "timestamp": "2025-01-01T00:00:00",
            "recommendation": None,
            "confidence_score": None,
            "overall_sentiment_score": None,
            "solution_agent_reasoning": None,
            "duration_seconds": None,
            "agents": [],
            "sentiment_factors": {},
        }
        result = generator.generate(minimal)
        assert isinstance(result, bytes)
        assert result[:5] == b"%PDF-"

    def test_generate_with_all_agents(self, generator, sample_analysis_data):
        """Full data with all 7 agents produces valid PDF."""
        result = generator.generate(sample_analysis_data)
        assert isinstance(result, bytes)
        assert len(result) > 1000  # Should be a substantial PDF

    def test_generate_with_missing_agents(self, generator):
        """Data with empty agents list still produces valid PDF."""
        data = {
            "id": 2,
            "ticker": "NVDA",
            "timestamp": "2025-02-07T12:00:00",
            "recommendation": "HOLD",
            "confidence_score": 0.5,
            "overall_sentiment_score": 0.0,
            "solution_agent_reasoning": "Neutral outlook.",
            "duration_seconds": 10.0,
            "agents": [],
            "sentiment_factors": {},
        }
        result = generator.generate(data)
        assert isinstance(result, bytes)
        assert result[:5] == b"%PDF-"

    def test_generate_with_failed_agents(self, generator):
        """Agents with success=False and error messages are handled gracefully."""
        data = {
            "id": 3,
            "ticker": "TSLA",
            "timestamp": "2025-02-07T12:00:00",
            "recommendation": "SELL",
            "confidence_score": 0.65,
            "overall_sentiment_score": -0.4,
            "solution_agent_reasoning": "Bearish outlook due to data failures.",
            "duration_seconds": 15.0,
            "agents": [
                {
                    "agent_type": "market",
                    "success": False,
                    "data": None,
                    "duration_seconds": 0.0,
                    "error": "API timeout",
                },
                {
                    "agent_type": "technical",
                    "success": False,
                    "data": {},
                    "duration_seconds": 0.0,
                    "error": "Rate limited",
                },
            ],
            "sentiment_factors": {},
        }
        result = generator.generate(data)
        assert isinstance(result, bytes)
        assert result[:5] == b"%PDF-"

    def test_generate_handles_special_characters(self, generator):
        """Special characters in text don't crash the PDF generator."""
        data = {
            "id": 4,
            "ticker": "T&T",
            "timestamp": "2025-02-07T12:00:00",
            "recommendation": "BUY",
            "confidence_score": 0.8,
            "overall_sentiment_score": 0.5,
            "solution_agent_reasoning": 'Price < $100 & P/E > 20. Special chars: "quotes" and <tags>.',
            "duration_seconds": 5.0,
            "agents": [
                {
                    "agent_type": "news",
                    "success": True,
                    "data": {"summary": 'Headlines say "Buy & Hold" for <strong>gains</strong>.'},
                    "duration_seconds": 1.0,
                    "error": None,
                },
            ],
            "sentiment_factors": {},
        }
        result = generator.generate(data)
        assert isinstance(result, bytes)
        assert result[:5] == b"%PDF-"

    def test_generate_with_buy_recommendation(self, generator, sample_analysis_data):
        """BUY recommendation produces valid PDF without errors."""
        sample_analysis_data["recommendation"] = "BUY"
        result = generator.generate(sample_analysis_data)
        assert isinstance(result, bytes)
        assert len(result) > 0

    def test_generate_with_sell_recommendation(self, generator, sample_analysis_data):
        """SELL recommendation produces valid PDF without errors."""
        sample_analysis_data["recommendation"] = "SELL"
        result = generator.generate(sample_analysis_data)
        assert isinstance(result, bytes)
        assert len(result) > 0

    def test_generate_with_hold_recommendation(self, generator, sample_analysis_data):
        """HOLD recommendation produces valid PDF without errors."""
        sample_analysis_data["recommendation"] = "HOLD"
        result = generator.generate(sample_analysis_data)
        assert isinstance(result, bytes)
        assert len(result) > 0

    def test_generate_with_none_data_dict(self, generator):
        """Agent with data=None doesn't crash the generator."""
        data = {
            "id": 5,
            "ticker": "META",
            "timestamp": "2025-02-07T12:00:00",
            "recommendation": "HOLD",
            "confidence_score": 0.6,
            "overall_sentiment_score": 0.1,
            "solution_agent_reasoning": "Limited data available.",
            "duration_seconds": 8.0,
            "agents": [
                {
                    "agent_type": "market",
                    "success": True,
                    "data": None,
                    "duration_seconds": 1.0,
                    "error": None,
                },
            ],
            "sentiment_factors": None,
        }
        result = generator.generate(data)
        assert isinstance(result, bytes)
        assert result[:5] == b"%PDF-"
