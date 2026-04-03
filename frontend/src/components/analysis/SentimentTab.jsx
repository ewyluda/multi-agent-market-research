import NewsFeed from '@/components/NewsFeed'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'

function SentimentBreakdown({ sentiment }) {
  if (!sentiment) return null
  const factors = sentiment.factors || sentiment.factor_scores || []
  const overall = sentiment.overall_score ?? sentiment.composite_score
  const analysisText = sentiment.analysis || sentiment.summary

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <CardTitle className="text-base">Sentiment Analysis</CardTitle>
          {overall != null && (
            <Badge variant={overall > 0.3 ? 'success' : overall < -0.3 ? 'danger' : 'warning'}>
              {overall > 0 ? '+' : ''}{overall.toFixed(2)}
            </Badge>
          )}
        </div>
      </CardHeader>
      <CardContent>
        {analysisText && <p className="text-sm text-[var(--text-secondary)] mb-4">{analysisText}</p>}
        {factors.length > 0 && (
          <div className="space-y-3">
            {factors.map((factor, i) => (
              <div key={i} className="flex items-center justify-between">
                <span className="text-sm text-[var(--text-secondary)]">{factor.name || factor.factor}</span>
                <div className="flex items-center gap-2">
                  <div className="w-24 h-1.5 rounded-full bg-[var(--muted)] overflow-hidden">
                    <div className="h-full rounded-full transition-all" style={{
                      width: `${Math.abs((factor.score || factor.weight || 0) * 100)}%`,
                      backgroundColor: (factor.score || 0) > 0 ? 'var(--success)' : 'var(--danger)',
                    }} />
                  </div>
                  <span className="font-data text-xs w-10 text-right text-[var(--text-muted)]">
                    {(factor.score || factor.weight || 0).toFixed(2)}
                  </span>
                </div>
              </div>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  )
}

function MacroSummary({ macro }) {
  if (!macro) return null
  const indicators = macro.indicators || []
  const summary = macro.analysis || macro.summary

  return (
    <Card>
      <CardHeader><CardTitle className="text-base">Macro Environment</CardTitle></CardHeader>
      <CardContent>
        {summary && <p className="text-sm text-[var(--text-secondary)] mb-4">{summary}</p>}
        {indicators.length > 0 && (
          <div className="grid grid-cols-2 gap-3">
            {indicators.map((ind, i) => (
              <div key={i} className="flex justify-between items-center py-1.5 border-b border-[var(--border)] last:border-0">
                <span className="text-xs text-[var(--text-muted)]">{ind.name}</span>
                <span className="font-data text-sm">{ind.value}</span>
              </div>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  )
}

export default function SentimentTab({ analysis }) {
  const sentiment = analysis?.agent_results?.sentiment?.data
  const macro = analysis?.agent_results?.macro?.data

  return (
    <div className="space-y-6">
      <SentimentBreakdown sentiment={sentiment} />
      <NewsFeed analysis={analysis} />
      <MacroSummary macro={macro} />
    </div>
  )
}
