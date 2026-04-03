import { useParams } from 'react-router-dom'
import { useAnalysisContext } from '@/context/AnalysisContext'

export default function AnalysisView() {
  const { ticker } = useParams()
  const { analysis, loading } = useAnalysisContext()

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

  return (
    <div>
      <h1 className="text-xl font-semibold mb-4">
        {analysis?.ticker || ticker} Analysis
      </h1>
      <p className="text-[var(--muted-foreground)]">
        {loading ? 'Analyzing...' : 'Analysis complete — tabs coming in next task.'}
      </p>
    </div>
  )
}
