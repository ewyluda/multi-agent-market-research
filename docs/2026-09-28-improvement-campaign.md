# Portfolio-Readiness Improvement Campaign — 2026-09-28

> **How to use this doc:** open a fresh session and say
> *"Read docs/2026-09-28-improvement-campaign.md and begin the next session."*
> The executing session picks the first `pending` session whose dependencies are `done`,
> follows the ground rules below, and updates this doc (status + session log) before finishing.
> This doc is the cross-session source of truth — treat it as append-truth.

**Goal:** turn this repo into a public portfolio showpiece for:

1. Applied AI / internal-tools engineer in a data-center or infrastructure org (build-out, capacity-planning, project-controls teams at neoclouds / hyperscalers) — *judged on shipped work*.
2. Forward-deployed / solutions engineer at an AI lab or AI-infra company — *customer-facing builder*.
3. TPM for data-center delivery — *only roles that include building tools and automation*.

**Positioning thesis:** the stock-research domain is the vehicle; the portable skills on display are
*orchestrating LLM agents over unreliable external data, deterministic validation of LLM output,
cost/latency observability, outcome-based evals, scheduled automation, and an agent/MCP interface*.
Every session below should make one of those more visible or more credible.

---

## Status board

| ID | Session | Depends on | Status |
|----|---------|-----------|--------|
| A0 | Repo triage, skills extraction, branch cleanup, schedule off | — | in progress (awaiting owner: merge PR #8, reset local main) |
| A1 | Frontend visual + data-binding bugs | A0 | pending |
| A2 | Restore synthesis agents (timeout budget, failure visibility) | A0 | pending |
| A3 | Error surfacing + backend startup time | A1 | pending |
| A4 | Verdict hero (render the Solution agent's output) | A1 | pending |
| B1 | CI, lint, dependency lock, leaky-test fixes | A1, A2 | pending |
| B2 | Security + deploy hardening | B1 | pending |
| B3 | Backend trim (dead code, flags, config sync, async DB access) | B1 | pending |
| B4 | Split `api.py` into routers | B3 | pending |
| B5 | Test-coverage gaps (backend agents + frontend unit tests) | B1 | pending |
| C1 | Unified async LLM client + model registry (first 3 agents) | B1 | pending |
| C2 | Migrate remaining LLM call sites; delete duplicates | C1 | pending |
| C3 | LLM observability: tokens, cost, latency, run traces | C2 | pending |
| C4 | Versioned prompts + offline eval harness | C3 | pending |
| D1 | Live agent-run visualization | A2, C3 | pending |
| D2 | Landing panel, responsive layout, accessibility | A3, A4 | pending |
| D3 | Design-system consolidation, bundle split, component cleanup | D2 | pending |
| D4 | Static demo mode + Vercel deploy | D1, D2, C4 | pending |
| D5 | README rewrite, ADRs, docs refresh | D4 | pending |
| D6 | Media, GitHub metadata, publish, resume bullets | D5 | pending |

Status values: `pending` / `in progress` / `done` / `blocked (<reason>)`.

---

## Resolved questions (do not re-ask)

| # | Question | Decision (2026-09-28) | Notes for executing sessions |
|---|----------|----------------------|------------------------------|
| 1 | Demo strategy | **Static demo mode** — recorded analyses + replayed SSE served as static JSON, deployed free (Vercel), shareable deep links, plus a 60–90s video. No hosted live backend. | Session D4. |
| 2 | `skills/` due-diligence framework (65 files, all 17 unpushed commits) | **Move to its own repo** and present it as the **"agent playbook layer"** that drives this platform through its MCP server. | Suggested repo name `equity-dd-agent-playbook` (public). Preserve history with `git subtree split`. Link both READMEs to each other. Session A0. |
| 3 | `docs/superpowers/` + `docs/plans/` internal AI-generated plans | **Remove from the public tree**; replace with 4–5 short ADRs. | Keep a local, unpushed archive tag. Session D5. |
| 4 | Scope cuts | **Yes**: delete `rollout_canary.py`, backfill CLI, always-true `*_ENABLED` flags; make council personas data-driven from `profiles.py`. | Sessions B3, C2. |
| 5 | Default LLM + model versions | **Default provider Anthropic**, single model registry constant. Update every model reference to current versions: **Claude Opus 5.5, Sonnet 5.5, Haiku 4.5; OpenAI GPT-6 Astra / Sol / Luna**; keep xAI supported. | Anthropic IDs confirmed: `claude-opus-5-5`, `claude-sonnet-5-5`, `claude-haiku-4-5-20251001`. **GPT-6 exact API IDs and tier ordering are owner-supplied but unverified — confirm against OpenAI's model list/docs before hardcoding.** Verify the current xAI ID too (local `.env` uses `grok-4.20-0309-reasoning`). Sessions A0 (quick default fix), C1 (registry). |
| 6 | Hourly AAPL schedule (64 runs so far) | **Disable it**; `SCHEDULER_ENABLED` defaults to `false` for cloners. | Session A0. |
| 7 | Claude co-author trailers on ~205/241 commits | **Keep them** and add a **"How I built this with AI agents"** README section. | Session D5. Outline below. |
| 8 | Merged branches (7 local, 7 remote, all 0 commits ahead of `main`) | **Delete all** per audit recommendation — owner authorized remote deletion. | Session A0. Re-verify "0 ahead" immediately before deleting each. |
| 9 | Infrastructure framing | **Apply it**: README section mapping the patterns to infra tooling; demo tickers drawn from the AI-infrastructure supply chain. | Sessions D4, D5. Talking points in Appendix C. |

---

## Ground rules for executing sessions

1. **Start:** read this doc → pick the first eligible `pending` session → set it `in progress` →
   create branch `campaign/<id>-<slug>` from up-to-date `main`.
2. **Stay in scope.** Anything found out-of-scope goes in *Discovered during execution* (bottom), not fixed inline.
3. **Verify for real.** Run the session's verification step; record the evidence (command result, screenshot, PR link) in the session log.
4. **Confirm before cost or outward-facing actions** unless a resolved question above already authorized it:
   live analyses (LLM + FMP spend), deploys, pushes, PR creation, creating repos. Q2 (create playbook repo) and
   Q8 (delete merged branches) are already authorized.
5. **Never re-enable** the AAPL schedule or make `SCHEDULER_ENABLED` default to true.
6. **Keep docs in sync.** If a session changes architecture, update `CLAUDE.md` in the same PR (README is rewritten wholesale in D5; until then, fix only outright false claims).
7. **Finish:** tests green → PR to `main` (one PR per session; the PR history itself is portfolio evidence) →
   mark `done` → append a dated line to the session log with PR link and any follow-ups.
8. **Dev servers:** use `.claude/launch.json` (`backend` now runs `venv/bin/python run.py`; `frontend` runs `npm run dev`). Stop the backend when finished — until A0 lands the scheduler can fire paid analyses.

---

## Phase A — Triage and visible breakage

### A0 · Repo triage, skills extraction, branch cleanup, schedule off
**Status:** in progress — all agent-side work done 2026-09-28; two owner actions remain (auto-mode blocked both): (1) merge [PR #8](https://github.com/ewyluda/multi-agent-market-research/pull/8); (2) reset local `main` to `origin/main` (drops the 17 skills commits, now preserved in the playbook repo and on local `backup/pre-campaign-main`). Mark `done` after both.
**Goal:** a clean, honest repo state that is safe to push, with nothing running up API bills.

**Scope and steps**
1. **Safety net first:** `git stash` the 17-line uncommitted `CLAUDE.MD` diff (Agent API / MCP docs), then create `backup/pre-campaign-main` at current `main` (local only).
2. **Extract the playbook (Q2):** the 17 unpushed commits (`9ae6a0c`…`11aef9d`) touch only `skills/`, `scripts/validate-skills.sh`,
   and two `docs/superpowers/*/2026-04-09-due-diligence-*` files (verified 2026-09-28).
   - `git subtree split --prefix=skills -b playbook-export` → create GitHub repo `equity-dd-agent-playbook` → push `playbook-export` as its `main`. Add `validate-skills.sh` and a README that explains it drives this platform via the 42-tool MCP server (`skills/due-diligence/platform-mapping.md` is the bridge).
   - Reset local `main` to `origin/main` (commits are unpushed, so no public history rewrite). Confirm `git rev-list --count origin/main..main` = 0.
3. **Re-apply** the stashed `CLAUDE.MD` diff, then `git mv CLAUDE.MD CLAUDE.md` (fixes the case mismatch with `.dockerignore` on Linux).
4. **Junk removal:** `git rm --cached .DS_Store` and add it to `.gitignore`; delete untracked `=1.0.0`, `=4.7.0` (pip output from an unquoted `>=`), `scripts/debug-validate.sh`, empty `.worktrees/`, empty `frontend/frontend/`; move tracked root `test_api.py` → `scripts/smoke_analysis.py`.
5. **LICENSE:** add MIT `LICENSE` (README already claims MIT, but no file exists).
6. **Schedule off (Q6):** `UPDATE schedules SET enabled=0 WHERE id=1;` in local `market_research.db`; change the default in `src/config.py:41` (`SCHEDULER_ENABLED`) and `CATALYST_SCHEDULER_ENABLED` (`:43`) to `false`; update `.env.example`.
7. **Quick model fix (Q5, interim):** replace the retired default `claude-3-5-sonnet-20241022` in `src/config.py:29` and `.env.example:14` with `claude-sonnet-5-5`; default `LLM_PROVIDER=anthropic`. (Per-agent hardcoded fallbacks are deleted in C2.)
8. **Branch cleanup (Q8):** for each of `feat/caprelay-replication`, `feat/frontend-overhaul`, `feat/frontend-redesign`, `feat/mcp-agent-api`, `fix/orchestrator-resilience-performance`, `worktree-feat+perception-ledger` (local) and `origin/{feat/analysis-page-redesign, feat/caprelay-replication, feat/frontend-overhaul, feat/mcp-agent-api, feat/news-agent-rss-quality-filter, fix/orchestrator-resilience-performance, perf/pipeline-optimization}`: re-check `git rev-list --count main..<b>` = 0, then `git branch -d` / `git push origin --delete`. Enable "Automatically delete head branches" in the GitHub repo settings (`gh repo edit --delete-branch-on-merge`).
9. **GitHub description typo:** `gh repo edit --description "Multi-agent LLM research platform: parallel data agents, synthesis agents, deterministic guardrails, MCP server"` (the final copy is set in D6).

**Files:** `.gitignore`, `CLAUDE.md`, `LICENSE`, `src/config.py`, `.env.example`, `scripts/`, local DB.
**Verification:** `git status` clean except intended changes; `git branch -a` shows only `main` (+ backup and campaign branches); the playbook repo is visible on GitHub with 17-commit history; `sqlite3 market_research.db "select enabled from schedules"` → `0`; the backend starts and logs no scheduled jobs; `pytest -m "not slow" -q` still 697 passing.
**Done when:** all of the above hold and the A0 PR is merged and pushed.

### A1 · Frontend visual and data-binding bugs
**Status:** pending
**Goal:** what's already built renders correctly and navigation works.

**Scope and steps**
1. **CSS reset (F1):** delete the unlayered `* { margin:0; padding:0 }` at `frontend/src/index.css:102-106` (Tailwind preflight already does this); check the second `*` rule at `:143` the same way. This currently zeroes *every* Tailwind spacing utility.
2. **One response-shape adapter (F4):** add `normalizeAnalysis()` (e.g. `frontend/src/utils/normalizeAnalysis.js`) applied in `useAnalysis`, so the flat DB shape (`GET /api/analysis/{t}/latest`) and the nested SSE result (`src/api.py` stream result ~L1510-1517) produce one shape. Then fix `frontend/src/components/analysis/KpiRow.jsx`:
   - confidence is 0–1 → display `×100` (currently `Math.round(0.45)` → "0%");
   - sentiment reads `overall_score`/`composite_score`, but the payload has `overall_sentiment_score` (top level) and `overall_sentiment` (`src/agents/sentiment_agent.py:121`);
   - `change_1d` doesn't exist in market output — map the real key or drop the chip.
3. **Sentiment factors:** `SentimentTab.jsx:7,25` treats `factors` as an array; the agent returns a dict → render `Object.entries`.
4. **History empty (F5):** `useHistory.fetchTickers` is only called after a delete (`hooks/useHistory.js:103`) → call it on mount in `HistoryView`. Wire up the built-but-unused filter/pagination state (`HistoryView.jsx:27-38`) or delete it.
5. **Dead ticker clicks (F5):** History/Watchlist/Portfolio expect `onSelectAnalysis`/`onSelectTicker` props that `App.jsx:24-27` never passes, and nobody calls `useOutletContext()` (`AppLayout.jsx:85`). Use `useNavigate()` → `/analysis/:ticker` directly in each view and remove the dead prop plumbing.
6. **Deep links:** `AnalysisView.jsx:16-20` fetches only when `!analysis` → refetch when the route ticker ≠ the loaded ticker; put the active tab in `?tab=`.
7. **Dead header controls:** Bell → `/alerts` (with count badge); Settings → remove (or a real settings popover if trivial). Add `aria-label`s.
8. **Raw float in summary text:** "P/E ratio: 31.516256537609213" on the Overview comes from backend summary generation — `grep -rn "P/E ratio:" src/` and format to 1 decimal at the source.

**Verification (preview, analysis id 221 / AAPL):** `getComputedStyle` of a nav link shows non-zero padding; the KPI row shows Confidence **45%** and Sentiment **−0.10**; the sentiment factor breakdown renders; History lists tickers; clicking a ticker in History/Watchlist opens it; loading `/analysis/NVDA` while AAPL is loaded shows NVDA; `?tab=technicals` survives reload; `npm run build` passes. Screenshot before/after in the PR.
**Done when:** every item above verified in the browser preview.

### A2 · Restore synthesis agents (timeout budget + failure visibility)
**Status:** pending
**Goal:** Thesis, Narrative and Tags actually appear again, and when a synthesis agent fails the UI says so.

**Evidence:** 0 of the last 40 analyses contain `thesis` or `narrative` (the last one with a thesis was on 2026-04-04). `src/orchestrator.py:301` wraps every synthesis agent in `ENRICHMENT_AGENT_TIMEOUT` = **15s**, *outside* each agent's own 30s `AGENT_TIMEOUT` (`orchestrator.py:910`), so the effective cap is 15s for two-pass LLM agents. `TimeoutError` has an empty message, so the log reads `Enrichment 'thesis' failed (non-blocking): ` with nothing after it. This was introduced in `9a18b3c` (2026-04-03, orchestrator resilience).

**Scope and steps**
1. Replace the nested timeouts with **one per-agent budget** from config (e.g. `SYNTHESIS_TIMEOUTS = {thesis: 90, narrative: 90, solution: 60, earnings_review: 45, risk_diff: 45, tag_extractor: 30}`), applied in exactly one place.
2. Log failures with `type(e).__name__`, elapsed time and the agent name.
3. Persist a `synthesis_status` map in the analysis payload (`{"thesis": {"status": "timeout", "elapsed_s": 15.0}, ...}`) and show it in the Diagnostics tab and MetaFooter ("Thesis: timed out after 90s").
4. `tag_result` is gathered (`orchestrator.py:310`) but never attached to `final_analysis` — check the tag persistence path and attach or persist it.
5. **Contradiction bug:** EarningsReview's executive summary says "No earnings transcript available for detailed review of AAPL" while the Overview shows the Q1 2026 call. Trace the input key path in `earnings_review_agent.py` against the earnings agent's output.
6. Known limitation, documented here (fixed properly in C1): the sync LLM SDK calls run in threads, so `wait_for` cancellation doesn't stop them; they keep running and billing.

**Verification:** a unit test with a fake synthesis agent that sleeps past its budget asserts the run completes and `synthesis_status` records the timeout; then **one live analysis** (confirm spend with the owner; suggested ticker NVDA) has non-null `thesis`, `narrative` and tags in the DB (`json_extract(analysis_payload,'$.thesis') is not null`).
**Done when:** the live run shows all synthesis outputs, or any failure is visible with a reason.

### A3 · Error surfacing + backend startup time
**Status:** pending
**Goal:** the app never looks "idle" when it is actually broken, and the backend is up in seconds.

**Scope and steps**
1. **Startup:** on 2026-09-28 it took ~68s from `Starting…` to the scheduler registering, and API calls timed out meanwhile. Profile it (`python -X importtime run.py 2>imports.log`, plus timestamps around OpenBB init, DB migrations and the scheduler) and make heavy init lazy or backgrounded. Target: `/health` returns 200 within 10s of launch.
2. **`/health`** timed out at 5s even after startup → make it cheap (no external calls); add `/health/deep` for provider checks. Report which LLM/data keys are configured (booleans only).
3. **Frontend:**
   - an error banner with a retry button in `AnalysisView` (today `useAnalysis.error` is set but never rendered; SSE failure drops back to "Enter a ticker");
   - a backend status pill in the header driven by `/health` (online / no LLM key / offline);
   - stop swallowing errors in the alert poll (`AppLayout.jsx:19-27`);
   - remove the `console.log`s in `useAnalysis.js:33,41,52`.

**Verification:** with the backend stopped, the UI shows an offline state; after starting it, the UI recovers without a reload; time-to-healthy measured and logged in the PR.
**Done when:** both verified, and startup is ≤10s or the remaining cost is documented with its cause.

### A4 · Verdict hero — render the Solution agent's output
**Status:** pending
**Goal:** the platform's headline answer is actually visible. Since `2949a39` deleted Summary/Recommendation/ScenarioPanel, **no UI reads** `reasoning`, `risks`, `opportunities`, `price_targets` or `scenarios` (`src/agents/solution_agent.py:357-368`).

**Scope:** a new `frontend/src/components/analysis/VerdictHero.jsx` above the tabs, containing:
- rating plus calibrated confidence (`confidence_calibrated`);
- `rationale_summary` (3 sentences);
- entry / target / stop from `price_targets`;
- bull / base / bear scenario bars;
- top 3 risks and top 3 opportunities;
- **guardrail warnings** and a **"recommendation overridden by rule engine"** badge from `validation` / `validation_rules.py`. This is the applied-AI judgement signal, so make it visible, not hidden.

**Verification:** renders correctly for AAPL id 221 and one fresh analysis; handles a missing section gracefully.
**Done when:** verified in preview; screenshot in the PR.

---

## Phase B — Engineering baseline

### B1 · CI, lint, dependency lock, leaky-test fixes
**Status:** pending
**Scope and steps**
1. `.github/workflows/ci.yml`:
   - Python job: `ruff check`, `ruff format --check`, `pytest -m "not slow"` with **no API keys in the environment**.
   - Frontend job: `npm ci`, `npm run lint`, `npm run build`.
   - Add a README badge.
2. Add `[tool.ruff]` to `pyproject.toml` and fix or ignore findings deliberately. Set `asyncio_default_fixture_loop_scope = "function"`. Add `pytest-timeout` (for example 60s by default).
3. Frontend lint currently fails (27 problems).
   - Add `eslint-plugin-react` with `jsx-uses-vars`; about 7 of the errors are `motion`/`Component` false positives.
   - Fix the real ones: `react-hooks/refs` at `PriceChart.jsx:159`; set-state-in-effect at `AppLayout.jsx:33` and in `Inflection{Chart,Feed,Heatmap}`; unused `thesisHealth`/`majorityConfig` at `CouncilPanel.jsx:500,513`; react-refresh in `ui/badge.jsx` and `ui/button.jsx`.
4. **Dependencies:** split `requirements.txt` (runtime) from `requirements-dev.txt` (pytest, pytest-cov, aioresponses, ruff); lock with `uv pip compile` (or pip-tools) and commit the lockfile(s). Move `@tailwindcss/postcss` to devDependencies and drop the redundant `autoprefixer`.
5. **Leaky tests:**
   - `tests/test_orchestrator.py::test_full_flow_with_mocked_agents` (13.8s) patches only 8 agents, so Leadership, Earnings, Thesis, EarningsReview, Narrative, TagExtractor and RiskDiff can reach real APIs. Patch every `AGENT_REGISTRY` entry.
   - `test_base_agent::test_retry_respects_max_retries` spends 9s in real backoff; monkeypatch `asyncio.sleep`.

**Verification:** CI is green on the PR; `env -u ANTHROPIC_API_KEY -u FMP_API_KEY … pytest -m "not slow"` passes locally; the fast suite is well under 100s.
**Done when:** CI is green and required on `main` (branch protection: require status checks).

### B2 · Security and deploy hardening
**Status:** pending
**Scope and steps**
1. Optional auth: if `API_AUTH_TOKEN` is set, require it (bearer header) on all mutating, analysis, batch and council routes. The MCP server forwards it via `MARKET_RESEARCH_API_KEY`.
2. Rate limit analyze, batch and council (slowapi).
3. Default `HOST` to `127.0.0.1` (`src/config.py:166`).
4. CORS origins from env; no `allow_credentials=True` combined with wildcard methods and headers (`src/api.py:99-103`).
5. Replace the 42 `detail=str(e)` sites with a global exception handler that logs and returns a generic 500 carrying an error id.
6. Dockerfile:
   - multi-stage build, so `gcc` is not in the final image;
   - non-root `USER`;
   - `COPY mcp_server/`;
   - a healthcheck.
   Document `docker compose up` for production.
7. SSRF hardening for the SEC section fetch (`src/routers/agent_api.py:835-866`, `src/data_provider.py:1331-1336`): https only, `allow_redirects=False`, a response-size cap.
8. Delete the rotating user-agent list and its "anti-detection" comment (`src/config.py:246-247`).
9. Ticker validation: allow share classes like `BRK.B` (`src/api.py:349`), and add `earnings` to `valid_agents` (`src/api.py:354`).
10. MCP: add `destructiveHint` annotations to `delete_watchlist`, `delete_alert` and `remove_holding` (`mcp_server/tools/actions.py:59,114,148`).

**Verification:**
- tests for auth on and off, 429 on the rate limit, and a generic 500 body;
- `docker compose up --build` gives a healthy backend running as non-root (`docker exec … id -u` ≠ 0).

**Done when:** all of the above verified, and CI is green.

### B3 · Backend trim, config sync, async DB access
**Status:** pending
**Scope and steps**
1. **Delete** `src/rollout_canary.py` (1,016 LOC, nothing imports it), `src/backfill_signal_contract.py`, and the `/api/rollout/phase7/status` endpoint if nothing uses it (grep the frontend and MCP first).
2. **Flags:** `src/config.py` reads 91 env vars, including 30 `*_ENABLED` flags that all default to true. Keep only real toggles: the per-agent enables, the scheduler flags, and `COT_PERSISTENCE_ENABLED`. Remove the rest together with the dead branches they guard.
3. Remove the Alpha Vantage / `NEWS_API_KEY` remnants (`src/config.py:14-17,107,204-207`).
4. Sync `.env.example` with every env var actually read. At least 11 are missing, for example `EARNINGS_AGENT_ENABLED`, `EARNINGS_TRANSCRIPT_QUARTERS`, `RSS_ENABLED`, `RSS_CACHE_TTL`, `NEWS_QUALITY_FILTER_ENABLED`, `THESIS_HEALTH_ENABLED` and `MARKET_RESEARCH_URL`. Add a test that fails when they drift.
5. **Async DB:** 72 synchronous `db_manager.*` calls run inside 59 `async def` handlers in `api.py`. Wrap them via `asyncio.to_thread` behind a thin async facade (or adopt `aiosqlite`). Run the PRAGMAs once at connection creation, not on every call (`src/database.py:25-34`).
6. Narrow the bare `except Exception: pass` sites (`database.py:3287,3356,3394`, `agent_api.py:377`, `leadership_agent.py:101`) and log with `exc_info`.

**Verification:** tests green; `grep -c "_ENABLED" src/config.py` reduced; the env-drift test passes; the backend runs one cached-analysis flow in the preview.
**Done when:** as above, and the diff is net-negative LOC.

### B4 · Split `api.py` into routers
**Status:** pending
**Scope:** move the 58 routes in `src/api.py` (1,919 LOC) into `src/routers/{analysis,watchlists,schedules,alerts,portfolio,council,system}.py`, following the pattern in `src/routers/inflection.py`. Share validation between `api.py` (L345-355) and `agent_api.py:44` through one dependency.
- Stretch: split `DatabaseManager` (95 methods, 3,481 LOC) along the same domains into `src/repositories/`, following `perception_repo.py`.
- Stretch: replace the 616-line `initialize_database` with numbered migrations (`PRAGMA user_version`).

**Verification:** the route list before and after is identical (compare `app.routes` dumps); tests green.
**Done when:** `api.py` holds only app wiring (target < 250 LOC).

### B5 · Test-coverage gaps
**Status:** pending
**Scope:**
- **Backend:** fixture-based tests for `src/data_provider.py` (1,408 LOC, currently untested) and the `market`, `macro`, `technical` and `sentiment` agents (currently not referenced by any test). Add fundamentals agent coverage for the FMP → yfinance fallback path.
- **Frontend:** add Vitest, with tests for `normalizeAnalysis` (both shapes), `KpiRow` formatting and `VerdictHero` with missing sections.
- Add the frontend tests to CI.

**Verification:** `pytest --cov=src` shows each named module covered; `npm test` runs in CI.
**Done when:** CI runs both suites and is green.

---

## Phase C — LLM platform (the applied-AI core)

### C1 · Unified async LLM client + model registry
**Status:** pending
**Problem (F9):** LLM client and provider-switch code is copy-pasted 14 times. Examples: `thesis_agent.py:365-411`, `earnings_agent.py:223-249`, `narrative_agent.py:320-344`, `council/base_council_agent.py:238-266`; find the rest with `grep -rn "messages.create\|chat.completions.create" src`. There are also 8 copies of fence-stripping `_parse_llm_response`. None of it uses structured output or schema validation. Sync clients run in threads, a new client is created per call, and there is no SDK timeout.

**Scope and steps**
1. `src/llm/models.py` holds **the only place model IDs live** (Q5). Provider × tier registry:

   | Tier | Anthropic | OpenAI (verify IDs!) | Use for |
   |------|-----------|----------------------|---------|
   | `deep` | `claude-opus-5-5` | GPT-6 Astra (?) | thesis, solution |
   | `standard` (default) | `claude-sonnet-5-5` | GPT-6 Sol (?) | narrative, earnings review, risk diff, leadership, fundamentals LLM, council |
   | `fast` | `claude-haiku-4-5-20251001` | GPT-6 Luna (?) | tag extractor, sentiment, news relevance |

   - The GPT-6 tier mapping is an **assumption** to confirm against OpenAI docs.
   - xAI stays available through its OpenAI-compatible endpoint; verify its current model ID.
   - Tier routing per agent is configurable through env (`LLM_TIER_<AGENT>=…`).
   - Load the `claude-api` skill before writing any Anthropic code.
2. `src/llm/client.py`:
   - async clients (`AsyncAnthropic`, `AsyncOpenAI`) reused per process;
   - a per-call SDK timeout, so cancellation really stops the request;
   - retries with backoff on 429 and 5xx;
   - `complete_structured(schema: type[BaseModel], …)` using forced tool-use (Anthropic) or JSON-schema response format (OpenAI), Pydantic validation, and one repair retry;
   - returns `LLMResult(parsed, text, usage, latency_ms, provider, model, tier)`.
3. Migrate **thesis**, **solution** and **sentiment** first, and define a Pydantic output schema for each.

**Verification:** unit tests with a fake transport (success, malformed JSON with repair, timeout, 429 retry); one live run with thesis, solution and sentiment going through the new client (confirm spend).
**Done when:** the 3 agents are migrated, their old code is deleted, and tests are green.

### C2 · Migrate the remaining LLM call sites
**Status:** pending
**Scope and steps**
1. Move every remaining agent (earnings, fundamentals LLM, earnings_review, narrative, tag_extractor, risk_diff, leadership, council base, council validator, council synthesis, and any others the grep finds) onto `src/llm`, each with a Pydantic output schema.
2. Delete all 8 `_parse_llm_response` copies and the per-agent hardcoded model fallbacks (`thesis_agent.py:384`, `sentiment_agent.py:139`, `solution_agent.py:429`, `tag_extractor_agent.py:223`).
3. Make the council personas data-driven from `src/agents/council/profiles.py` (Q4): one generic persona agent replaces the 26 seven-line stub modules and the `importlib` loading (`src/api.py:1876`).

**Verification:** `grep -rn "messages.create\|chat.completions.create\|claude-3" src` finds matches only inside `src/llm/`; tests green; one live analysis plus one council run succeed (confirm spend).
**Done when:** as above.

### C3 · LLM observability: tokens, cost, latency, run traces
**Status:** pending
**Why it matters for the target roles:** infrastructure and capacity teams live in dashboards and unit economics. "This run cost $0.41 and took 38s, and here is the per-agent breakdown" is the single most transferable signal in the repo. Today there is **zero** usage capture.

**Scope and steps**
1. A `run_id` (contextvar) created per analysis and propagated to every LLM call and agent.
2. A new `llm_calls` table with:
   - identifiers: `id`, `analysis_id`, `run_id`, `agent`;
   - model: `provider`, `model`, `tier`, `prompt_version`;
   - usage: `input_tokens`, `output_tokens`, `cache_read_tokens`, `cost_usd`, `latency_ms`;
   - outcome: `status`, `error_type`, `created_at`.

   Recorded by `src/llm/client.py` automatically.
3. A pricing table in `src/llm/models.py`, **sourced from provider docs with an as-of date**. Never guess prices; use the `claude-api` skill for Anthropic pricing.
4. `run_metrics` in the analysis payload: total cost, total tokens, wall time, critical path, and per-agent latency/cost/data source.
5. `GET /api/metrics/llm?days=30` for cost per run, p50/p95 latency per agent, error and timeout rate per agent, and cost by tier. Add a matching MCP tool.
6. Diagnostics tab: per-agent Gantt of latency plus cost bars, and run totals.
7. Optional `LLM_TRACE_PAYLOADS=true` stores prompt hash, prompt and raw response for debugging (off by default).

**Verification:** after one live analysis, `llm_calls` rows exist for every LLM agent and the costs add up to `run_metrics.total_cost`; the Diagnostics tab renders the breakdown; the metrics endpoint returns sane p50/p95.
**Done when:** verified; screenshot of the Diagnostics tab in the PR.

### C4 · Versioned prompts + offline eval harness
**Status:** pending
**Scope and steps**
1. **Prompts:** move the inline f-strings (for example the 212-line `solution_agent._build_prompt` at `solution_agent.py:179`) into `src/prompts/<agent>/v1.md` templates. The version is recorded in `llm_calls.prompt_version`.
2. **Grounding check:** replace the 40% keyword-substring heuristic (`src/llm_guardrails.py:443-455`) with numeric-claim grounding: every number in the LLM output must trace to an input value within tolerance. Keep the existing 25 guardrail tests passing and add new ones.
3. **Eval harness** in `evals/`:
   - Fixtures: frozen `agent_results` inputs for about 5 tickers. Export them from the local DB, which already holds NVDA, CRWV, NBIS, BE and AAPL.
   - Checks: schema validity, guardrail warning counts, numeric grounding rate, cross-agent consistency (thesis direction vs. recommendation; the override rule firing correctly), and cost/latency from C3.
   - Offline mode replays cached responses and runs in CI. Live mode (`make eval-live`) is opt-in, and it is how prompt changes get compared v1 vs v2.
   - Output: a markdown scorecard in `evals/results/`.
4. **Outcome eval:** surface the existing calibration loop (`src/scheduler.py:613`, `/api/calibration/summary`) in the scorecard as the production eval: predicted vs. realized.

**Verification:** `make eval` runs offline in CI; one live eval run produces a scorecard; changing a prompt version shows up as a scorecard diff.
**Done when:** CI runs the offline evals, and the scorecard is linked from the README (D5).

---

## Phase D — Showpiece

### D1 · Live agent-run visualization
**Status:** pending
**Goal:** the moment a hiring manager remembers. Today, 7 tiny 1.5px dots (`frontend/src/components/Header.jsx:56-73`) are colored from the *previous* run's results.

**Scope and steps**
1. **Backend:** emit an `agent_done` SSE event for each agent (duration, success, data source, e.g. FMP vs. yfinance fallback, and cost from C3), alongside the existing `running_{agent}` events (`orchestrator.py:844`). Give every stage (`gathering_data`, `synthesizing`, `validating`, `saving`) and every synthesis agent a label.
2. **Frontend** — a run panel with:
   - swimlanes for the data-agent fan-out, then sentiment, then the synthesis fan-out, then validation and save;
   - live timers per agent;
   - status (running / done / fell back / timed out) plus a data-source badge;
   - a running cost counter.

   On completion it collapses into a persisted Gantt in the MetaFooter or Diagnostics.
3. **One stream owner:** today each `useAnalysis()` call creates its own `useSSE` ref, so one instance's `cancelStream` can't cancel another's stream. Keep a single owner in `AnalysisContext`.
4. Everything is driven from an **event log**, so D4 can replay it.

**Verification:** a live run shows parallel lanes filling in real time (confirm spend); replaying a saved event log renders the same view.
**Done when:** both verified; a short screen capture is saved for D6.

### D2 · Landing panel, responsive layout, accessibility
**Status:** pending
**Scope and steps**
1. **First-visit landing panel** replacing "Enter a ticker to start analysis", with:
   - a one-line pitch;
   - a mini architecture diagram (agents → synthesis → guardrails → output);
   - example-ticker chips (the D4 demo tickers);
   - a "watch a recorded run" call to action.
2. **Responsive:**
   - a sidebar drawer below `md`;
   - KPIs at `grid-cols-2 md:grid-cols-5` (`KpiRow.jsx:39`, `AnalysisView.jsx:41`), and fix the `PriceChart.jsx:358,420` `grid-cols-4`;
   - remove `body{overflow:hidden}`;
   - make the header search usable at 375px. On 2026-09-28 the sidebar covered over half the phone screen.
3. **Accessibility:**
   - `aria-label` on every icon button;
   - `--text-muted` raised from 0.35 to about 0.55 alpha (`index.css:61`);
   - a 12px minimum text size (there are 159 uses of `text-[9-11px]`);
   - visible focus states.

**Verification:** screenshots at 375, 768 and 1440; Lighthouse accessibility ≥ 90; keyboard-only navigation through the main flow.
**Done when:** verified; screenshots in the PR.

### D3 · Design-system consolidation, bundle split, component cleanup
**Status:** pending
**Scope and steps**
1. **Design system:**
   - Move the tokens into Tailwind v4 `@theme`.
   - Delete the dead v3 `frontend/tailwind.config.js`, which still has the old blue palette.
   - Replace the leftover `#006fee` (`PriceChart.jsx:241-242`, `InflectionChart.jsx:15`) and hard-coded amber `rgba(...)` (`KpiCard.jsx:13`) with tokens.
   - Chip away at the 349 inline `style={{}}`, 132 `rgba()` and 61 hex literals, prioritizing the visible screens.
   - Load fonts in one place: `index.html` loads Inter + JetBrains Mono while `index.css:2` loads Inter + Fira Code. Pick one pair.
2. **Bundle:** there is one 811 kB chunk (249 kB gzipped). Use `React.lazy` for the routes, CouncilPanel and PriceChart, and split vendor chunks with `manualChunks`. Target: no Vite >500 kB warning.
3. **Cleanup:**
   - delete the unused `ui/dialog.jsx`, `ui/dropdown-menu.jsx` and `ui/select.jsx`, plus their Radix dependencies if nothing else uses them;
   - delete the empty `components/panels/` and `views/`;
   - migrate `Icons.jsx` (276 LOC, 3 users) to lucide;
   - move the views out of the `components/` root, finishing the half-done move noted at `App.jsx:6`;
   - split `CouncilPanel.jsx` (881 LOC, 11 `useState`) into `council/` subcomponents;
   - replace the `vite.svg` favicon;
   - delete the boilerplate `frontend/README.md`, and fix or delete `FRONTEND_README.md`, which still says "5 agents".

**Verification:** `npm run build` with no chunk warning; lint green; visual parity screenshots.
**Done when:** verified.

### D4 · Static demo mode + Vercel deploy
**Status:** pending
**Scope and steps**
1. **Demo tickers (Q9 framing):** the AI-infrastructure supply chain. Suggested: **NVDA** (compute), **CRWV** (neocloud), **NBIS** (neocloud), **VRT** (data-center power and cooling), and optionally **BE** (on-site power) or **EQIX** (colocation). Confirm the list and the live-run spend with the owner.
2. `scripts/record_demo.py` runs fresh live analyses (after A2, C3 and D1, so the recordings include the thesis, cost data and a full event log). It exports each ticker's final payload, SSE event timeline with timestamps, history entries and one council result to `frontend/public/demo/<ticker>/*.json`.
3. With `VITE_DEMO_MODE=true`:
   - the `utils/api.js` layer swaps to a fixture adapter;
   - SSE is replayed with real timing (1× or 2×), so the D1 run view animates;
   - History and Watchlist are seeded from the fixtures;
   - write actions are disabled, with a tooltip: "Demo is read-only — clone the repo to run live";
   - a persistent banner reads "Recorded <date> · Not investment advice".
4. `vercel.json` with an SPA rewrite. **Deploy to Vercel** (confirm with the owner at the time). Deep links like `/analysis/CRWV?tab=thesis` must work cold.

**Verification:** a production build served with no backend running; every demo route and tab works; deep links work in a fresh browser; mobile check at 375px.
**Done when:** the public demo URL works, and is recorded here and in the status log.

### D5 · README rewrite, ADRs, docs refresh
**Status:** pending
**Scope and steps**
1. **README** (target about 150–200 lines, down from 665), in this order:
   - pitch line
   - demo link and GIF
   - Mermaid architecture diagram
   - "What's interesting here" (4 bullets: parallel orchestration with timeout budgets; deterministic guardrails and rule override; calibration loop as a production eval; agent API + MCP)
   - cost and latency numbers from C3
   - eval scorecard link from C4
   - **"Why this pattern matters for infrastructure tooling"** (Appendix C)
   - 5-minute quickstart: demo mode needs zero keys; live mode needs only `ANTHROPIC_API_KEY`, with FMP/FRED/Tavily optional upgrades
   - **"How I built this with AI agents"** (outline below)
   - link to the `equity-dd-agent-playbook` repo as the agent playbook layer
   - license and disclaimer

   Remove the internal ops notes (Phase 7 canary, Stage A/B/C/D migration notes, lines ~397-494), the "CapRelay-inspired" framing, and the stale counts (the "642 passed" at `README.md:648`).
2. **ADRs** in `docs/adr/`:
   - `0001` parallel orchestration and timeout budgets (including the A2 regression story)
   - `0002` deterministic guardrails over LLM output
   - `0003` calibration loop as outcome eval
   - `0004` agent API + MCP layer
   - `0005` unified LLM client, model tiers and cost observability
3. **Archive (Q3):**
   - tag the current state as `archive/internal-docs-2026-09` (local, not pushed);
   - `git rm -r docs/superpowers docs/plans docs/reports`;
   - update the `CLAUDE.md` line that points to `docs/plans/INDEX.md`.
4. **CLAUDE.md:** regenerate the counts from code (9 default agents, 14 in the registry, 26 personas, 27 tables, 42 MCP tools). Add `EarningsAgent` to the table. Rewrite the stale Frontend section: the Dashboard/Summary/Recommendation components and `glass-card` are gone, there are 5 tabs, and the theme is amber `#e8860c`. Delete `AGENTS.md` or reduce it to a 3-line pointer.
5. Add `tests/test_docs_consistency.py`, which asserts that the README and CLAUDE.md agent counts match `DEFAULT_AGENTS` and `AGENT_REGISTRY`.

**"How I built this with AI agents" — outline (Q7):**
- **Workflow:** spec → plan → subagent execution with Claude Code; about 205 of 241 commits are co-authored; where the plans live now (archived).
- **What I owned:** the architecture calls (orchestration model, timeout budgets, guardrail design, calibration loop, MCP surface), and review and verification of every change.
- **Where the agents got it wrong, and how I caught it.** This is the credibility section; use real examples from this campaign:
  - a resilience refactor that silently capped synthesis agents at 15s;
  - a CSS reset that zeroed all Tailwind spacing;
  - a redesign that dropped the Solution agent's output from the UI;
  - stale docs claiming 7, 9 or 16 agents.
  Then say what process fixed each: CI, evals, the docs-consistency test, run observability.
- **What I'd do differently.**

**Verification:** Mermaid renders on GitHub; every quickstart command works from a fresh clone (test in a temp dir); the docs-consistency test passes.
**Done when:** verified.

### D6 · Media, GitHub metadata, publish, resume bullets
**Status:** pending
**Scope and steps**
1. Retake the `docs/screenshots/*` images at 1440 wide from demo mode. The current hero image shows the broken spacing, the "1%" confidence and the "—" sentiment. Record a 60–90s video or GIF of a run (D1 view → verdict → thesis → diagnostics cost breakdown).
2. `gh repo edit`: final description, homepage = the demo URL, topics (`llm`, `multi-agent`, `mcp`, `fastapi`, `react`, `anthropic`, `observability`, `evals`); a social preview image; pin the repo on the GitHub profile.
3. Decide what happens to this campaign doc. Recommendation: keep a condensed version as `docs/engineering-log/2026-portfolio-hardening.md`. An audit → sequenced plan → executed PRs trail is strong evidence for TPM-with-tooling roles.
4. **Resume and LinkedIn bullets:** 3–5 quantified bullets drafted from the real C3/C4 numbers: agents, wall time p50, cost per run, test count, eval grounding rate, and PR count for the campaign. Keep them in `docs/engineering-log/` or give them to the owner directly.

**Done when:** the repo page, demo, video and bullets are all live or delivered.

---

## Appendix A — Audit findings index (2026-09-28)

| ID | Finding | Evidence | Session |
|----|---------|----------|---------|
| F1 | An unlayered CSS reset zeroes all Tailwind spacing | `frontend/src/index.css:102` | A1 |
| F2 | Thesis/narrative/tags null in 40/40 recent runs (15s outer cap) | `src/orchestrator.py:301`, `:910`; DB | A2 |
| F3 | The Solution agent's output is not rendered anywhere | `solution_agent.py:357-368`; commit `2949a39` | A4 |
| F4 | KPI row: confidence 0%, sentiment "—", SSE shape mismatch, factors dict vs array | `KpiRow.jsx:23-33`, `SentimentTab.jsx:7,25` | A1 |
| F5 | History never loads; ticker clicks dead in 3 views | `useHistory.js:103`, `App.jsx:24-27`, `AppLayout.jsx:85` | A1 |
| F6 | Retired default model id | `src/config.py:29`, `.env.example:14`, 4 agent fallbacks | A0, C2 |
| F7 | Errors never shown; ~68s startup; `/health` slow | `AnalysisView.jsx:22`, preview logs | A3 |
| F8 | No mobile layout | fixed sidebar, `body{overflow:hidden}` | D2 |
| F9 | LLM client duplicated 14×; no structured output; threads keep billing after timeout | see C1 | C1, C2 |
| F10 | No token/cost/trace observability | no `.usage` reads anywhere | C3 |
| F11 | No evals; weak grounding heuristic | `llm_guardrails.py:443-455` | C4 |
| F12 | No CI/lint/lockfile; 27 lint problems; 811 kB bundle; leaky tests | — | B1, D3 |
| F13 | No auth; permissive CORS; `0.0.0.0`; root Docker; `detail=str(e)` ×42 | `api.py:99-103`, `config.py:166` | B2 |
| F14 | 72 blocking SQLite calls in async handlers | `api.py` | B3 |
| F15 | README: jargon, 665 lines, stale counts, no LICENSE file | `README.md:3,648` | A0, D5 |
| F16 | Doc drift: `CLAUDE.MD` case, stale `AGENTS.md`, stale Frontend section | — | A0, D5 |
| F17 | Internal scratch public (`docs/superpowers`, `skills/`) | — | A0, D5 |
| F18 | Repo junk + 14 merged branches + description typo | — | A0 |
| F19 | Config sprawl; unused 1,016-LOC canary; "anti-detection" comment | `config.py:36-96,246` | B2, B3 |
| F20 | Test gaps (data_provider, 4 agents, frontend = 0) | — | B5 |
| F21 | Hourly AAPL schedule on; scheduler default on for cloners | `schedules` row id 1, `config.py:41` | A0 |
| F22 | EarningsReview says "no transcript" while the Overview shows one | Thesis & Risk tab, AAPL id 221 | A2 |
| F23 | Raw float in the fundamentals summary text | Overview, AAPL id 221 | A1 |

**Strengths to preserve and showcase:**
- deterministic guardrails plus the rule-engine override;
- the calibration loop that scores predictions against realized prices;
- request coalescing and the TTL cache in the data provider;
- straggler cancellation in the parallel runner;
- a clean 42-tool MCP server and the three-layer agent API;
- 697 fast tests passing;
- real URL routing, and SSE-aware nginx and Docker config for the frontend.

## Appendix B — Model registry target (Q5)

- **Single source of truth:** `src/llm/models.py` (C1). Nothing else in `src/` may contain a model ID string; a C2 grep check enforces this.
- **Default:** provider `anthropic`, tier `standard` → `claude-sonnet-5-5`.
- **Anthropic:** `claude-opus-5-5` (deep), `claude-sonnet-5-5` (standard), `claude-haiku-4-5-20251001` (fast).
- **OpenAI:** GPT-6 Astra / Sol / Luna per the owner. **Verify the exact API IDs and which variant maps to which tier before hardcoding.**
- **xAI:** keep supported; verify the current ID.
- **Pricing table:** sourced from provider docs with an as-of date (C3).

## Appendix C — Infrastructure framing talking points (Q9)

| This repo | Infra / data-center tooling analogue |
|-----------|---------------------------------------|
| Parallel agents over flaky vendor APIs, with fallbacks (FMP → yfinance, EDGAR) and timeout budgets | Aggregating vendor, ERP, schedule and telemetry feeds for build-out tracking when sources are late or wrong |
| Deterministic guardrails and a rule override on top of LLM output | Trustworthy numbers in capacity and project-controls reporting: the LLM drafts, rules gate |
| Calibration loop (prediction vs. realized) | Forecast vs. actual for capacity plans, energization dates and schedule slip |
| Scheduler + alert engine + inflection detection | Milestone-slip and threshold alerting across a portfolio of sites |
| Agent API + MCP server | Letting internal agents and copilots query operational systems safely |
| Per-run cost, latency and tokens (C3) | Unit economics and SLOs for internal AI tools |
| Demo tickers on the AI-infra supply chain (NVDA, CRWV, NBIS, VRT…) | Domain fluency in the neocloud / hyperscaler build-out |

Keep claims honest: frame these as transferable patterns, not as data-center experience the repo itself doesn't have.

---

## Discovered during execution
*(Append out-of-scope findings here with date and session ID.)*

- 2026-09-28 (A0): **API key health** (free/cheap endpoint checks): xAI ✅, FRED ✅, Tavily ✅, Twitter ✅; **OpenAI 401, FMP 401** (likely rotated); `ANTHROPIC_API_KEY` empty/unparseable in `.env`. Owner to refresh before live-run sessions (A2+). With FMP down, fundamentals/market fall back to yfinance.
- 2026-09-28 (A0): xAI model list includes `grok-4.3 … grok-4.7` (latest) and `grok-4.20-0309-{reasoning,non-reasoning}`, `grok-4.20-multi-agent-0309`. Interim xAI default set to `grok-4.7`; owner's `.env` still pins `grok-4.20-0309-reasoning`. C1: decide xAI tier mapping. OpenAI model list could not be fetched (401) — GPT-6 IDs still unverified.
- 2026-09-28 (A0): all `llm_config.get("model", <fallback>)` fallbacks in agents are dead code — `Config.get_llm_config()` always supplies `model`. Delete in C2 as planned. Tests still reference `claude-3-5-*` IDs as mock config values (harmless; update in C2).
- 2026-09-28 (A0): with schedulers off by default, the **daily calibration job** (the outcome-eval showcase) also doesn't run unless opted in. D5 README must say how to enable it; C4 scorecard should read existing `analysis_outcomes` rows.
- 2026-09-28 (A0): backend startup measured at ~19s to `Application startup complete` (OpenBB init ~12s, macro pre-warm ~7s) with scheduler off; the 68s seen during the audit included scheduler setup + reloads from concurrent test runs. A3 target unchanged (≤10s).
- 2026-09-28 (audit): `.claude/launch.json` called a bare `python`, which isn't on PATH; changed to `venv/bin/python` (untracked file).

## Session log
*(Append-only. Format: `YYYY-MM-DD · <ID> · <status> · <PR link> · <notes>`)*

- 2026-09-28 · audit · done · — · Phases 1–3 presented; owner answered Q1–Q9; this campaign doc written.
- 2026-09-28 · A0 · in progress · [PR #8](https://github.com/ewyluda/multi-agent-market-research/pull/8) · Playbook repo created: https://github.com/ewyluda/equity-dd-agent-playbook (13 skills commits via subtree split + README/LICENSE/validator; 65/65 files validate). LICENSE added; CLAUDE.MD→CLAUDE.md; schedulers default off; AAPL schedule disabled in local DB; model defaults updated; junk removed. Branches: 6 local + 4 remote deleted (3 remote were already gone); `delete_branch_on_merge` enabled; description fixed. Verified: 697 fast tests pass; backend starts ~19s with no scheduler jobs. Blocked for owner: PR merge, local `main` reset.
