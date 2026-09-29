import { useState } from 'react'
import { ShieldCheck, ShieldAlert, Scale, TrendingUp, TrendingDown } from 'lucide-react'
import { Card } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { formatPercent } from '@/utils/normalizeAnalysis'

/**
 * The Solution agent's headline answer plus the deterministic checks applied to it:
 * rating, rationale, price plan, scenarios, risks/opportunities, validation status,
 * rule-engine override, and guardrail adjustments.
 */

const REC_VARIANT = { BUY: 'success', SELL: 'danger', HOLD: 'warning' }
const tint = (color, pct = 14) => `color-mix(in srgb, ${color} ${pct}%, transparent)`

const humanize = (value) =>
  typeof value === 'string' ? value.toLowerCase().replace(/_/g, ' ').replace(/^\w/, (c) => c.toUpperCase()) : null

const money = (n) => `$${Number(n).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
const signedPct = (n, digits = 1) => `${n > 0 ? '+' : ''}${n.toFixed(digits)}%`
const isNum = (n) => typeof n === 'number' && Number.isFinite(n)

function SectionLabel({ children }) {
  return <h3 className="text-[11px] font-semibold uppercase tracking-wider text-[var(--text-muted)] mb-2">{children}</h3>
}

function ValidationBadge({ validation, overridden, overrideEvidence }) {
  if (overridden) {
    return (
      <Badge variant="danger" className="gap-1" title={overrideEvidence || undefined}>
        <ShieldAlert className="h-3 w-3" aria-hidden /> Overridden by rule engine
      </Badge>
    )
  }
  if (!validation) return null
  const rules = validation.rule_validation || {}
  const status = validation.overall_status || 'clean'
  const variant = status === 'clean' ? 'success' : status === 'contradictions' ? 'danger' : 'warning'
  const Icon = status === 'clean' ? ShieldCheck : ShieldAlert
  const rulesText = isNum(rules.total_rules_checked) ? ` · ${rules.passed}/${rules.total_rules_checked} rules passed` : ''
  return (
    <Badge variant={variant} className="gap-1">
      <Icon className="h-3 w-3" aria-hidden /> Validation {status}{rulesText}
    </Badge>
  )
}

function PriceLadder({ targets, currentPrice }) {
  const points = [
    { key: 'stop', label: 'Stop', value: targets.stop_loss, color: 'var(--danger)' },
    { key: 'entry', label: 'Entry', value: targets.entry, color: 'var(--text-secondary)' },
    { key: 'target', label: 'Target', value: targets.target, color: 'var(--success)' },
  ].filter((p) => isNum(p.value))
  if (points.length === 0) return null

  const all = [...points.map((p) => p.value), ...(isNum(currentPrice) ? [currentPrice] : [])]
  const lo = Math.min(...all)
  const hi = Math.max(...all)
  const pad = (hi - lo) * 0.06 || hi * 0.05
  const pos = (v) => ((v - (lo - pad)) / (hi - lo + 2 * pad)) * 100

  const { entry, target, stop_loss: stop } = targets
  const rewardRisk = isNum(entry) && isNum(target) && isNum(stop) && entry > stop ? (target - entry) / (entry - stop) : null

  return (
    <div>
      <SectionLabel>Price plan</SectionLabel>
      <div
        className="relative h-10 mb-3"
        role="img"
        aria-label={points.map((p) => `${p.label} ${money(p.value)}`).join(', ') + (isNum(currentPrice) ? `, current ${money(currentPrice)}` : '')}
      >
        <div className="absolute top-1/2 left-0 right-0 h-1 -translate-y-1/2 rounded-full bg-[var(--muted)]" />
        {isNum(stop) && isNum(target) && (
          <div
            className="absolute top-1/2 h-1 -translate-y-1/2 rounded-full"
            style={{
              left: `${pos(Math.min(stop, target))}%`,
              width: `${Math.abs(pos(target) - pos(stop))}%`,
              background: `linear-gradient(90deg, ${tint('var(--danger)', 60)}, ${tint('var(--success)', 60)})`,
            }}
          />
        )}
        {points.map((p) => (
          <div key={p.key} className="absolute top-1/2 -translate-x-1/2 -translate-y-1/2" style={{ left: `${pos(p.value)}%` }}>
            <div className="h-3.5 w-3.5 rounded-full border-2 border-[var(--card)]" style={{ background: p.color }} />
          </div>
        ))}
        {isNum(currentPrice) && (
          <div className="absolute top-0 bottom-0 -translate-x-1/2 flex flex-col items-center" style={{ left: `${pos(currentPrice)}%` }}>
            <div className="w-0.5 h-full bg-[var(--primary)]" />
          </div>
        )}
      </div>
      <dl className="grid grid-cols-3 gap-2 text-center">
        {points.map((p) => (
          <div key={p.key}>
            <dt className="text-[11px] text-[var(--text-muted)]">{p.label}</dt>
            <dd className="font-data text-sm text-[var(--text-primary)]">{money(p.value)}</dd>
            {isNum(currentPrice) && (
              <dd className="font-data text-[11px]" style={{ color: p.value >= currentPrice ? 'var(--success)' : 'var(--danger)' }}>
                {signedPct(((p.value - currentPrice) / currentPrice) * 100)}
              </dd>
            )}
          </div>
        ))}
      </dl>
      <p className="mt-2 text-[11px] text-[var(--text-muted)] flex items-center justify-between">
        {isNum(currentPrice) && (
          <span className="flex items-center gap-1.5">
            <span className="inline-block w-2.5 h-0.5 bg-[var(--primary)]" aria-hidden /> Current {money(currentPrice)}
          </span>
        )}
        {rewardRisk != null && (
          <span className="font-data">
            Reward/risk <span className="text-[var(--text-secondary)]">{rewardRisk.toFixed(1)}×</span>
          </span>
        )}
      </p>
    </div>
  )
}

function Scenarios({ scenarios, guardrailWarnings }) {
  const rows = ['bull', 'base', 'bear']
    .map((key) => ({ key, ...(scenarios?.[key] || {}) }))
    .filter((s) => isNum(s.probability) || isNum(s.expected_return_pct))
  if (rows.length === 0) return null

  const weighted = rows.every((s) => isNum(s.probability) && isNum(s.expected_return_pct))
    ? rows.reduce((sum, s) => sum + s.probability * s.expected_return_pct, 0)
    : null
  const clamped = (key) => (guardrailWarnings || []).some((w) => w.includes(`scenario '${key}'`))
  const color = { bull: 'var(--success)', base: 'var(--info)', bear: 'var(--danger)' }

  return (
    <div>
      <SectionLabel>Scenarios</SectionLabel>
      <ul className="space-y-2.5">
        {rows.map((s) => (
          <li key={s.key} title={s.thesis || undefined}>
            <div className="flex items-baseline justify-between text-xs mb-1">
              <span className="capitalize text-[var(--text-secondary)]">
                {s.key}
                {clamped(s.key) && (
                  <span className="ml-1.5 text-[10px] text-[var(--warning)]" title="Return clamped to ±30% by a deterministic guardrail">
                    clamped
                  </span>
                )}
              </span>
              <span className="font-data">
                <span className="text-[var(--text-muted)]">{isNum(s.probability) ? formatPercent(s.probability) : '—'}</span>
                {isNum(s.expected_return_pct) && (
                  <span className="ml-2" style={{ color: color[s.key] }}>{signedPct(s.expected_return_pct)}</span>
                )}
              </span>
            </div>
            <div className="h-1.5 rounded-full bg-[var(--muted)] overflow-hidden" role="img" aria-label={`${s.key} probability ${formatPercent(s.probability)}`}>
              <div className="h-full rounded-full" style={{ width: `${Math.min(100, (s.probability || 0) * 100)}%`, background: color[s.key] }} />
            </div>
          </li>
        ))}
      </ul>
      {weighted != null && (
        <p className="mt-2.5 text-[11px] text-[var(--text-muted)]">
          Probability-weighted return{' '}
          <span className="font-data" style={{ color: weighted >= 0 ? 'var(--success)' : 'var(--danger)' }}>
            {signedPct(weighted)}
          </span>
        </p>
      )}
    </div>
  )
}

function BulletList({ items, positive }) {
  const Icon = positive ? TrendingUp : TrendingDown
  const color = positive ? 'var(--success)' : 'var(--danger)'
  return (
    <ul className="space-y-1.5">
      {items.slice(0, 3).map((item, i) => (
        <li key={i} className="flex gap-2 text-[13px] leading-snug text-[var(--text-secondary)]">
          <Icon className="h-3.5 w-3.5 mt-0.5 shrink-0" style={{ color }} aria-hidden />
          <span>{item}</span>
        </li>
      ))}
    </ul>
  )
}

export default function VerdictHero({ analysis }) {
  const [expanded, setExpanded] = useState(false)
  const payload = analysis?.analysis || {}
  const recommendation = (analysis?.recommendation || payload.recommendation || '').toUpperCase()
  const rationale = payload.rationale_summary || payload.reasoning || analysis?.solution_agent_reasoning
  const targets = payload.price_targets || {}
  const risks = Array.isArray(payload.risks) ? payload.risks : []
  const opportunities = Array.isArray(payload.opportunities) ? payload.opportunities : []
  const guardrailWarnings = Array.isArray(payload.guardrail_warnings) ? payload.guardrail_warnings : []
  const validation = payload.validation
  const overrideRule = (validation?.rule_validation?.results || []).find(
    (r) => r.rule_id === 'recommendation_override' && r.passed === false,
  )
  const currentPrice = analysis?.agent_results?.market?.data?.current_price
  const hasPlan = [targets.entry, targets.target, targets.stop_loss].some(isNum)
  const hasScenarios = payload.scenarios && Object.keys(payload.scenarios).length > 0

  if (!recommendation && !rationale && !hasPlan) return null

  const confidence = analysis?.confidence_calibrated ?? analysis?.confidence_score ?? payload.confidence
  const meta = [humanize(payload.position_size) && `${humanize(payload.position_size)} position`, humanize(payload.time_horizon)].filter(Boolean)

  return (
    <Card className="mb-6 overflow-hidden" aria-labelledby="verdict-heading">
      <div
        className="h-0.5"
        style={{ background: `var(--accent-${recommendation === 'BUY' ? 'buy' : recommendation === 'SELL' ? 'sell' : 'hold'})` }}
        aria-hidden
      />
      <div className="grid grid-cols-1 xl:grid-cols-[minmax(0,1fr)_320px] gap-6 p-5">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2 mb-3">
            <h2 id="verdict-heading" className="text-sm font-semibold text-[var(--text-primary)] mr-1 flex items-center gap-1.5">
              <Scale className="h-4 w-4 text-[var(--primary)]" aria-hidden /> Verdict
            </h2>
            {recommendation && (
              <Badge variant={REC_VARIANT[recommendation] || 'secondary'} className="text-sm px-2.5">
                {recommendation}
              </Badge>
            )}
            {confidence != null && (
              <span className="text-xs text-[var(--text-secondary)] font-data">{formatPercent(confidence)} confidence</span>
            )}
            {meta.map((m) => (
              <span key={m} className="text-[11px] px-1.5 py-0.5 rounded bg-[var(--secondary)] text-[var(--text-muted)]">{m}</span>
            ))}
            <span className="ml-auto">
              <ValidationBadge validation={validation} overridden={payload.recommendation_overridden} overrideEvidence={overrideRule?.evidence} />
            </span>
          </div>

          {rationale && (
            <div className="mb-4">
              <p className={`text-sm leading-relaxed text-[var(--text-secondary)] ${expanded ? '' : 'line-clamp-3'}`}>{rationale}</p>
              {rationale.length > 280 && (
                <button
                  type="button"
                  onClick={() => setExpanded((v) => !v)}
                  className="mt-1 text-xs text-[var(--primary)] opacity-80 hover:opacity-100"
                  aria-expanded={expanded}
                >
                  {expanded ? 'Show less' : 'Show full rationale'}
                </button>
              )}
            </div>
          )}

          {(risks.length > 0 || opportunities.length > 0) && (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
              {opportunities.length > 0 && (
                <div>
                  <SectionLabel>Top opportunities</SectionLabel>
                  <BulletList items={opportunities} positive />
                </div>
              )}
              {risks.length > 0 && (
                <div>
                  <SectionLabel>Top risks</SectionLabel>
                  <BulletList items={risks} positive={false} />
                </div>
              )}
            </div>
          )}

          {(guardrailWarnings.length > 0 || overrideRule) && (
            <details className="mt-4 text-xs text-[var(--text-muted)]">
              <summary className="cursor-pointer select-none hover:text-[var(--text-secondary)]">
                {guardrailWarnings.length > 0 && `${guardrailWarnings.length} guardrail adjustment${guardrailWarnings.length === 1 ? '' : 's'}`}
                {guardrailWarnings.length > 0 && overrideRule && ' · '}
                {overrideRule && 'rule-engine override'}
                <span className="ml-1 text-[var(--text-muted)]">— deterministic checks applied to the model's output</span>
              </summary>
              <ul className="mt-2 space-y-1 pl-4 list-disc marker:text-[var(--warning)]">
                {overrideRule && <li className="text-[var(--danger)]">{overrideRule.evidence}</li>}
                {guardrailWarnings.map((w, i) => (
                  <li key={i} className="text-[var(--text-secondary)]">{w}</li>
                ))}
              </ul>
            </details>
          )}
        </div>

        {(hasPlan || hasScenarios) && (
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-1 gap-5 border-t border-[var(--border)] pt-5 xl:border-t-0 xl:pt-0 xl:border-l xl:pl-6">
            {hasPlan && <PriceLadder targets={targets} currentPrice={currentPrice} />}
            {hasScenarios && <Scenarios scenarios={payload.scenarios} guardrailWarnings={guardrailWarnings} />}
          </div>
        )}
      </div>
    </Card>
  )
}
