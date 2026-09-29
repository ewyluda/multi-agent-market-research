"""Synthesis-phase time budgets and failure visibility (campaign session A2).

Regression guard: a 15s outer cap once wrapped every synthesis agent, silently dropping
the two-pass thesis/narrative agents from every analysis. Budgets are now applied once,
per agent, and every outcome is recorded in ``Orchestrator._synthesis_status``.
"""

import asyncio

import pytest

from src.config import Config
from src.orchestrator import Orchestrator


def _fake_agent(delay: float = 0.0, result=None, exc: Exception = None):
    class FakeAgent:
        def __init__(self, ticker, config, agent_results):
            self.ticker = ticker

        async def execute(self):
            await asyncio.sleep(delay)
            if exc is not None:
                raise exc
            return result if result is not None else {"success": True, "data": {"ok": True}}

    return FakeAgent


def _orchestrator(budgets):
    return Orchestrator(config={"AGENT_TIMEOUT": 30, "SYNTHESIS_TIMEOUTS": budgets})


def test_default_budgets_fit_two_pass_agents():
    # Two-pass agents must not share the 30s single-agent default (or the old 15s cap).
    assert Config.SYNTHESIS_TIMEOUTS["thesis"] >= 60
    assert Config.SYNTHESIS_TIMEOUTS["narrative"] >= 60
    assert set(Config.SYNTHESIS_TIMEOUTS) >= {
        "solution", "thesis", "narrative", "earnings_review", "risk_diff", "tag_extractor",
    }


@pytest.mark.asyncio
async def test_agent_within_budget_succeeds_and_records_ok():
    orch = _orchestrator({"thesis": 1.0})
    data = await orch._run_synthesis_agent("thesis", _fake_agent(delay=0.05), "NVDA", {})
    assert data == {"ok": True}
    status = orch._synthesis_status["thesis"]
    assert status["status"] == "ok"
    assert status["timeout_s"] == 1.0
    assert 0 <= status["elapsed_s"] < 1.0


@pytest.mark.asyncio
async def test_agent_over_budget_times_out_without_failing_run():
    orch = _orchestrator({"narrative": 0.1})
    data = await orch._run_synthesis_agent("narrative", _fake_agent(delay=1.0), "NVDA", {})
    assert data is None
    status = orch._synthesis_status["narrative"]
    assert status["status"] == "timeout"
    assert "0s budget" in status["error"] or "budget" in status["error"]
    assert status["elapsed_s"] >= 0.1


@pytest.mark.asyncio
async def test_each_agent_uses_its_own_budget():
    # A slow-but-allowed thesis must not be killed by a tighter budget meant for another agent.
    orch = _orchestrator({"thesis": 1.0, "tag_extractor": 0.05})
    thesis, tags = await asyncio.gather(
        orch._run_synthesis_agent("thesis", _fake_agent(delay=0.2), "NVDA", {}),
        orch._run_synthesis_agent("tag_extractor", _fake_agent(delay=0.2), "NVDA", {}),
    )
    assert thesis == {"ok": True}
    assert tags is None
    assert orch._synthesis_status["thesis"]["status"] == "ok"
    assert orch._synthesis_status["tag_extractor"]["status"] == "timeout"


@pytest.mark.asyncio
async def test_agent_reported_failure_is_recorded_with_reason():
    orch = _orchestrator({"risk_diff": 1.0})
    agent = _fake_agent(result={"success": False, "error": "EDGAR returned 503"})
    data = await orch._run_synthesis_agent("risk_diff", agent, "NVDA", {})
    assert data is None
    assert orch._synthesis_status["risk_diff"] == {
        **orch._synthesis_status["risk_diff"],
        "status": "failed",
        "error": "EDGAR returned 503",
    }


@pytest.mark.asyncio
async def test_exception_is_recorded_with_type_name():
    orch = _orchestrator({"earnings_review": 1.0})
    agent = _fake_agent(exc=ValueError("bad JSON from model"))
    data = await orch._run_synthesis_agent("earnings_review", agent, "NVDA", {})
    assert data is None
    status = orch._synthesis_status["earnings_review"]
    assert status["status"] == "error"
    assert status["error"].startswith("ValueError: bad JSON from model")


def test_unknown_agent_falls_back_to_agent_timeout():
    orch = _orchestrator({})
    assert orch._synthesis_timeout("something_new") == 30.0


@pytest.mark.asyncio
async def test_partial_result_is_recorded_as_partial():
    orch = _orchestrator({"earnings_review": 1.0})
    agent = _fake_agent(result={"success": True, "data": {"partial": True, "partial_reason": "llm_failed",
                                                          "partial_error": "TimeoutError: read timed out"}})
    data = await orch._run_synthesis_agent("earnings_review", agent, "NVDA", {})
    assert data["partial"] is True  # partial data is still returned for display
    status = orch._synthesis_status["earnings_review"]
    assert status["status"] == "partial"
    assert status["error"] == "TimeoutError: read timed out"
