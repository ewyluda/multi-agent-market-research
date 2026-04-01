"""Tests for FMP earnings call transcript integration."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import aiohttp

from src.data_provider import OpenBBDataProvider


@pytest.fixture
def provider():
    """Create a data provider with FMP key configured."""
    return OpenBBDataProvider({"FMP_API_KEY": "test_key"})


@pytest.fixture
def provider_no_key():
    """Create a data provider without FMP key."""
    return OpenBBDataProvider({})


class TestGetEarningsTranscript:
    """Tests for OpenBBDataProvider.get_earnings_transcript()."""

    @pytest.mark.asyncio
    async def test_returns_none_without_fmp_key(self, provider_no_key):
        result = await provider_no_key.get_earnings_transcript("AAPL")
        assert result is None

    @pytest.mark.asyncio
    async def test_fetches_most_recent_transcript(self, provider):
        """When quarter/year not specified, fetches list first then transcript."""
        list_response = [{"quarter": 1, "year": 2026}]
        transcript_response = [{
            "symbol": "AAPL",
            "quarter": 1,
            "year": 2026,
            "date": "2026-01-30",
            "content": "Good afternoon everyone. Welcome to Apple's earnings call.",
        }]

        mock_responses = iter([
            _mock_aiohttp_response(200, list_response),
            _mock_aiohttp_response(200, transcript_response),
        ])

        with patch("src.data_provider.aiohttp.ClientSession") as mock_session_cls:
            mock_session = AsyncMock()
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=False)
            mock_session.get = lambda *a, **kw: next(mock_responses)
            mock_session_cls.return_value = mock_session

            result = await provider.get_earnings_transcript("AAPL")

        assert result is not None
        assert result["quarter"] == 1
        assert result["year"] == 2026
        assert "Welcome to Apple" in result["content"]
        assert result["data_source"] == "fmp"

    @pytest.mark.asyncio
    async def test_fetches_specific_quarter(self, provider):
        """When quarter/year specified, fetches transcript directly."""
        transcript_response = [{
            "symbol": "NVDA",
            "quarter": 4,
            "year": 2025,
            "date": "2025-11-20",
            "content": "Thank you for joining NVIDIA's Q4 earnings call.",
        }]

        with patch("src.data_provider.aiohttp.ClientSession") as mock_session_cls:
            mock_session = AsyncMock()
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=False)
            mock_session.get = lambda *a, **kw: _mock_aiohttp_response(200, transcript_response)
            mock_session_cls.return_value = mock_session

            result = await provider.get_earnings_transcript("NVDA", quarter=4, year=2025)

        assert result is not None
        assert result["quarter"] == 4
        assert result["year"] == 2025

    @pytest.mark.asyncio
    async def test_returns_none_on_402(self, provider):
        """FMP returns 402 for free-tier users on this endpoint."""
        with patch("src.data_provider.aiohttp.ClientSession") as mock_session_cls:
            mock_session = AsyncMock()
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=False)
            mock_session.get = lambda *a, **kw: _mock_aiohttp_response(402, [])
            mock_session_cls.return_value = mock_session

            result = await provider.get_earnings_transcript("AAPL")

        assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_on_empty_list(self, provider):
        """No transcripts available for ticker."""
        with patch("src.data_provider.aiohttp.ClientSession") as mock_session_cls:
            mock_session = AsyncMock()
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=False)
            mock_session.get = lambda *a, **kw: _mock_aiohttp_response(200, [])
            mock_session_cls.return_value = mock_session

            result = await provider.get_earnings_transcript("AAPL")

        assert result is None

    @pytest.mark.asyncio
    async def test_truncates_long_transcript(self, provider):
        """Transcripts longer than 16000 chars get smart-truncated (intro + Q&A)."""
        long_content = "A" * 20000
        transcript_response = [{
            "symbol": "AAPL",
            "quarter": 1,
            "year": 2026,
            "date": "2026-01-30",
            "content": long_content,
        }]

        with patch("src.data_provider.aiohttp.ClientSession") as mock_session_cls:
            mock_session = AsyncMock()
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=False)
            mock_session.get = lambda *a, **kw: _mock_aiohttp_response(200, transcript_response)
            mock_session_cls.return_value = mock_session

            result = await provider.get_earnings_transcript("AAPL", quarter=1, year=2026)

        assert result is not None
        assert len(result["content"]) < 20000
        assert "truncated" in result["content"]

    @pytest.mark.asyncio
    async def test_caches_result(self, provider):
        """Second call should return cached result without hitting API."""
        transcript_response = [{
            "symbol": "AAPL",
            "quarter": 2,
            "year": 2026,
            "date": "2026-04-25",
            "content": "Cached transcript content",
        }]

        call_count = 0

        with patch("src.data_provider.aiohttp.ClientSession") as mock_session_cls:
            mock_session = AsyncMock()
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=False)

            def track_get(*a, **kw):
                nonlocal call_count
                call_count += 1
                return _mock_aiohttp_response(200, transcript_response)

            mock_session.get = track_get
            mock_session_cls.return_value = mock_session

            r1 = await provider.get_earnings_transcript("AAPL", quarter=2, year=2026)
            r2 = await provider.get_earnings_transcript("AAPL", quarter=2, year=2026)

        assert r1 is not None
        assert r2 is not None
        assert r1["content"] == r2["content"]
        # Only 1 HTTP call — second was served from cache
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_handles_network_error(self, provider):
        """Network errors return None gracefully."""
        with patch("src.data_provider.aiohttp.ClientSession") as mock_session_cls:
            mock_session = AsyncMock()
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=False)

            def raise_error(*a, **kw):
                raise aiohttp.ClientError("Connection refused")

            mock_session.get = raise_error
            mock_session_cls.return_value = mock_session

            result = await provider.get_earnings_transcript("AAPL")

        assert result is None


def _mock_aiohttp_response(status, json_data):
    """Create a mock aiohttp response context manager."""
    mock_resp = AsyncMock()
    mock_resp.status = status
    mock_resp.json = AsyncMock(return_value=json_data)

    mock_ctx = AsyncMock()
    mock_ctx.__aenter__ = AsyncMock(return_value=mock_resp)
    mock_ctx.__aexit__ = AsyncMock(return_value=False)
    return mock_ctx
