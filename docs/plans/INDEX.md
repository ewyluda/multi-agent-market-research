# Feature Plans Index

Consolidated reference for all implementation plans in this project.

| Date | Plan | Status | Key Outcome |
|------|------|--------|-------------|
| 2026-02-12 | [Frontend Redesign](./2026-02-12-frontend-redesign.md) | ✅ Completed | Replaced horizontal nav with 64px icon sidebar + tabbed content + right sidebar |
| 2026-02-12 | [Frontend Design Spec](./2026-02-12-frontend-redesign-design.md) | ✅ Completed | Design spec for the above redesign |
| 2026-02-12 | [Twitter/X Integration](./2026-02-12-twitter-x-integration-design.md) | ✅ Approved / Implemented | Twitter API v2 social sentiment as 5th sentiment factor; flows via NewsAgent → SentimentAgent |
| 2026-02-15 | [Actionable Insights Roadmap](./2026-02-15-actionable-insights-roadmap.md) | ✅ Phases 1–3 Implemented | Signal contract v2, calibration, portfolio advisor, alerts v2, scenario framing |
| 2026-02-16 | [Quant PM Upgrade](./2026-02-16-quant-pm-upgrade-implementation-plan.md) | ✅ Phases 0–6 Completed; Phase 7 operational hardening in progress | EV scoring, confidence calibration, regime labels, portfolio engine, watchlist ranking |
| 2026-02-17 | [Analysis Intelligence Upgrade](./2026-02-17-analysis-intelligence-implementation-plan.md) | ✅ Completed | V2 features enabled, calibration grounding, ticker validation, bulk analysis endpoint, calibration card |
| 2026-02-17 | [Analysis Intelligence Design](./2026-02-17-analysis-intelligence-design.md) | ✅ Reference spec | Design spec for the above upgrade |
| 2026-03-10 | [OpenBB Data Pipeline Migration](../superpowers/plans/2026-03-10-openbb-data-pipeline.md) | ✅ Completed | Replaced Alpha Vantage with centralized `OpenBBDataProvider` backed by OpenBB Platform SDK v4.7+ |
| — | [Leadership Agent](./leadership-agent-implementation.md) | ✅ Completed | Four Capitals Framework leadership scorecard; LeadershipPanel tab |

## In Progress / Planned

| Feature | Description | Spec |
|---------|-------------|------|
| **Investor Council** | Qualitative layer — 26 investor personas (see `src/agents/council/`). Phase 2 (primary 5 agents) complete. Phase 3 (thesis health monitor), Phase 4 (synthesis view), Phase 5 (ATLAS layering) planned. | — |
| **Two-Tier Validation Agent** | Cross-validates synthesis and council claims against raw agent data. Tier 1a: deterministic rule engine (direction, numeric, regime, technical, options consistency). Tier 1b: LLM-powered council validator. Tier 2: human spot-checks via alert pipeline. Contradictions penalize confidence (capped at 0.50 total penalty). Feature-flagged via `ENABLE_VALIDATION_V1`. | [Design spec](../superpowers/specs/2026-03-30-two-tier-validation-agent-design.md) · [Implementation plan](../superpowers/plans/2026-03-30-two-tier-validation-agent.md) |

## Phase 7 Rollout Status

Phase 7 of the Quant PM Upgrade covers operational hardening, backfill, and canary rollout of signal contract v2 features. Gate metrics tracked at `GET /api/rollout/phase7/status`. See [Quant PM Upgrade plan](./2026-02-16-quant-pm-upgrade-implementation-plan.md) for gate criteria.
