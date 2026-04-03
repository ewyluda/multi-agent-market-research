import TechnicalsOptionsSection from '@/components/TechnicalsOptionsSection'
import PriceChart from '@/components/PriceChart'

export default function TechnicalsTab({ analysis }) {
  const hasTechnicals = analysis?.agent_results?.technical?.data
  const hasOptions = analysis?.agent_results?.options?.data
  const hasMarket = analysis?.agent_results?.market?.data

  if (!hasTechnicals && !hasOptions && !hasMarket) {
    return (
      <div className="text-center py-12 text-[var(--muted-foreground)]">
        <p>No technical or options data available for this analysis.</p>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <PriceChart analysis={analysis} />
      <TechnicalsOptionsSection analysis={analysis} />
    </div>
  )
}
