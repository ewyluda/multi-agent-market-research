import TechnicalsOptionsSection from '@/components/TechnicalsOptionsSection'
import PriceChart from '@/components/PriceChart'

export default function TechnicalsTab({ analysis }) {
  return (
    <div className="space-y-6">
      <PriceChart analysis={analysis} />
      <TechnicalsOptionsSection analysis={analysis} />
    </div>
  )
}
