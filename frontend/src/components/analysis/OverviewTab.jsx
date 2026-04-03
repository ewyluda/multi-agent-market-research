import CompanyOverview from '@/components/CompanyOverview'
import EarningsPanel from '@/components/EarningsPanel'
import PriceChart from '@/components/PriceChart'

export default function OverviewTab({ analysis }) {
  const hasFundamentals = analysis?.agent_results?.fundamentals?.data
  const hasMarket = analysis?.agent_results?.market?.data
  const hasEarnings = analysis?.agent_results?.fundamentals?.data?.earnings

  if (!hasFundamentals && !hasMarket && !hasEarnings) {
    return (
      <div className="text-center py-12 text-[var(--muted-foreground)]">
        <p>No overview data available for this analysis.</p>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <CompanyOverview analysis={analysis} />
      <EarningsPanel analysis={analysis} />
      <PriceChart analysis={analysis} />
    </div>
  )
}
