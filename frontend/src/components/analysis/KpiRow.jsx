import { DollarSign, Target, Gauge, TrendingUp, BarChart3 } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import KpiCard from './KpiCard'
import { motion } from 'framer-motion'

const REC_VARIANT = {
  BUY: 'success', 'STRONG BUY': 'success',
  SELL: 'danger', 'STRONG SELL': 'danger',
  HOLD: 'warning',
}

function formatPrice(price) {
  if (!price && price !== 0) return '—'
  return '$' + Number(price).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

export default function KpiRow({ analysis }) {
  if (!analysis) return null

  const market = analysis.agent_results?.market?.data || {}
  const fundamentals = analysis.agent_results?.fundamentals?.data || {}
  const sentiment = analysis.agent_results?.sentiment?.data || analysis.analysis?.sentiment || {}
  const recommendation = analysis.signal_contract_v2?.recommendation || analysis.recommendation || '—'
  const confidence = analysis.confidence_score ?? analysis.signal_contract_v2?.confidence
  const price = market.current_price || market.price
  const change1d = market.change_1d ?? market.percent_change
  const sentimentScore = sentiment.overall_score ?? sentiment.composite_score
  const pe = fundamentals.pe_ratio ?? fundamentals.pe

  const cards = [
    { icon: DollarSign, label: 'Price', value: formatPrice(price), trend: change1d },
    null, // recommendation card is custom
    { icon: Gauge, label: 'Confidence', value: confidence != null ? `${Math.round(confidence)}%` : '—', trendLabel: confidence != null ? 'AI confidence score' : undefined },
    { icon: TrendingUp, label: 'Sentiment', value: sentimentScore != null ? (sentimentScore > 0 ? '+' : '') + sentimentScore.toFixed(2) : '—', trendLabel: sentimentScore != null ? (sentimentScore > 0.3 ? 'Bullish' : sentimentScore < -0.3 ? 'Bearish' : 'Neutral') : undefined },
    { icon: BarChart3, label: 'P/E Ratio', value: pe != null ? pe.toFixed(1) + 'x' : '—', trendLabel: 'Price to earnings' },
  ]

  return (
    <div className="grid grid-cols-5 gap-4 mb-6">
      {cards.map((card, i) => (
        <motion.div key={i} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.2, delay: i * 0.05 }}>
          {card ? (
            <KpiCard {...card} />
          ) : (
            /* Recommendation card */
            <div className="rounded-lg border border-[var(--border)] bg-[var(--card)] p-4">
              <div className="flex items-start justify-between mb-3">
                <div className="w-9 h-9 rounded-lg flex items-center justify-center" style={{ backgroundColor: 'rgba(232, 134, 12, 0.1)' }}>
                  <Target className="w-4.5 h-4.5 text-[var(--primary)]" />
                </div>
              </div>
              <p className="text-xs text-[var(--muted-foreground)] mb-1">Rating</p>
              <Badge variant={REC_VARIANT[recommendation?.toUpperCase()] || 'secondary'} className="text-base px-3 py-0.5">
                {recommendation}
              </Badge>
            </div>
          )}
        </motion.div>
      ))}
    </div>
  )
}
