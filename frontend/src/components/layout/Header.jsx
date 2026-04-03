import { Search, Bell, Settings, Loader2 } from 'lucide-react'
import { Input } from '@/components/ui/input'
import { Button } from '@/components/ui/button'
import { useAnalysisContext } from '@/context/AnalysisContext'

const AGENT_KEYS = ['market', 'fundamentals', 'technical', 'news', 'sentiment', 'macro', 'options']

const STAGE_LABELS = {
  initializing: 'Starting...',
  running_market: 'Market data',
  running_fundamentals: 'Fundamentals',
  running_technical: 'Technicals',
  running_news: 'News',
  running_sentiment: 'Sentiment',
  running_macro: 'Macro',
  running_options: 'Options',
  running_solution: 'Synthesizing',
  running_thesis: 'Thesis',
  completed: 'Complete',
}

export default function Header({ tickerInput, setTickerInput, onAnalyze, unacknowledgedCount }) {
  const { loading, stage, progress, analysis } = useAnalysisContext()

  return (
    <header
      className="fixed top-0 left-0 right-0 z-40 flex items-center gap-4 px-4 border-b border-[var(--border)]"
      style={{ height: 'var(--header-height)', backgroundColor: 'var(--header-bg)' }}
    >
      {/* Logo */}
      <div className="flex items-center gap-2 w-[180px] shrink-0">
        <div className="w-8 h-8 rounded-lg bg-[var(--primary)] flex items-center justify-center">
          <span className="text-black font-bold text-sm">MR</span>
        </div>
        <span className="font-semibold text-sm text-[var(--text-primary)]">Market Research</span>
      </div>

      {/* Search bar */}
      <form onSubmit={onAnalyze} className="flex-1 max-w-md mx-auto flex items-center gap-2">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-[var(--muted-foreground)]" />
          <Input
            value={tickerInput}
            onChange={(e) => setTickerInput(e.target.value.toUpperCase().slice(0, 5))}
            placeholder="Search ticker..."
            className="pl-9 h-9 bg-[var(--secondary)] border-[var(--border)] font-data"
            disabled={loading}
          />
        </div>
        <Button type="submit" size="sm" disabled={loading || !tickerInput.trim()}>
          {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : 'Analyze'}
        </Button>
      </form>

      {/* Agent progress dots */}
      {loading && (
        <div className="flex items-center gap-3 shrink-0">
          <div className="flex items-center gap-1">
            {AGENT_KEYS.map((key) => {
              const agentResult = analysis?.agent_results?.[key]
              let color = 'rgba(255,255,255,0.15)'
              if (agentResult?.success) color = 'var(--success)'
              else if (agentResult?.success === false) color = 'var(--danger)'
              else if (stage?.includes(key)) color = 'var(--primary)'
              return (
                <div
                  key={key}
                  className="w-1.5 h-1.5 rounded-full transition-colors duration-300"
                  style={{ backgroundColor: color }}
                />
              )
            })}
          </div>
          <span className="text-xs text-[var(--muted-foreground)]">
            {STAGE_LABELS[stage] || stage}
          </span>
        </div>
      )}

      {/* Right actions */}
      <div className="flex items-center gap-1 shrink-0">
        <Button variant="ghost" size="icon" className="relative">
          <Bell className="h-4 w-4" />
          {unacknowledgedCount > 0 && (
            <span className="absolute -top-0.5 -right-0.5 w-4 h-4 rounded-full bg-[var(--danger)] text-[10px] font-bold flex items-center justify-center text-white">
              {unacknowledgedCount > 9 ? '9+' : unacknowledgedCount}
            </span>
          )}
        </Button>
        <Button variant="ghost" size="icon">
          <Settings className="h-4 w-4" />
        </Button>
      </div>

      {/* Progress bar */}
      {loading && progress > 0 && (
        <div
          className="absolute bottom-0 left-0 h-[2px] transition-all duration-300"
          style={{
            width: `${progress}%`,
            background: `linear-gradient(90deg, var(--primary), var(--success))`,
          }}
        />
      )}
    </header>
  )
}
