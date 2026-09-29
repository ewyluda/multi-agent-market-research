import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import { useAnalysisContext } from '@/context/AnalysisContext'
import { useAnalysis } from '@/hooks/useAnalysis'
import { Skeleton } from '@/components/ui/skeleton'
import { Button } from '@/components/ui/button'
import KpiRow from './KpiRow'
import VerdictHero from './VerdictHero'
import AnalysisTabs from './AnalysisTabs'
import MetaFooter from '@/components/MetaFooter'
import { motion } from 'framer-motion'

export default function AnalysisView() {
  const { ticker: routeTicker } = useParams()
  const ticker = routeTicker?.toUpperCase()
  const { analysis: loadedAnalysis, loading, currentTicker } = useAnalysisContext()
  const { fetchLatest, runAnalysis } = useAnalysis()
  const [missingTicker, setMissingTicker] = useState(null)

  // The route is the source of truth: load the latest saved analysis whenever the URL
  // ticker differs from what's in context, unless a live run for it is already streaming.
  useEffect(() => {
    if (!ticker) return
    if (loadedAnalysis?.ticker?.toUpperCase() === ticker) return
    if (loading && currentTicker?.toUpperCase() === ticker) return
    setMissingTicker(null)
    fetchLatest(ticker).catch(() => setMissingTicker(ticker))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ticker])

  // Never show one ticker's analysis under another ticker's URL.
  const analysis = !ticker || loadedAnalysis?.ticker?.toUpperCase() === ticker ? loadedAnalysis : null

  if (ticker && missingTicker === ticker && !loading) {
    return (
      <div className="flex flex-col items-center justify-center h-[60vh] text-center">
        <p className="text-xl font-semibold text-[var(--text-primary)] mb-2">No saved analysis for {ticker} yet</p>
        <p className="text-sm text-[var(--muted-foreground)] max-w-md mb-6">
          A live run fans out to the data agents, then the synthesis agents. It takes about a minute and uses your API credits.
        </p>
        <Button onClick={() => runAnalysis(ticker).catch(() => {})}>Run analysis for {ticker}</Button>
      </div>
    )
  }

  if (!analysis && !loading && !ticker) {
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

  if (!analysis) {
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
      <VerdictHero analysis={analysis} />
      <AnalysisTabs analysis={analysis} />
      <MetaFooter analysis={analysis} />
    </motion.div>
  )
}
