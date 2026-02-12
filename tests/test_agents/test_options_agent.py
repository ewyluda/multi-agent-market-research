"""Tests for OptionsAgent — options flow analysis and unusual activity detection."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.agents.options_agent import OptionsAgent


# ─── Fixtures ───


@pytest.fixture
def av_realtime_options_response():
    """Sample AV REALTIME_OPTIONS response with mixed calls/puts."""
    return {
        "data": [
            {
                "contractID": "AAPL250221C00180000",
                "symbol": "AAPL",
                "expiration": "2025-02-21",
                "strike": "180.00",
                "type": "call",
                "last": "5.20",
                "mark": "5.25",
                "bid": "5.10",
                "ask": "5.40",
                "volume": "15000",
                "open_interest": "5000",
                "impliedVolatility": "0.35",
            },
            {
                "contractID": "AAPL250221P00180000",
                "symbol": "AAPL",
                "expiration": "2025-02-21",
                "strike": "180.00",
                "type": "put",
                "last": "3.80",
                "mark": "3.85",
                "bid": "3.70",
                "ask": "4.00",
                "volume": "8000",
                "open_interest": "4000",
                "impliedVolatility": "0.38",
            },
            {
                "contractID": "AAPL250221C00185000",
                "symbol": "AAPL",
                "expiration": "2025-02-21",
                "strike": "185.00",
                "type": "call",
                "last": "2.10",
                "mark": "2.15",
                "bid": "2.00",
                "ask": "2.30",
                "volume": "25000",
                "open_interest": "3000",
                "impliedVolatility": "0.42",
            },
            {
                "contractID": "AAPL250221P00175000",
                "symbol": "AAPL",
                "expiration": "2025-02-21",
                "strike": "175.00",
                "type": "put",
                "last": "1.50",
                "mark": "1.55",
                "bid": "1.40",
                "ask": "1.70",
                "volume": "6000",
                "open_interest": "8000",
                "impliedVolatility": "0.30",
            },
            {
                "contractID": "AAPL250228C00190000",
                "symbol": "AAPL",
                "expiration": "2025-02-28",
                "strike": "190.00",
                "type": "call",
                "last": "1.00",
                "mark": "1.05",
                "bid": "0.90",
                "ask": "1.20",
                "volume": "3000",
                "open_interest": "2000",
                "impliedVolatility": "0.45",
            },
        ]
    }


# ─── TestOptionsAgentAnalyze ───


class TestOptionsAgentAnalyze:
    """Tests for OptionsAgent.analyze() and its helper methods."""

    async def test_analyze_empty_contracts(self, make_agent):
        """Empty contracts list yields neutral signal with None ratios."""
        agent = make_agent(OptionsAgent, "AAPL")
        raw_data = {"ticker": "AAPL", "source": "none", "contracts": []}

        result = await agent.analyze(raw_data)

        assert result["overall_signal"] == "neutral"
        assert result["put_call_ratio"] is None
        assert result["put_call_oi_ratio"] is None
        assert result["max_pain"] is None
        assert result["unusual_activity"] == []
        assert result["highest_iv_contracts"] == []
        assert result["near_term_summary"] == {}
        assert "No options data available" in result["summary"]

    async def test_put_call_ratio_calculation(
        self, make_agent, av_realtime_options_response
    ):
        """P/C volume ratio = total put volume / total call volume."""
        agent = make_agent(OptionsAgent, "AAPL")
        contracts = av_realtime_options_response["data"]
        raw_data = {"ticker": "AAPL", "source": "alpha_vantage", "contracts": contracts}

        result = await agent.analyze(raw_data)

        # Calls: 15000 + 25000 + 3000 = 43000
        # Puts:  8000 + 6000 = 14000
        # Ratio: 14000 / 43000 = 0.326 (rounded to 3 decimals)
        assert result["put_call_ratio"] == pytest.approx(14000 / 43000, abs=0.001)

    async def test_put_call_oi_ratio_calculation(
        self, make_agent, av_realtime_options_response
    ):
        """P/C OI ratio = total put OI / total call OI."""
        agent = make_agent(OptionsAgent, "AAPL")
        contracts = av_realtime_options_response["data"]
        raw_data = {"ticker": "AAPL", "source": "alpha_vantage", "contracts": contracts}

        result = await agent.analyze(raw_data)

        # Call OI: 5000 + 3000 + 2000 = 10000
        # Put OI:  4000 + 8000 = 12000
        # Ratio: 12000 / 10000 = 1.2
        assert result["put_call_oi_ratio"] == pytest.approx(1.2, abs=0.001)

    async def test_max_pain_calculation(self, make_agent, av_realtime_options_response):
        """Max pain is the strike where total option holder pain is minimized."""
        agent = make_agent(OptionsAgent, "AAPL")
        contracts = av_realtime_options_response["data"]
        raw_data = {"ticker": "AAPL", "source": "alpha_vantage", "contracts": contracts}

        result = await agent.analyze(raw_data)

        # Unique strikes: 175, 180, 185, 190
        # Max pain should be one of these — verify it is a valid strike
        assert result["max_pain"] in [175.0, 180.0, 185.0, 190.0]

        # Manually verify: at each strike, compute pain
        # At 175: calls all OOB (pain=0), puts: 180-175=5*4000=20000
        #   total=20000
        # At 180: calls: 0 (180 not > 180), puts: 180-175 OOB for 175 put (180>175 => 0), 180 put OOB (180 not < 180)
        #   calls at 180: test_price 180 > strike 180? No. calls at 185: 180>185? No. calls at 190: 180>190? No.
        #   puts at 180: 180 < 180? No. puts at 175: 180 < 175? No.
        #   total = 0
        # At 180, pain = 0 — this should be max pain
        assert result["max_pain"] == 180.0

    async def test_unusual_activity_detection(
        self, make_agent, av_realtime_options_response
    ):
        """Contracts with volume > 2x open interest are flagged as unusual."""
        agent = make_agent(OptionsAgent, "AAPL")
        contracts = av_realtime_options_response["data"]
        raw_data = {"ticker": "AAPL", "source": "alpha_vantage", "contracts": contracts}

        result = await agent.analyze(raw_data)

        unusual = result["unusual_activity"]

        # Check which contracts have vol > 2 * OI:
        # AAPL250221C00180000: vol=15000, OI=5000  => 15000 > 10000 => YES (ratio=3.0)
        # AAPL250221P00180000: vol=8000, OI=4000   => 8000 > 8000   => NO (not strictly >)
        # AAPL250221C00185000: vol=25000, OI=3000  => 25000 > 6000  => YES (ratio=8.33)
        # AAPL250221P00175000: vol=6000, OI=8000   => 6000 > 16000  => NO
        # AAPL250228C00190000: vol=3000, OI=2000   => 3000 > 4000   => NO
        # Wait, re-check: threshold=2.0, condition is volume > oi * threshold
        # AAPL250221C00180000: 15000 > 5000*2=10000 => YES
        # AAPL250221P00180000: 8000 > 4000*2=8000   => NO (not strictly >)
        # AAPL250221C00185000: 25000 > 3000*2=6000  => YES
        # AAPL250221P00175000: 6000 > 8000*2=16000  => NO
        # AAPL250228C00190000: 3000 > 2000*2=4000   => NO
        assert len(unusual) == 2

        # Should be sorted by vol/oi ratio descending
        # 185 call: 25000/3000 = 8.33
        # 180 call: 15000/5000 = 3.0
        assert unusual[0]["contractID"] == "AAPL250221C00185000"
        assert unusual[0]["vol_oi_ratio"] == pytest.approx(8.33, abs=0.01)
        assert unusual[1]["contractID"] == "AAPL250221C00180000"
        assert unusual[1]["vol_oi_ratio"] == pytest.approx(3.0, abs=0.01)

    async def test_highest_iv_contracts(
        self, make_agent, av_realtime_options_response
    ):
        """Top 5 contracts sorted by implied volatility descending."""
        agent = make_agent(OptionsAgent, "AAPL")
        contracts = av_realtime_options_response["data"]
        raw_data = {"ticker": "AAPL", "source": "alpha_vantage", "contracts": contracts}

        result = await agent.analyze(raw_data)

        iv_contracts = result["highest_iv_contracts"]

        # All 5 contracts have IV > 0, so all should appear
        assert len(iv_contracts) == 5

        # Should be sorted by IV descending:
        # 0.45 (190C), 0.42 (185C), 0.38 (180P), 0.35 (180C), 0.30 (175P)
        ivs = [c["implied_volatility"] for c in iv_contracts]
        assert ivs == sorted(ivs, reverse=True)
        assert iv_contracts[0]["implied_volatility"] == pytest.approx(0.45, abs=0.0001)
        assert iv_contracts[0]["contractID"] == "AAPL250228C00190000"

    async def test_signal_determination_bullish(self, make_agent):
        """Low P/C ratio + dominant unusual call activity yields bullish signal."""
        agent = make_agent(OptionsAgent, "AAPL")

        # Craft contracts: heavy call volume, low put volume
        contracts = [
            {"contractID": "C1", "type": "call", "strike": "180", "expiration": "2025-02-21",
             "volume": "50000", "open_interest": "5000", "impliedVolatility": "0.30"},
            {"contractID": "C2", "type": "call", "strike": "185", "expiration": "2025-02-21",
             "volume": "40000", "open_interest": "4000", "impliedVolatility": "0.32"},
            {"contractID": "P1", "type": "put", "strike": "175", "expiration": "2025-02-21",
             "volume": "5000", "open_interest": "3000", "impliedVolatility": "0.28"},
        ]
        raw_data = {"ticker": "AAPL", "source": "alpha_vantage", "contracts": contracts}

        result = await agent.analyze(raw_data)

        # P/C ratio = 5000 / 90000 = 0.056 (< 0.5 => +2)
        # Unusual calls: C1 (50k > 10k), C2 (40k > 8k) = 2 unusual calls
        # Unusual puts: P1 (5000 > 6000) = NO
        # unusual_calls (2) > unusual_puts (0) * 2 => +1
        # Score = +3 => bullish
        assert result["overall_signal"] == "bullish"

    async def test_signal_determination_bearish(self, make_agent):
        """High P/C ratio + dominant unusual put activity yields bearish signal."""
        agent = make_agent(OptionsAgent, "AAPL")

        # Craft contracts: heavy put volume, low call volume
        contracts = [
            {"contractID": "C1", "type": "call", "strike": "180", "expiration": "2025-02-21",
             "volume": "3000", "open_interest": "5000", "impliedVolatility": "0.30"},
            {"contractID": "P1", "type": "put", "strike": "175", "expiration": "2025-02-21",
             "volume": "50000", "open_interest": "4000", "impliedVolatility": "0.40"},
            {"contractID": "P2", "type": "put", "strike": "170", "expiration": "2025-02-21",
             "volume": "40000", "open_interest": "3000", "impliedVolatility": "0.42"},
        ]
        raw_data = {"ticker": "AAPL", "source": "alpha_vantage", "contracts": contracts}

        result = await agent.analyze(raw_data)

        # P/C ratio = 90000 / 3000 = 30.0 (> 1.5 => -2)
        # Unusual puts: P1 (50k > 8k), P2 (40k > 6k) = 2 unusual puts
        # Unusual calls: C1 (3k > 10k) = NO
        # unusual_puts (2) > unusual_calls (0) * 2 => -1
        # Score = -3 => bearish
        assert result["overall_signal"] == "bearish"

    async def test_summary_generation(
        self, make_agent, av_realtime_options_response
    ):
        """Summary string includes key metrics: P/C ratio, max pain, signal."""
        agent = make_agent(OptionsAgent, "AAPL")
        contracts = av_realtime_options_response["data"]
        raw_data = {"ticker": "AAPL", "source": "alpha_vantage", "contracts": contracts}

        result = await agent.analyze(raw_data)

        summary = result["summary"]
        assert "P/C ratio" in summary
        assert "Max pain" in summary
        assert "Signal" in summary
        assert "[Source: alpha_vantage]" in summary


# ─── TestOptionsAgentFetchData ───


class TestOptionsAgentFetchData:
    """Tests for OptionsAgent.fetch_data() — AV primary with yfinance fallback."""

    async def test_fetch_data_av_primary(self, make_agent, av_realtime_options_response):
        """When AV returns data, source is 'alpha_vantage' and contracts are populated."""
        agent = make_agent(OptionsAgent, "AAPL")

        with patch.object(
            agent, "_fetch_av_realtime_options", new_callable=AsyncMock
        ) as mock_rt, patch.object(
            agent, "_fetch_av_historical_options", new_callable=AsyncMock
        ) as mock_hist:
            mock_rt.return_value = {
                "contracts": av_realtime_options_response["data"],
                "source": "realtime",
            }
            mock_hist.return_value = None

            result = await agent.fetch_data()

        assert result["source"] == "alpha_vantage"
        assert len(result["contracts"]) == 5
        assert result["av_source_type"] == "realtime"

    async def test_fetch_data_av_fallback_to_yfinance(self, make_agent):
        """When AV returns None for both endpoints, falls back to yfinance."""
        agent = make_agent(OptionsAgent, "AAPL")

        yf_contracts = [
            {"contractID": "YF1", "type": "call", "strike": "180", "expiration": "2025-03-21",
             "volume": "100", "open_interest": "50", "impliedVolatility": "0.30"},
        ]

        with patch.object(
            agent, "_fetch_av_realtime_options", new_callable=AsyncMock
        ) as mock_rt, patch.object(
            agent, "_fetch_av_historical_options", new_callable=AsyncMock
        ) as mock_hist, patch.object(
            agent, "_fetch_yfinance_options", new_callable=AsyncMock
        ) as mock_yf:
            mock_rt.return_value = None
            mock_hist.return_value = None
            mock_yf.return_value = {"contracts": yf_contracts, "source": "yfinance"}

            result = await agent.fetch_data()

        assert result["source"] == "yfinance"
        assert len(result["contracts"]) == 1
        mock_yf.assert_awaited_once()

    async def test_fetch_data_no_data_available(self, make_agent):
        """When both AV and yfinance return nothing, source is 'none' with empty contracts."""
        agent = make_agent(OptionsAgent, "AAPL")

        with patch.object(
            agent, "_fetch_av_realtime_options", new_callable=AsyncMock
        ) as mock_rt, patch.object(
            agent, "_fetch_av_historical_options", new_callable=AsyncMock
        ) as mock_hist, patch.object(
            agent, "_fetch_yfinance_options", new_callable=AsyncMock
        ) as mock_yf:
            mock_rt.return_value = None
            mock_hist.return_value = None
            mock_yf.return_value = None

            result = await agent.fetch_data()

        assert result["source"] == "none"
        assert result["contracts"] == []

    async def test_fetch_data_no_av_key(self, test_config, av_cache, av_rate_limiter):
        """When ALPHA_VANTAGE_API_KEY is absent, skips AV and goes straight to yfinance."""
        config_no_av = {**test_config, "ALPHA_VANTAGE_API_KEY": ""}
        agent = OptionsAgent("AAPL", config_no_av)
        agent._av_cache = av_cache
        agent._rate_limiter = av_rate_limiter
        agent._shared_session = None

        yf_contracts = [
            {"contractID": "YF1", "type": "call", "strike": "180", "expiration": "2025-03-21",
             "volume": "200", "open_interest": "100", "impliedVolatility": "0.35"},
        ]

        with patch.object(
            agent, "_fetch_av_realtime_options", new_callable=AsyncMock
        ) as mock_rt, patch.object(
            agent, "_fetch_av_historical_options", new_callable=AsyncMock
        ) as mock_hist, patch.object(
            agent, "_fetch_yfinance_options", new_callable=AsyncMock
        ) as mock_yf:
            mock_yf.return_value = {"contracts": yf_contracts, "source": "yfinance"}

            result = await agent.fetch_data()

        # AV endpoints should never be called when key is empty
        mock_rt.assert_not_awaited()
        mock_hist.assert_not_awaited()
        assert result["source"] == "yfinance"
        assert len(result["contracts"]) == 1


# ─── TestOptionsAgentHelpers ───


class TestOptionsAgentHelpers:
    """Tests for OptionsAgent utility / helper methods."""

    def test_safe_float_valid(self, make_agent):
        """_safe_float converts valid numeric strings to float."""
        agent = make_agent(OptionsAgent, "AAPL")

        assert agent._safe_float("3.14") == pytest.approx(3.14)
        assert agent._safe_float("0") == 0.0
        assert agent._safe_float("-1.5") == pytest.approx(-1.5)
        assert agent._safe_float(42) == 42.0

    def test_safe_float_invalid(self, make_agent):
        """_safe_float returns default for invalid inputs."""
        agent = make_agent(OptionsAgent, "AAPL")

        assert agent._safe_float("not_a_number") == 0.0
        assert agent._safe_float(None) == 0.0
        assert agent._safe_float("") == 0.0
        assert agent._safe_float(None, default=5.0) == 5.0

    def test_safe_int_valid(self, make_agent):
        """_safe_int converts valid numeric strings to int."""
        agent = make_agent(OptionsAgent, "AAPL")

        assert agent._safe_int("100") == 100
        assert agent._safe_int("3.9") == 3  # truncates via int(float(...))
        assert agent._safe_int(42) == 42
        assert agent._safe_int("0") == 0

    def test_safe_int_invalid(self, make_agent):
        """_safe_int returns default for invalid inputs."""
        agent = make_agent(OptionsAgent, "AAPL")

        assert agent._safe_int("abc") == 0
        assert agent._safe_int(None) == 0
        assert agent._safe_int("") == 0
        assert agent._safe_int(None, default=10) == 10

    def test_normalize_yf_contract(self, make_agent):
        """_normalize_yf_contract maps yfinance row fields to AV-compatible schema."""
        agent = make_agent(OptionsAgent, "AAPL")

        # Simulate a yfinance option chain row (pandas-like dict via .get())
        yf_row = MagicMock()
        yf_row.get = lambda key, default=None: {
            "contractSymbol": "AAPL250321C00180000",
            "strike": 180.0,
            "lastPrice": 5.20,
            "bid": 5.10,
            "ask": 5.40,
            "volume": 15000,
            "openInterest": 5000,
            "impliedVolatility": 0.35,
        }.get(key, default)

        normalized = agent._normalize_yf_contract(yf_row, "call", "2025-03-21")

        assert normalized["contractID"] == "AAPL250321C00180000"
        assert normalized["symbol"] == "AAPL"
        assert normalized["expiration"] == "2025-03-21"
        assert normalized["strike"] == "180.0"
        assert normalized["type"] == "call"
        assert normalized["last"] == "5.2"
        assert normalized["bid"] == "5.1"
        assert normalized["ask"] == "5.4"
        assert normalized["volume"] == "15000"
        assert normalized["open_interest"] == "5000"
        assert normalized["impliedVolatility"] == "0.35"
        # mark = (bid + ask) / 2 = (5.1 + 5.4) / 2 = 5.25
        assert float(normalized["mark"]) == pytest.approx(5.25)
