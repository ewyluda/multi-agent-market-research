import { useEffect } from 'react'
import { useParams } from 'react-router-dom'
import { useAnalysisContext } from '@/context/AnalysisContext'
import { useAnalysis } from '@/hooks/useAnalysis'
import { Skeleton } from '@/components/ui/skeleton'
import KpiRow from './KpiRow'
import AnalysisTabs from './AnalysisTabs'
import MetaFooter from '@/components/MetaFooter'
import { motion } from 'framer-motion'

export default function AnalysisView() {
  const { ticker } = useParams()
  const { analysis, loading } = useAnalysisContext()
  const { fetchLatest } = useAnalysis()

  useEffect(() => {
    if (ticker && !analysis && !loading) {
      fetchLatest(ticker)
    }
  }, [ticker])

  if (!analysis && !loading) {
    return (
      <div className="flex flex-col items-center justify-center h-[60vh] text-center">
        <div className="w-16 h-16 rounded-2xl bg-[var(--secondary)] flex items-center justify-center mb-6">
          <span className="text-3xl text-[var(--primary)]">$</span>
        </div>
        <p className="text-xl font-semibold text-[var(--text-primary)] mb-2">
          Enter a ticker to start analysis
        </p>
        <p className="text-sm text-[var(--muted-foreground)] max-w-md">
          Search for any stock symbol above to get AI-powered market research with insights from 9 specialized agents.
        </p>
      </div>
    )
  }

  if (loading && !analysis) {
    return (
      <div className="space-y-6">
        <div className="grid grid-cols-5 gap-4">
          {[...Array(5)].map((_, i) => (
            <Skeleton key={i} className="h-28 rounded-lg" />
          ))}
        </div>
        <Skeleton className="h-10 w-96 rounded-lg" />
        <Skeleton className="h-64 rounded-lg" />
        <Skeleton className="h-48 rounded-lg" />
      </div>
    )
  }

  return (
    <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ duration: 0.2 }}>
      <KpiRow analysis={analysis} />
      <AnalysisTabs analysis={analysis} />
      <MetaFooter analysis={analysis} />
    </motion.div>
  )
}
