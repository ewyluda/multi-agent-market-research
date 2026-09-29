import { useEffect, useState } from 'react'
import { useOutletContext, useParams } from 'react-router-dom'
import { AlertTriangle, RotateCw, WifiOff } from 'lucide-react'
import { useAnalysisContext } from '@/context/AnalysisContext'
import { useAnalysis } from '@/hooks/useAnalysis'
import { Skeleton } from '@/components/ui/skeleton'
import { Button } from '@/components/ui/button'
import KpiRow from './KpiRow'
import VerdictHero from './VerdictHero'
import AnalysisTabs from './AnalysisTabs'
import MetaFooter from '@/components/MetaFooter'
import { motion } from 'framer-motion'

function ErrorBanner({ title, message, onRetry, retryLabel = 'Retry' }) {
  return (
    <div
      role="alert"
      className="mb-6 flex items-start gap-3 rounded-lg border px-4 py-3"
      style={{ borderColor: 'color-mix(in srgb, var(--danger) 35%, transparent)', background: 'color-mix(in srgb, var(--danger) 8%, transparent)' }}
    >
      <AlertTriangle className="h-4 w-4 mt-0.5 shrink-0 text-[var(--danger)]" aria-hidden />
      <div className="min-w-0 flex-1">
        <p className="text-sm font-medium text-[var(--text-primary)]">{title}</p>
        {message && <p className="text-xs text-[var(--text-secondary)] mt-0.5 break-words">{message}</p>}
      </div>
      {onRetry && (
        <Button size="sm" variant="secondary" onClick={onRetry} className="shrink-0 gap-1.5">
          <RotateCw className="h-3.5 w-3.5" aria-hidden /> {retryLabel}
        </Button>
      )}
    </div>
  )
}

export default function AnalysisView() {
  const { ticker: routeTicker } = useParams()
  const ticker = routeTicker?.toUpperCase()
  const { backend } = useOutletContext() || {}
  const { analysis: loadedAnalysis, loading, currentTicker, error, stage } = useAnalysisContext()
  const { fetchLatest, runAnalysis } = useAnalysis()
  const [missingTicker, setMissingTicker] = useState(null)
  const [loadError, setLoadError] = useState(null)

  const load = (t) => {
    setMissingTicker(null)
    setLoadError(null)
    fetchLatest(t).catch((err) => {
      // 404 = nothing saved yet; anything else (network, 5xx) is a real failure to surface.
      if (err?.response?.status === 404) setMissingTicker(t)
      else setLoadError({ ticker: t, message: err?.message || 'Request failed' })
    })
  }

  // The route is the source of truth: load the latest saved analysis whenever the URL
  // ticker differs from what's in context, unless a live run for it is already streaming.
  useEffect(() => {
    if (!ticker) return
    if (loadedAnalysis?.ticker?.toUpperCase() === ticker) return
    if (loading && currentTicker?.toUpperCase() === ticker) return
    load(ticker)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ticker])

  // If the backend was down and comes back, retry the failed load automatically.
  useEffect(() => {
    if (loadError?.ticker === ticker && backend?.status === 'online') load(ticker)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [backend?.status])

  // Never show one ticker's analysis under another ticker's URL.
  const analysis = !ticker || loadedAnalysis?.ticker?.toUpperCase() === ticker ? loadedAnalysis : null
  const runFailed = stage === 'error' && error && currentTicker?.toUpperCase() === ticker
  const retryRun = () => runAnalysis(ticker).catch(() => {})

  if (ticker && loadError?.ticker === ticker && !analysis && !loading) {
    const offline = backend?.status === 'offline'
    return (
      <div className="flex flex-col items-center justify-center h-[60vh] text-center">
        <WifiOff className="h-8 w-8 text-[var(--text-muted)] mb-4" aria-hidden />
        <p className="text-xl font-semibold text-[var(--text-primary)] mb-2">
          {offline ? "Can't reach the analysis backend" : `Couldn't load ${ticker}`}
        </p>
        <p className="text-sm text-[var(--muted-foreground)] max-w-md mb-6">
          {offline
            ? 'The API server is not responding. Start it with `python run.py` — this page retries automatically once it is back.'
            : loadError.message}
        </p>
        <Button variant="secondary" onClick={() => load(ticker)} className="gap-1.5">
          <RotateCw className="h-3.5 w-3.5" aria-hidden /> Retry
        </Button>
      </div>
    )
  }

  // A first-time live run failed (nothing saved to fall back on).
  if (ticker && runFailed && !analysis && !loading && missingTicker !== ticker) {
    return (
      <div className="flex flex-col items-center justify-center h-[60vh]">
        <div className="w-full max-w-xl">
          <ErrorBanner title={`Analysis for ${ticker} failed`} message={error} onRetry={retryRun} />
        </div>
      </div>
    )
  }

  if (ticker && missingTicker === ticker && !analysis && !loading) {
    return (
      <div className="flex flex-col items-center justify-center h-[60vh] text-center">
        {runFailed && (
          <div className="w-full max-w-xl text-left">
            <ErrorBanner title={`Analysis for ${ticker} failed`} message={error} onRetry={retryRun} />
          </div>
        )}
        <p className="text-xl font-semibold text-[var(--text-primary)] mb-2">No saved analysis for {ticker} yet</p>
        <p className="text-sm text-[var(--muted-foreground)] max-w-md mb-6">
          A live run fans out to the data agents, then the synthesis agents. It takes about two minutes and uses your API credits.
        </p>
        {backend?.status === 'no-llm-key' ? (
          <p className="text-sm text-[var(--warning)] max-w-md">
            No API key is configured for the selected LLM provider, so live runs are disabled. Add one to <code>.env</code> and restart the backend.
          </p>
        ) : (
          !runFailed && <Button onClick={retryRun}>Run analysis for {ticker}</Button>
        )}
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
      {runFailed && (
        <ErrorBanner
          title={`Re-running ${ticker} failed — showing the last saved analysis`}
          message={error}
          onRetry={retryRun}
        />
      )}
      <KpiRow analysis={analysis} />
      <VerdictHero analysis={analysis} />
      <AnalysisTabs analysis={analysis} />
      <MetaFooter analysis={analysis} />
    </motion.div>
  )
}
