/**
 * The backend returns analyses in two shapes:
 *  - GET /api/analysis/{ticker}/latest → flat DB row (recommendation, confidence_score,
 *    overall_sentiment_score, timestamp, id …) plus `analysis` (payload) and `agent_results`.
 *  - SSE `result` event → { success, ticker, analysis_id, analysis, agent_results,
 *    duration_seconds } with the headline fields nested inside `analysis`.
 *
 * Components read one canonical shape; this adapter fills the top-level fields from
 * whichever source has them.
 */

const firstDefined = (...values) => values.find((v) => v !== undefined && v !== null) ?? null

export function normalizeAnalysis(raw) {
  if (!raw) return raw

  const payload = raw.analysis || {}
  const agentResults = raw.agent_results || {}
  const sentimentData = agentResults.sentiment?.data || {}

  return {
    ...raw,
    id: firstDefined(raw.id, raw.analysis_id),
    ticker: firstDefined(raw.ticker, payload.ticker),
    timestamp: firstDefined(raw.timestamp, payload.timestamp, raw.success ? new Date().toISOString() : null),
    recommendation: firstDefined(raw.recommendation, payload.recommendation),
    // 0–1 scale everywhere; format as a percentage at display time.
    confidence_score: firstDefined(raw.confidence_score, payload.confidence),
    confidence_calibrated: firstDefined(raw.confidence_calibrated, payload.confidence_calibrated),
    // −1..1 scale.
    overall_sentiment_score: firstDefined(raw.overall_sentiment_score, sentimentData.overall_sentiment),
    signal_contract_v2: firstDefined(raw.signal_contract_v2, payload.signal_contract_v2),
    rationale_summary: firstDefined(raw.rationale_summary, payload.rationale_summary),
    duration_seconds: firstDefined(raw.duration_seconds, payload.duration_seconds),
    analysis: payload,
    agent_results: agentResults,
  }
}

/** Percent string for a 0–1 score (tolerates values already on a 0–100 scale). */
export function formatPercent(score) {
  if (score === null || score === undefined || Number.isNaN(Number(score))) return '—'
  const n = Number(score)
  return `${Math.round(n <= 1 ? n * 100 : n)}%`
}
