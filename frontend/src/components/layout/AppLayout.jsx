import { useState, useEffect, useCallback } from 'react'
import { Outlet, useNavigate } from 'react-router-dom'
import Header from './Header'
import Sidebar from './Sidebar'
import { useAnalysisContext } from '@/context/AnalysisContext'
import { useAnalysis } from '@/hooks/useAnalysis'
import { getUnacknowledgedCount } from '@/utils/api'

export default function AppLayout() {
  const [tickerInput, setTickerInput] = useState('')
  const [unacknowledgedCount, setUnacknowledgedCount] = useState(0)
  const [recentAnalyses, setRecentAnalyses] = useState([])
  const { analysis } = useAnalysisContext()
  const { runAnalysis } = useAnalysis()
  const navigate = useNavigate()

  // Fetch alert count
  useEffect(() => {
    getUnacknowledgedCount()
      .then((data) => setUnacknowledgedCount(data?.count || 0))
      .catch(() => {})
    const interval = setInterval(() => {
      getUnacknowledgedCount()
        .then((data) => setUnacknowledgedCount(data?.count || 0))
        .catch(() => {})
    }, 30000)
    return () => clearInterval(interval)
  }, [])

  // Track recent analyses
  useEffect(() => {
    if (analysis?.ticker && analysis?.recommendation) {
      setRecentAnalyses((prev) => {
        const filtered = prev.filter((a) => a.ticker !== analysis.ticker)
        return [
          { ticker: analysis.ticker, recommendation: analysis.recommendation },
          ...filtered,
        ].slice(0, 5)
      })
    }
  }, [analysis?.ticker, analysis?.recommendation])

  const handleAnalyze = useCallback(
    (e) => {
      e.preventDefault()
      const ticker = tickerInput.trim().toUpperCase()
      if (!ticker) return
      navigate(`/analysis/${ticker}`)
      runAnalysis(ticker)
    },
    [tickerInput, navigate, runAnalysis]
  )

  const handleSelectTicker = useCallback(
    (ticker) => {
      setTickerInput(ticker)
      navigate(`/analysis/${ticker}`)
      runAnalysis(ticker)
    },
    [navigate, runAnalysis]
  )

  return (
    <div className="h-screen overflow-hidden">
      <Header
        tickerInput={tickerInput}
        setTickerInput={setTickerInput}
        onAnalyze={handleAnalyze}
        unacknowledgedCount={unacknowledgedCount}
      />
      <Sidebar
        unacknowledgedCount={unacknowledgedCount}
        recentAnalyses={recentAnalyses}
        onSelectTicker={handleSelectTicker}
      />
      <main
        className="overflow-y-auto"
        style={{
          marginLeft: 'var(--sidebar-width)',
          marginTop: 'var(--header-height)',
          height: 'calc(100vh - var(--header-height))',
          padding: '24px',
        }}
      >
        <Outlet context={{ onSelectTicker: handleSelectTicker }} />
      </main>
    </div>
  )
}
