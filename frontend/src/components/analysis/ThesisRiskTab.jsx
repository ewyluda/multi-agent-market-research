import ThesisPanel from '@/components/ThesisPanel'
import NarrativePanel from '@/components/NarrativePanel'
import RiskDiffPanel from '@/components/RiskDiffPanel'
import EarningsReviewPanel from '@/components/EarningsReviewPanel'

export default function ThesisRiskTab({ analysis }) {
  const hasThesis = analysis?.analysis?.thesis
  const hasNarrative = analysis?.analysis?.narrative
  const hasRiskDiff = analysis?.analysis?.risk_diff
  const hasEarningsReview = analysis?.analysis?.earnings_review

  return (
    <div className="space-y-6">
      {hasThesis && <ThesisPanel analysis={analysis} />}
      {hasNarrative && <NarrativePanel analysis={analysis} />}
      {hasRiskDiff && <RiskDiffPanel analysis={analysis} />}
      {hasEarningsReview && <EarningsReviewPanel analysis={analysis} />}
      {!hasThesis && !hasNarrative && !hasRiskDiff && !hasEarningsReview && (
        <div className="text-center py-12 text-[var(--muted-foreground)]">
          <p>No thesis or risk data available for this analysis.</p>
        </div>
      )}
    </div>
  )
}
