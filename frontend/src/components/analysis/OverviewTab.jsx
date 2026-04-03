import CompanyOverview from '@/components/CompanyOverview'
import EarningsPanel from '@/components/EarningsPanel'
import PriceChart from '@/components/PriceChart'

export default function OverviewTab({ analysis }) {
  return (
    <div className="space-y-6">
      <CompanyOverview analysis={analysis} />
      <EarningsPanel analysis={analysis} />
      <PriceChart analysis={analysis} />
    </div>
  )
}
