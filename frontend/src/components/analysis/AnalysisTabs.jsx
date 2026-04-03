import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs'
import OverviewTab from './OverviewTab'
import ThesisRiskTab from './ThesisRiskTab'
import TechnicalsTab from './TechnicalsTab'
import SentimentTab from './SentimentTab'
import CouncilTab from './CouncilTab'
import { motion } from 'framer-motion'

const TABS = [
  { value: 'overview', label: 'Overview' },
  { value: 'thesis', label: 'Thesis & Risk' },
  { value: 'technicals', label: 'Technicals' },
  { value: 'sentiment', label: 'Sentiment' },
  { value: 'council', label: 'Council' },
]

export default function AnalysisTabs({ analysis }) {
  return (
    <Tabs defaultValue="overview" className="w-full">
      <TabsList className="w-full justify-start bg-transparent border-b border-[var(--border)] rounded-none p-0 h-auto gap-0">
        {TABS.map((tab) => (
          <TabsTrigger
            key={tab.value}
            value={tab.value}
            className="rounded-none border-b-2 border-transparent data-[state=active]:border-[var(--primary)] data-[state=active]:bg-transparent data-[state=active]:text-[var(--text-primary)] data-[state=active]:shadow-none px-4 py-2.5 text-sm"
          >
            {tab.label}
          </TabsTrigger>
        ))}
      </TabsList>

      {[
        { value: 'overview', Component: OverviewTab },
        { value: 'thesis', Component: ThesisRiskTab },
        { value: 'technicals', Component: TechnicalsTab },
        { value: 'sentiment', Component: SentimentTab },
        { value: 'council', Component: CouncilTab },
      ].map(({ value, Component }) => (
        <TabsContent key={value} value={value}>
          <motion.div initial={{ opacity: 0, y: 4 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.15 }}>
            <Component analysis={analysis} />
          </motion.div>
        </TabsContent>
      ))}
    </Tabs>
  )
}
