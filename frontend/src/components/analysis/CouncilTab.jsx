import CouncilPanel from '@/components/CouncilPanel'
import LeadershipPanel from '@/components/LeadershipPanel'

export default function CouncilTab({ analysis }) {
  return (
    <div className="space-y-6">
      <CouncilPanel analysis={analysis} ticker={analysis?.ticker} />
      <LeadershipPanel analysis={analysis} />
    </div>
  )
}
