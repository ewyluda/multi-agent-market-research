# Analysis Intelligence Upgrade — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make the analysis output meaningfully better by enabling V2 features, grounding the LLM in calibration data, validating tickers before pipeline runs, adding portfolio-level risk aggregation, fixing critical stability issues, uncapping change summaries, and adding a bulk analysis endpoint with a frontend calibration card.

**Architecture:** Seven independent work units touching backend config, orchestrator, solution agent, portfolio engine, rate limiter, database, API, and one frontend component. Each task is self-contained and testable in isolation.

**Tech Stack:** Python 3, FastAPI, SQLite, pytest, aiohttp, yfinance, React, Tailwind CSS v4, framer-motion

---

### Task 1: Enable V2 Feature Flags by Default

**Files:**
- Modify: `src/config.py:57-70`
- Modify: `tests/conftest.py:248-255`

**Step 1: Flip feature flag defaults in config.py**

In `src/config.py`, change these 11 lines from `"false"` to `"true"`:

```python
# Line 57-63: V2 feature flags
SIGNAL_CONTRACT_V2_ENABLED = os.getenv("SIGNAL_CONTRACT_V2_ENABLED", "true").lower() == "true"
COT_PERSISTENCE_ENABLED = os.getenv("COT_PERSISTENCE_ENABLED", "true").lower() == "true"
PORTFOLIO_OPTIMIZER_V2_ENABLED = os.getenv("PORTFOLIO_OPTIMIZER_V2_ENABLED", "true").lower() == "true"
CALIBRATION_ECONOMICS_ENABLED = os.getenv("CALIBRATION_ECONOMICS_ENABLED", "true").lower() == "true"
ALERTS_V2_ENABLED = os.getenv("ALERTS_V2_ENABLED", "true").lower() == "true"
WATCHLIST_RANKING_ENABLED = os.getenv("WATCHLIST_RANKING_ENABLED", "true").lower() == "true"
UI_PM_DASHBOARD_ENABLED = os.getenv("UI_PM_DASHBOARD_ENABLED", "true").lower() == "true"

# Line 65-70: Scheduled rollout variants
SCHEDULED_SIGNAL_CONTRACT_V2_ENABLED = os.getenv("SCHEDULED_SIGNAL_CONTRACT_V2_ENABLED", "true").lower() == "true"
SCHEDULED_CALIBRATION_ECONOMICS_ENABLED = os.getenv("SCHEDULED_CALIBRATION_ECONOMICS_ENABLED", "true").lower() == "true"
SCHEDULED_PORTFOLIO_OPTIMIZER_V2_ENABLED = (
    os.getenv("SCHEDULED_PORTFOLIO_OPTIMIZER_V2_ENABLED", "true").lower() == "true"
)
SCHEDULED_ALERTS_V2_ENABLED = os.getenv("SCHEDULED_ALERTS_V2_ENABLED", "true").lower() == "true"
```

**Step 2: Update test_config fixture to match**

In `tests/conftest.py`, update the `test_config` fixture to set V2 flags to `True`:

```python
# Lines 248-255 — change False → True
"SIGNAL_CONTRACT_V2_ENABLED": True,
"CALIBRATION_ECONOMICS_ENABLED": True,
"PORTFOLIO_OPTIMIZER_V2_ENABLED": True,
"ALERTS_V2_ENABLED": True,
"SCHEDULED_SIGNAL_CONTRACT_V2_ENABLED": True,
"SCHEDULED_CALIBRATION_ECONOMICS_ENABLED": True,
"SCHEDULED_PORTFOLIO_OPTIMIZER_V2_ENABLED": True,
"SCHEDULED_ALERTS_V2_ENABLED": True,
```

**Step 3: Run full test suite to verify nothing breaks**

Run: `python -m pytest tests/ -v`
Expected: All 208 tests pass (some tests may need minor adjustments if they assert `analysis_schema_version == "v1"`)

**Step 4: Commit**

```bash
git add src/config.py tests/conftest.py
git commit -m "feat: enable all V2 feature flags by default"
```

---

### Task 2: Critical Stability — WAL Mode for SQLite

**Files:**
- Modify: `src/database.py:24-36`
- Test: `tests/test_database.py`

**Step 1: Write the failing test**

Add to `tests/test_database.py`:

```python
def test_wal_mode_enabled(db_manager):
    """Database uses WAL journal mode for concurrent access."""
    with db_manager.get_connection() as conn:
        result = conn.execute("PRAGMA journal_mode").fetchone()
        assert result[0] == "wal"
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_database.py::test_wal_mode_enabled -v`
Expected: FAIL — journal_mode will be "delete" (SQLite default)

**Step 3: Implement WAL mode in get_connection**

In `src/database.py`, modify the `get_connection` method (lines 24-36):

```python
@contextmanager
def get_connection(self):
    """Context manager for database connections."""
    conn = sqlite3.connect(self.db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    try:
        yield conn
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise
    finally:
        conn.close()
```

**Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_database.py::test_wal_mode_enabled -v`
Expected: PASS

**Step 5: Run full database test suite**

Run: `python -m pytest tests/test_database.py -v`
Expected: All pass

**Step 6: Commit**

```bash
git add src/database.py tests/test_database.py
git commit -m "fix: enable WAL journal mode and busy_timeout for SQLite concurrency"
```

---

### Task 3: Critical Stability — Rate Limiter While-Loop

**Files:**
- Modify: `src/av_rate_limiter.py:70-75`
- Test: `tests/test_av_rate_limiter.py`

**Step 1: Write the failing test**

Add to `tests/test_av_rate_limiter.py`:

```python
async def test_minute_window_retries_without_recursion(self):
    """acquire() retries via loop (not recursion) when minute window is full."""
    limiter = AVRateLimiter(requests_per_minute=2, requests_per_day=100)
    # Fill minute window
    await limiter.acquire()
    await limiter.acquire()
    # Third call should wait and succeed (not blow stack)
    # We patch sleep to avoid actual delay
    import unittest.mock
    with unittest.mock.patch("asyncio.sleep", new_callable=unittest.mock.AsyncMock) as mock_sleep:
        # Simulate time passing by clearing timestamps after sleep
        original_acquire = limiter.acquire

        async def patched_acquire():
            # On first sleep call, clear the minute window to simulate time passing
            if mock_sleep.call_count == 0:
                pass
            result = await original_acquire()
            return result

        # Clear timestamps to simulate time having passed
        mock_sleep.side_effect = lambda _: setattr(limiter, '_minute_timestamps', [])
        result = await limiter.acquire()
        assert result is True
        assert mock_sleep.called
```

**Step 2: Run test to verify current behavior**

Run: `python -m pytest tests/test_av_rate_limiter.py::TestAVRateLimiter::test_minute_window_retries_without_recursion -v`

**Step 3: Replace recursion with while-loop**

In `src/av_rate_limiter.py`, replace lines 35-85 with:

```python
async def acquire(self) -> bool:
    """
    Acquire permission to make one AV API request.

    Blocks until a slot is available within the per-minute window.
    Returns False if the daily limit has been reached.

    Returns:
        True if request can proceed, False if daily limit exhausted
    """
    while True:
        async with self._lock:
            now = time.time()

            # Reset daily counter if 24h have passed
            if now >= self._daily_reset_time:
                self._daily_count = 0
                self._daily_reset_time = now + 86400

            # Check daily limit
            if self._daily_count >= self.requests_per_day:
                self.logger.warning(
                    f"Alpha Vantage daily limit reached ({self.requests_per_day} requests). "
                    "Agents will use fallback sources."
                )
                return False

            # Clean up old timestamps (older than 60 seconds)
            self._minute_timestamps = [t for t in self._minute_timestamps if t > now - 60.0]

            # If minute window full, calculate wait time
            if len(self._minute_timestamps) >= self.requests_per_minute:
                oldest = self._minute_timestamps[0]
                wait_time = 60.0 - (now - oldest) + 0.1  # +0.1s buffer
            else:
                # Slot available — record and return
                self._minute_timestamps.append(time.time())
                self._daily_count += 1
                self.logger.debug(
                    f"AV rate limiter: {self._daily_count}/{self.requests_per_day} daily, "
                    f"{len(self._minute_timestamps)}/{self.requests_per_minute} per minute"
                )
                return True

        # Wait outside the lock if needed, then loop back to retry
        self.logger.info(f"Rate limiter: waiting {wait_time:.1f}s for AV minute window")
        await asyncio.sleep(wait_time)
```

**Step 4: Run rate limiter test suite**

Run: `python -m pytest tests/test_av_rate_limiter.py -v`
Expected: All pass

**Step 5: Commit**

```bash
git add src/av_rate_limiter.py tests/test_av_rate_limiter.py
git commit -m "fix: replace recursive acquire() with while-loop to prevent stack overflow"
```

---

### Task 4: Critical Stability — Protect _save_to_database

**Files:**
- Modify: `src/orchestrator.py:216-219`
- Test: `tests/test_orchestrator.py`

**Step 1: Write the failing test**

Add to `tests/test_orchestrator.py`:

```python
@pytest.mark.asyncio
async def test_db_write_failure_still_returns_analysis(test_config, tmp_db_path):
    """If _save_to_database fails, analyze_ticker still returns the analysis result."""
    db = DatabaseManager(tmp_db_path)
    orch = Orchestrator(config=test_config, db_manager=db)

    mock_results = {
        "news": _make_agent_result("news"),
        "market": _make_agent_result("market", data={"current_price": 150.0, "trend": "uptrend"}),
        "fundamentals": _make_agent_result("fundamentals"),
        "technical": _make_agent_result("technical"),
        "macro": _make_agent_result("macro"),
        "options": _make_agent_result("options"),
        "sentiment": _make_agent_result("sentiment"),
    }

    with patch.object(orch, "_run_agents", new_callable=AsyncMock, return_value=mock_results), \
         patch.object(orch, "_run_solution_agent", new_callable=AsyncMock, return_value=_make_solution_result()["data"]), \
         patch.object(orch, "_save_to_database", side_effect=Exception("DB locked")), \
         patch.object(orch, "_create_shared_session", new_callable=AsyncMock), \
         patch.object(orch, "_close_shared_session", new_callable=AsyncMock), \
         patch.object(orch, "_notify_progress", new_callable=AsyncMock):
        result = await orch.analyze_ticker("AAPL")

    assert result["success"] is True
    assert result["analysis_id"] is None
    assert result["analysis"]["recommendation"] == "BUY"
    assert result.get("db_write_warning") is not None
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_orchestrator.py::test_db_write_failure_still_returns_analysis -v`
Expected: FAIL — currently the exception propagates and `success` is `False`

**Step 3: Wrap _save_to_database in try/except**

In `src/orchestrator.py`, replace the save block around line 216-219:

```python
            # Phase 3: Save to database
            await self._notify_progress("saving", ticker, 95)

            analysis_id = None
            db_write_warning = None
            try:
                analysis_id = self._save_to_database(ticker, agent_results, final_analysis, time.time() - start_time)
            except Exception as db_exc:
                self.logger.error(f"Database write failed for {ticker}: {db_exc}", exc_info=True)
                db_write_warning = f"Analysis completed but database save failed: {db_exc}"
```

Then update the calibration block (line ~221) to guard on `analysis_id`:

```python
            if analysis_id and self.config.get("CALIBRATION_ENABLED", True):
```

And the alerts block (~line 240):

```python
            if analysis_id and self.config.get("ALERTS_ENABLED", True):
```

And the return dict (~line 252):

```python
            result = {
                "success": True,
                "ticker": ticker,
                "analysis_id": analysis_id,
                "analysis": final_analysis,
                "agent_results": agent_results,
                "alerts_triggered": alerts_triggered,
                "duration_seconds": time.time() - start_time,
            }
            if db_write_warning:
                result["db_write_warning"] = db_write_warning
            return result
```

**Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_orchestrator.py::test_db_write_failure_still_returns_analysis -v`
Expected: PASS

**Step 5: Run full orchestrator test suite**

Run: `python -m pytest tests/test_orchestrator.py -v`
Expected: All pass

**Step 6: Commit**

```bash
git add src/orchestrator.py tests/test_orchestrator.py
git commit -m "fix: protect _save_to_database so DB failure doesn't discard completed analysis"
```

---

### Task 5: Ticker Validation Before Pipeline

**Files:**
- Modify: `src/orchestrator.py` (add `_validate_ticker` method)
- Test: `tests/test_orchestrator.py`

**Step 1: Write the failing tests**

Add to `tests/test_orchestrator.py`:

```python
@pytest.mark.asyncio
async def test_invalid_ticker_returns_error_without_running_agents(test_config, tmp_db_path):
    """Invalid ticker is caught before agents run, saving AV budget."""
    db = DatabaseManager(tmp_db_path)
    orch = Orchestrator(config=test_config, db_manager=db)

    with patch("yfinance.Ticker") as mock_yf:
        mock_yf.return_value.info = {"shortName": None}
        with patch.object(orch, "_run_agents", new_callable=AsyncMock) as mock_run:
            result = await orch.analyze_ticker("NVIDX")
            mock_run.assert_not_called()

    assert result["success"] is False
    assert "Unknown ticker" in result["error"]


@pytest.mark.asyncio
async def test_valid_ticker_caches_validation(test_config, tmp_db_path):
    """Second analysis of same ticker skips yfinance validation."""
    db = DatabaseManager(tmp_db_path)
    orch = Orchestrator(config=test_config, db_manager=db)

    with patch("yfinance.Ticker") as mock_yf:
        mock_yf.return_value.info = {"shortName": "NVIDIA Corp"}
        # First call validates
        await orch._validate_ticker("NVDA")
        # Second call should not hit yfinance
        mock_yf.reset_mock()
        await orch._validate_ticker("NVDA")
        mock_yf.assert_not_called()


@pytest.mark.asyncio
async def test_yfinance_failure_allows_ticker_through(test_config, tmp_db_path):
    """If yfinance is down, validation is skipped (fail-open)."""
    db = DatabaseManager(tmp_db_path)
    orch = Orchestrator(config=test_config, db_manager=db)

    with patch("yfinance.Ticker", side_effect=Exception("yfinance down")):
        # Should not raise — fail-open
        result = await orch._validate_ticker("AAPL")
        assert result is True
```

**Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_orchestrator.py::test_invalid_ticker_returns_error_without_running_agents tests/test_orchestrator.py::test_valid_ticker_caches_validation tests/test_orchestrator.py::test_yfinance_failure_allows_ticker_through -v`
Expected: FAIL — `_validate_ticker` doesn't exist yet

**Step 3: Implement _validate_ticker**

Add to `Orchestrator` class in `src/orchestrator.py`:

```python
# Class-level cache (shared across instances within same process)
_validated_tickers: set = set()

async def _validate_ticker(self, ticker: str) -> bool:
    """
    Validate that a ticker symbol corresponds to a real tradeable security.

    Uses yfinance for a lightweight check. Caches validated tickers in-memory.
    Fails open (returns True) if yfinance is unavailable.

    Args:
        ticker: Stock ticker symbol

    Returns:
        True if valid or validation skipped, False if definitely invalid
    """
    if ticker in self._validated_tickers:
        return True

    try:
        import yfinance as yf

        info = await asyncio.get_event_loop().run_in_executor(
            None, lambda: yf.Ticker(ticker).info
        )
        short_name = (info or {}).get("shortName")
        if not short_name:
            return False

        self._validated_tickers.add(ticker)
        return True
    except Exception as e:
        self.logger.warning(f"Ticker validation skipped for {ticker} (yfinance error: {e})")
        return True  # Fail-open
```

Then add the validation call at the start of `analyze_ticker()`, right after `ticker = ticker.upper()` and before `agents_to_run = ...`:

```python
        # Validate ticker is a real symbol before burning API budget
        if not await self._validate_ticker(ticker):
            return {
                "success": False,
                "ticker": ticker,
                "error": f"Unknown ticker symbol: {ticker}",
                "duration_seconds": time.time() - start_time,
            }
```

**Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_orchestrator.py::test_invalid_ticker_returns_error_without_running_agents tests/test_orchestrator.py::test_valid_ticker_caches_validation tests/test_orchestrator.py::test_yfinance_failure_allows_ticker_through -v`
Expected: PASS

**Step 5: Run full test suite**

Run: `python -m pytest tests/ -v`
Expected: All pass

**Step 6: Commit**

```bash
git add src/orchestrator.py tests/test_orchestrator.py
git commit -m "feat: validate ticker symbol with yfinance before running agent pipeline"
```

---

### Task 6: Feed Calibration Data into Solution Agent + DRY Prompt

**Files:**
- Modify: `src/agents/solution_agent.py`
- Modify: `src/orchestrator.py` (~line 420, solution agent instantiation)
- Test: `tests/test_agents/test_solution_agent.py`

**Step 1: Write the failing test**

Add to `tests/test_agents/test_solution_agent.py`:

```python
def test_build_prompt_includes_calibration_context():
    """When calibration_context is provided, prompt includes HISTORICAL ACCURACY section."""
    from src.agents.solution_agent import SolutionAgent

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


def test_build_prompt_without_calibration_omits_section():
    """When calibration_context is None/empty, prompt has no HISTORICAL ACCURACY section."""
    from src.agents.solution_agent import SolutionAgent

    agent = SolutionAgent("AAPL", {"llm_config": {}}, {})
    agent.calibration_context = None
    prompt = agent._build_prompt(
        news_data={}, sentiment_data={}, fundamentals_data={},
        market_data={}, technical_data={}, macro_data={}, options_data={},
    )
    assert "HISTORICAL ACCURACY" not in prompt
```

**Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_agents/test_solution_agent.py::test_build_prompt_includes_calibration_context tests/test_agents/test_solution_agent.py::test_build_prompt_without_calibration_omits_section -v`
Expected: FAIL — `_build_prompt` doesn't exist, `calibration_context` attribute doesn't exist

**Step 3: Implement changes in solution_agent.py**

3a. Add `calibration_context` to `__init__`:

```python
def __init__(self, ticker: str, config: Dict[str, Any], agent_results: Dict[str, Any]):
    super().__init__(ticker, config)
    self.agent_results = agent_results
    self.calibration_context: Optional[Dict[str, Any]] = None
```

3b. Extract the duplicated prompt into `_build_prompt()`:

Create a new method `_build_prompt(self, news_data, sentiment_data, fundamentals_data, market_data, technical_data, macro_data, options_data) -> str` that contains the shared prompt text (currently duplicated in `_synthesize_with_llm` and `_synthesize_with_openai`).

At the end of the prompt, before the "Using first-principles reasoning:" section, append the calibration block:

```python
        # Append calibration context if available
        calibration_section = ""
        if self.calibration_context:
            calibration_section = "\n## HISTORICAL ACCURACY (Your Track Record)\n"
            for horizon, data in sorted(self.calibration_context.items()):
                if isinstance(data, dict):
                    hit_rate = data.get("hit_rate")
                    sample_size = data.get("sample_size", 0)
                    if hit_rate is not None:
                        calibration_section += f"- {horizon} horizon: {hit_rate:.0%} accuracy ({sample_size} samples)\n"
            calibration_section += (
                "\nAdjust your confidence level to reflect this track record. "
                "If historical accuracy at this confidence band is low, lower your confidence accordingly.\n"
            )
```

3c. Update both `_synthesize_with_llm` and `_synthesize_with_openai` to call `self._build_prompt(...)` instead of inline prompt construction.

**Step 4: Update orchestrator to pass calibration context**

In `src/orchestrator.py`, in the `_run_solution_agent` method (~line 421), after creating the `SolutionAgent`, inject calibration context:

```python
    async def _run_solution_agent(self, ticker: str, agent_results: Dict[str, Any]) -> Dict[str, Any]:
        solution_agent = SolutionAgent(ticker, self.config, agent_results)

        # Inject calibration context if available
        try:
            confidence_raw = 0.5  # pre-synthesis default
            hit_rate_by_horizon = {}
            for horizon in (1, 7, 30):
                row = self.db_manager.get_reliability_hit_rate(horizon_days=horizon, confidence_raw=confidence_raw)
                if row:
                    hit_rate_by_horizon[f"{horizon}d"] = row
            if hit_rate_by_horizon:
                solution_agent.calibration_context = hit_rate_by_horizon
        except Exception as e:
            self.logger.debug(f"Could not load calibration context: {e}")

        timeout = self.config.get("AGENT_TIMEOUT", 30)
        # ... rest unchanged
```

**Step 5: Run tests to verify they pass**

Run: `python -m pytest tests/test_agents/test_solution_agent.py -v`
Expected: All pass

**Step 6: Run full test suite**

Run: `python -m pytest tests/ -v`
Expected: All pass

**Step 7: Commit**

```bash
git add src/agents/solution_agent.py src/orchestrator.py tests/test_agents/test_solution_agent.py
git commit -m "feat: feed calibration track record into solution agent prompt + DRY duplicated prompt"
```

---

### Task 7: Cross-Ticker Portfolio Risk Aggregation

**Files:**
- Modify: `src/portfolio_engine.py`
- Modify: `src/api.py`
- Modify: `frontend/src/utils/api.js`
- Test: `tests/test_portfolio_engine.py`

**Step 1: Write the failing tests**

Add to `tests/test_portfolio_engine.py`:

```python
def test_portfolio_risk_summary_basic():
    """portfolio_risk_summary computes weighted beta and sector concentration."""
    holdings = [
        {"ticker": "AAPL", "shares": 100, "market_value": 18000, "sector": "Technology", "beta": 1.2},
        {"ticker": "JPM", "shares": 50, "market_value": 10000, "sector": "Financials", "beta": 1.1},
        {"ticker": "MSFT", "shares": 30, "market_value": 12000, "sector": "Technology", "beta": 1.0},
    ]
    profile = {"max_position_pct": 0.10, "max_sector_pct": 0.30}

    result = PortfolioEngine.portfolio_risk_summary(holdings, profile)

    assert "portfolio_beta" in result
    assert "total_market_value" in result
    assert result["total_market_value"] == 40000
    assert "sector_concentration" in result
    assert "Technology" in result["sector_concentration"]
    tech_pct = result["sector_concentration"]["Technology"]
    assert abs(tech_pct - 0.75) < 0.01  # (18000+12000)/40000
    assert len(result["sector_breaches"]) > 0  # Technology > 30%


def test_portfolio_risk_summary_empty_holdings():
    """portfolio_risk_summary returns sensible defaults for empty portfolio."""
    result = PortfolioEngine.portfolio_risk_summary([], {})

    assert result["portfolio_beta"] == 0.0
    assert result["total_market_value"] == 0.0
    assert result["sector_concentration"] == {}
    assert result["position_breaches"] == []
    assert result["sector_breaches"] == []


def test_portfolio_risk_summary_position_breach():
    """Holdings exceeding max_position_pct are flagged."""
    holdings = [
        {"ticker": "AAPL", "shares": 100, "market_value": 18000, "sector": "Tech", "beta": 1.2},
        {"ticker": "JPM", "shares": 50, "market_value": 2000, "sector": "Fin", "beta": 1.1},
    ]
    profile = {"max_position_pct": 0.50}

    result = PortfolioEngine.portfolio_risk_summary(holdings, profile)

    assert any(b["ticker"] == "AAPL" for b in result["position_breaches"])
```

**Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_portfolio_engine.py::test_portfolio_risk_summary_basic tests/test_portfolio_engine.py::test_portfolio_risk_summary_empty_holdings tests/test_portfolio_engine.py::test_portfolio_risk_summary_position_breach -v`
Expected: FAIL — `portfolio_risk_summary` doesn't exist

**Step 3: Implement portfolio_risk_summary**

Add to `PortfolioEngine` class in `src/portfolio_engine.py`:

```python
@staticmethod
def portfolio_risk_summary(
    holdings: List[Dict[str, Any]],
    profile: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Compute portfolio-level risk metrics across all holdings.

    Args:
        holdings: List of holding dicts (ticker, shares, market_value, sector, beta)
        profile: Portfolio profile dict (max_position_pct, max_sector_pct)

    Returns:
        Dict with portfolio_beta, total_market_value, sector_concentration,
        position_breaches, sector_breaches, diversity_score
    """
    if not holdings:
        return {
            "portfolio_beta": 0.0,
            "total_market_value": 0.0,
            "sector_concentration": {},
            "position_breaches": [],
            "sector_breaches": [],
            "diversity_score": 0,
        }

    total_value = sum(float(h.get("market_value") or 0) for h in holdings)
    if total_value <= 0:
        total_value = 1.0  # Prevent division by zero

    max_position_pct = float(profile.get("max_position_pct") or 0.10)
    max_sector_pct = float(profile.get("max_sector_pct") or 0.30)

    # Weighted-average beta
    weighted_beta = 0.0
    for h in holdings:
        mv = float(h.get("market_value") or 0)
        beta = float(h.get("beta") or 1.0)
        weighted_beta += (mv / total_value) * beta

    # Sector concentration
    sector_values: Dict[str, float] = {}
    for h in holdings:
        sector = str(h.get("sector") or "Unknown")
        mv = float(h.get("market_value") or 0)
        sector_values[sector] = sector_values.get(sector, 0.0) + mv
    sector_concentration = {s: v / total_value for s, v in sector_values.items()}

    # Position breaches
    position_breaches = []
    for h in holdings:
        mv = float(h.get("market_value") or 0)
        pct = mv / total_value
        if pct > max_position_pct:
            position_breaches.append({
                "ticker": h.get("ticker"),
                "position_pct": round(pct, 4),
                "limit_pct": max_position_pct,
            })

    # Sector breaches
    sector_breaches = []
    for sector, pct in sector_concentration.items():
        if pct > max_sector_pct:
            sector_breaches.append({
                "sector": sector,
                "concentration_pct": round(pct, 4),
                "limit_pct": max_sector_pct,
            })

    # Simple diversity score: number of distinct sectors (0-100 scale)
    diversity_score = min(100, len(sector_values) * 15)

    return {
        "portfolio_beta": round(weighted_beta, 4),
        "total_market_value": round(total_value, 2),
        "sector_concentration": {s: round(v, 4) for s, v in sector_concentration.items()},
        "position_breaches": position_breaches,
        "sector_breaches": sector_breaches,
        "diversity_score": diversity_score,
    }
```

**Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_portfolio_engine.py -v`
Expected: All pass

**Step 5: Add API endpoint**

In `src/api.py`, add the endpoint (near the other portfolio endpoints, after ~line 960):

```python
@app.get("/api/portfolio/risk-summary")
async def get_portfolio_risk_summary():
    """Compute portfolio-level risk metrics across all holdings."""
    try:
        holdings = db_manager.list_portfolio_holdings()
        profile = db_manager.get_portfolio_profile()
        summary = PortfolioEngine.portfolio_risk_summary(holdings, profile)
        return summary
    except Exception as e:
        logger.error(f"Failed to compute portfolio risk summary: {e}")
        raise HTTPException(status_code=500, detail=str(e))
```

Add the import at the top of `src/api.py`:
```python
from .portfolio_engine import PortfolioEngine
```

**Step 6: Add API test**

Add to `tests/test_api.py`:

```python
class TestPortfolioRiskSummary:
    """Tests for GET /api/portfolio/risk-summary."""

    def test_risk_summary_empty_portfolio(self, client):
        """Returns sensible defaults for empty portfolio."""
        response = client.get("/api/portfolio/risk-summary")
        assert response.status_code == 200
        data = response.json()
        assert data["portfolio_beta"] == 0.0
        assert data["total_market_value"] == 0.0
```

**Step 7: Add frontend API function**

In `frontend/src/utils/api.js`, add after the other portfolio functions:

```javascript
export const getPortfolioRiskSummary = async () => {
  const response = await api.get('/api/portfolio/risk-summary');
  return response.data;
};
```

**Step 8: Run full test suite**

Run: `python -m pytest tests/ -v`
Expected: All pass

**Step 9: Commit**

```bash
git add src/portfolio_engine.py src/api.py tests/test_portfolio_engine.py tests/test_api.py frontend/src/utils/api.js
git commit -m "feat: add cross-ticker portfolio risk aggregation with API endpoint"
```

---

### Task 8: Remove Change Summary Truncation

**Files:**
- Modify: `src/orchestrator.py:1080-1086`
- Test: `tests/test_orchestrator.py`

**Step 1: Write the failing test**

Add to `tests/test_orchestrator.py`:

```python
def test_change_summary_not_truncated(test_config, tmp_db_path):
    """Change summary includes all detected changes, not capped at 6."""
    db = DatabaseManager(tmp_db_path)
    orch = Orchestrator(config=test_config, db_manager=db)

    # Build previous and current analyses with 8 material differences
    previous = {
        "id": 1,
        "timestamp": "2025-01-01T00:00:00",
        "recommendation": "HOLD",
        "score": 0,
        "confidence": 0.5,
        "signal_snapshot": {
            "recommendation": "HOLD",
            "score": 0,
            "confidence_raw": 0.5,
            "rsi": 50.0,
            "macd_signal": "neutral",
            "overall_sentiment": 0.0,
            "options_signal": "neutral",
            "options_put_call": 1.0,
            "macro_risk_environment": "low_risk",
        },
    }

    current_analysis = {
        "recommendation": "BUY",
        "score": 80,
        "confidence": 0.9,
        "signal_snapshot": {
            "recommendation": "BUY",
            "score": 80,
            "confidence_raw": 0.9,
            "rsi": 75.0,
            "macd_signal": "bullish",
            "overall_sentiment": 0.8,
            "options_signal": "bullish",
            "options_put_call": 0.5,
            "macro_risk_environment": "high_risk",
        },
    }

    result = orch._build_change_summary(previous, current_analysis)
    assert result["has_previous"] is True
    # Should not be truncated to 6
    assert result["change_count"] > 6 or result["change_count"] == len(result["material_changes"])
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_orchestrator.py::test_change_summary_not_truncated -v`
Expected: May fail or pass depending on detected changes — the key assertion is that `change_count == len(material_changes)` (no truncation)

**Step 3: Remove the truncation**

In `src/orchestrator.py`, find the change summary truncation block (~line 1080-1086) and replace:

```python
        # Old:
        # changes = changes[:6]
        # if changes:
        #     summary = "; ".join(change["label"] for change in changes[:3])
        #     if len(changes) > 3:
        #         summary += f"; and {len(changes) - 3} more change(s)"

        # New: include all changes in summary
        if changes:
            summary = "; ".join(change["label"] for change in changes)
        else:
            summary = "No material signal changes versus the previous run."
```

**Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_orchestrator.py::test_change_summary_not_truncated -v`
Expected: PASS

**Step 5: Run full test suite**

Run: `python -m pytest tests/ -v`
Expected: All pass

**Step 6: Commit**

```bash
git add src/orchestrator.py tests/test_orchestrator.py
git commit -m "feat: remove change summary truncation — surface all material changes"
```

---

### Task 9: Bulk Analysis Endpoint

**Files:**
- Modify: `src/api.py`
- Modify: `src/models.py`
- Test: `tests/test_api.py`

**Step 1: Add the Pydantic model**

In `src/models.py`, add:

```python
class BatchAnalysisRequest(BaseModel):
    """Request body for bulk analysis."""
    tickers: List[str]
    agents: Optional[str] = None
```

**Step 2: Write the API test**

Add to `tests/test_api.py`:

```python
class TestBatchAnalysis:
    """Tests for POST /api/analyze/batch."""

    def test_empty_tickers_returns_400(self, client):
        """Empty ticker list returns 400."""
        response = client.post("/api/analyze/batch", json={"tickers": []})
        assert response.status_code == 400

    def test_invalid_ticker_format_returns_400(self, client):
        """Invalid ticker format in list returns 400."""
        response = client.post("/api/analyze/batch", json={"tickers": ["123"]})
        assert response.status_code == 400

    def test_too_many_tickers_returns_400(self, client):
        """More than 20 tickers returns 400."""
        response = client.post(
            "/api/analyze/batch",
            json={"tickers": [f"T{i}" for i in range(21)]},
        )
        assert response.status_code == 400
```

**Step 3: Run tests to verify they fail**

Run: `python -m pytest tests/test_api.py::TestBatchAnalysis -v`
Expected: FAIL — endpoint doesn't exist (404)

**Step 4: Implement the endpoint**

In `src/api.py`, add the import for the model and the endpoint. Place it BEFORE the `POST /api/analyze/{ticker}` route so FastAPI doesn't match "batch" as a ticker:

```python
from .models import (
    # ... existing imports ...,
    BatchAnalysisRequest,
)

@app.post("/api/analyze/batch")
async def batch_analyze_tickers(body: BatchAnalysisRequest):
    """
    Batch-analyze a list of tickers via SSE stream.

    Accepts a JSON body with tickers list and optional agents string.
    Returns SSE events: 'result' per ticker, 'error' on failure, 'done' at end.
    """
    tickers = [t.upper() for t in body.tickers]

    if not tickers:
        raise HTTPException(status_code=400, detail="No tickers provided")
    if len(tickers) > 20:
        raise HTTPException(status_code=400, detail="Maximum 20 tickers per batch")

    # Validate ticker formats
    for t in tickers:
        if not re.match(r"^[A-Z]{1,5}$", t):
            raise HTTPException(status_code=400, detail=f"Invalid ticker format: {t}")

    # Parse agents
    requested_agents = None
    if body.agents:
        valid_agents = {"news", "sentiment", "fundamentals", "market", "technical", "macro", "options"}
        requested_agents = [a.strip().lower() for a in body.agents.split(",") if a.strip()]
        invalid = set(requested_agents) - valid_agents
        if invalid:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid agent names: {', '.join(sorted(invalid))}",
            )

    async def batch_generator():
        concurrency = 4
        semaphore = asyncio.Semaphore(concurrency)

        async def _analyze_one(ticker: str) -> Dict[str, Any]:
            async with semaphore:
                orchestrator = Orchestrator(
                    db_manager=db_manager,
                    rate_limiter=av_rate_limiter,
                    av_cache=av_cache,
                )
                result = await orchestrator.analyze_ticker(ticker, requested_agents=requested_agents)
                return {
                    "ticker": ticker,
                    "success": result.get("success", False),
                    "analysis_id": result.get("analysis_id"),
                    "recommendation": (result.get("analysis") or {}).get("recommendation"),
                    "score": (result.get("analysis") or {}).get("score"),
                    "confidence": (result.get("analysis") or {}).get("confidence"),
                    "ev_score_7d": (result.get("analysis") or {}).get("ev_score_7d"),
                    "duration_seconds": result.get("duration_seconds", 0),
                    "error": result.get("error"),
                }

        tasks = [asyncio.create_task(_analyze_one(t)) for t in tickers]
        completed = 0
        for task in asyncio.as_completed(tasks):
            completed += 1
            try:
                payload = await task
            except Exception as e:
                logger.error("Batch analysis task failed: %s", e)
                payload = {"success": False, "error": str(e), "ticker": "UNKNOWN"}

            event_type = "result" if payload.get("success") else "error"
            yield f"event: {event_type}\ndata: {json.dumps(payload, default=str)}\n\n"

        yield f"event: done\ndata: {json.dumps({'message': 'Batch complete', 'ticker_count': len(tickers), 'completed': completed}, default=str)}\n\n"

    return StreamingResponse(
        batch_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )
```

**Step 5: Run tests to verify they pass**

Run: `python -m pytest tests/test_api.py::TestBatchAnalysis -v`
Expected: PASS

**Step 6: Add frontend API function**

In `frontend/src/utils/api.js`, add:

```javascript
/**
 * Get SSE URL for batch analysis of arbitrary tickers
 */
export const getBatchAnalyzeURL = () => `${API_BASE_URL}/api/analyze/batch`;
```

**Step 7: Run full test suite**

Run: `python -m pytest tests/ -v`
Expected: All pass

**Step 8: Commit**

```bash
git add src/api.py src/models.py tests/test_api.py frontend/src/utils/api.js
git commit -m "feat: add POST /api/analyze/batch endpoint for arbitrary ticker batch analysis"
```

---

### Task 10: Frontend — CalibrationCard + Diagnostics Cleanup

**Files:**
- Create: `frontend/src/components/CalibrationCard.jsx`
- Modify: `frontend/src/components/Dashboard.jsx:263-264` (remove duplicate AgentPipelineBar)
- Modify: `frontend/src/components/Dashboard.jsx:292-296` (add CalibrationCard to right sidebar)

**Step 1: Remove duplicate AgentPipelineBar from Diagnostics tab**

In `frontend/src/components/Dashboard.jsx`, find the Diagnostics tab content (~line 254-266) and remove the `<AgentPipelineBar />` line:

```jsx
{/* Diagnostics Tab */}
{activeTab === 'diagnostics' && (
  <Motion.div
    key="tab-diagnostics"
    initial={{ opacity: 0, y: 8 }}
    animate={{ opacity: 1, y: 0 }}
    exit={{ opacity: 0, y: -8 }}
    transition={{ duration: 0.2 }}
    className="space-y-6"
  >
    <DiagnosticsPanel analysis={analysis} />
  </Motion.div>
)}
```

**Step 2: Create CalibrationCard.jsx**

Use the `/frontend-design` skill to create this component. It should:
- Fetch data from `getCalibrationSummary()` and `getCalibrationReliability()`
- Display overall accuracy, sample count
- Show per-horizon (1d, 7d, 30d) accuracy bars
- Use glassmorphic card styling (`glass-card` class)
- Graceful empty state when no calibration data exists
- Match the MacroSnapshot card style and sizing

**Step 3: Add CalibrationCard to the right sidebar**

In `frontend/src/components/Dashboard.jsx`, in the right sidebar block (~line 287-296):

```jsx
<Motion.div
  initial={{ opacity: 0, x: 12 }}
  animate={{ opacity: 1, x: 0 }}
  transition={{ duration: 0.4, ease: 'easeOut' }}
  className="hidden lg:block w-[340px] shrink-0 border-l border-white/5 p-5 space-y-5 overflow-y-auto"
>
  <Recommendation analysis={analysis} />
  <CalibrationCard />
  <MacroSnapshot analysis={analysis} />
</Motion.div>
```

Add the import at the top of Dashboard.jsx:
```jsx
import CalibrationCard from './CalibrationCard';
```

**Step 4: Verify frontend builds**

Run: `cd frontend && npm run build`
Expected: Build succeeds with no errors

**Step 5: Commit**

```bash
git add frontend/src/components/CalibrationCard.jsx frontend/src/components/Dashboard.jsx
git commit -m "feat: add CalibrationCard to right sidebar, remove duplicate pipeline bar from diagnostics"
```

---

### Task 11: Final Verification

**Step 1: Run full backend test suite**

Run: `python -m pytest tests/ -v`
Expected: All tests pass

**Step 2: Verify frontend build**

Run: `cd frontend && npm run build`
Expected: Clean build

**Step 3: Verify no regressions**

Run: `python -m pytest tests/ --tb=short`
Expected: All pass, zero failures

**Step 4: Final commit (if any fixups needed)**

Only if prior tasks left loose ends.
