const AGENT_HEATMAP = [
  { key: 'market', label: 'MKT' },
  { key: 'fundamentals', label: 'FUN' },
  { key: 'technical', label: 'TCH' },
  { key: 'news', label: 'NWS' },
  { key: 'sentiment', label: 'SNT' },
  { key: 'macro', label: 'MAC' },
  { key: 'options', label: 'OPT' },
];

const REC_COLORS = {
  BUY: { text: '#17c964', gradFrom: 'rgba(23,201,100,0.06)', gradTo: 'rgba(23,201,100,0.01)', border: 'rgba(23,201,100,0.12)' },
  SELL: { text: '#f31260', gradFrom: 'rgba(243,18,96,0.06)', gradTo: 'rgba(243,18,96,0.01)', border: 'rgba(243,18,96,0.12)' },
  HOLD: { text: '#f5a524', gradFrom: 'rgba(245,165,36,0.06)', gradTo: 'rgba(245,165,36,0.01)', border: 'rgba(245,165,36,0.12)' },
};

const SIGNAL_COLORS = { bullish: '#17c964', bearish: '#f31260', neutral: '#f5a524' };

function getAgentStance(agentKey, agentResult) {
  if (!agentResult?.success || !agentResult?.data) return 'neutral';
  const d = agentResult.data;
  switch (agentKey) {
    case 'fundamentals': return (d.health_score > 60) ? 'bullish' : (d.health_score < 40) ? 'bearish' : 'neutral';
    case 'technical': return d.signals?.overall || 'neutral';
    case 'sentiment': return (d.overall_sentiment > 0.3) ? 'bullish' : (d.overall_sentiment < -0.3) ? 'bearish' : 'neutral';
    case 'market': {
      const trend = (d.trend || '').toLowerCase();
      return trend.includes('up') || trend.includes('bull') ? 'bullish' : trend.includes('down') || trend.includes('bear') ? 'bearish' : 'neutral';
    }
    case 'macro': return d.risk_environment === 'dovish' ? 'bullish' : d.risk_environment === 'hawkish' ? 'bearish' : 'neutral';
    case 'options': return d.overall_signal || 'neutral';
    case 'news': {
      const articles = d.articles || [];
      if (!articles.length) return 'neutral';
      const avg = articles.reduce((sum, a) => sum + (a.overall_sentiment_score ?? a.sentiment_score ?? 0), 0) / articles.length;
      return avg > 0.15 ? 'bullish' : avg < -0.15 ? 'bearish' : 'neutral';
    }
    default: return 'neutral';
  }
}

function getStanceColor(stance) {
  return SIGNAL_COLORS[stance] || SIGNAL_COLORS.neutral;
}

export default function ThesisCard({ analysis }) {
  if (!analysis) return null;

  const payload = analysis.analysis || analysis;
  const signal = payload.signal_contract_v2 || {};
  const agentResults = analysis.agent_results || payload.agent_results || {};
  const marketData = agentResults.market?.data || {};

  const recommendation = (signal.recommendation || payload.recommendation || 'HOLD').toUpperCase();
  const colors = REC_COLORS[recommendation] || REC_COLORS.HOLD;
  const ticker = analysis.ticker || '';
  const price = marketData.current_price;
  const changePct = marketData.price_change_1m?.change_pct;
  const isPositive = changePct > 0;

  const scenarios = payload.scenarios || signal.scenarios || {};
  const targetLow = scenarios.base?.price_target || signal.price_target_low;
  const targetHigh = scenarios.bull?.price_target || signal.price_target_high;
  const targetRange = targetLow && targetHigh ? `$${Math.round(targetLow)} – $${Math.round(targetHigh)}` : null;

  const thesis = payload.executive_summary || payload.synthesis || payload.summary || '';
  const signals = payload.key_factors || payload.key_findings || [];
  const topSignals = (Array.isArray(signals) ? signals : []).slice(0, 3);

  return (
    <div
      className="mx-6 mt-5 rounded-[14px] flex gap-7"
      style={{
        padding: '24px',
        background: `linear-gradient(135deg, ${colors.gradFrom}, ${colors.gradTo})`,
        border: `1px solid ${colors.border}`,
      }}
    >
      <div className="flex-shrink-0 w-[200px] pr-7" style={{ borderRight: '1px solid rgba(255,255,255,0.06)' }}>
        <div className="text-[0.65rem] uppercase tracking-[0.1em] text-white/35 mb-2">
          {ticker} · {price ? `$${price.toFixed(2)}` : '—'}{' '}
          {changePct != null && (
            <span style={{ color: isPositive ? '#17c964' : '#f31260' }}>
              {isPositive ? '+' : ''}{changePct.toFixed(1)}%
            </span>
          )}
        </div>
        <div className="text-[2.4rem] font-extrabold leading-none mb-1.5" style={{ color: colors.text }}>
          {recommendation}
        </div>
        {targetRange && <div className="text-[0.85rem] text-white/45 mb-3.5">{targetRange}</div>}
        <div className="flex gap-[3px] mb-1">
          {AGENT_HEATMAP.map(({ key }) => (
            <div key={key} className="heatmap-bar" style={{ background: getStanceColor(getAgentStance(key, agentResults[key])) }} />
          ))}
        </div>
        <div className="flex justify-between text-[0.55rem] text-white/20">
          {AGENT_HEATMAP.map(({ key, label }) => <span key={key}>{label}</span>)}
        </div>
      </div>

      <div className="flex-1">
        <div className="text-[1.05rem] font-medium text-white/85 leading-relaxed mb-4">
          {thesis || 'Analysis synthesis pending...'}
        </div>
        <div className="flex flex-col gap-1.5 text-[0.8rem] text-white/50">
          {topSignals.map((sig, i) => {
            const text = typeof sig === 'string' ? sig : sig.description || sig.text || sig.factor || '';
            const direction = typeof sig === 'object' ? (sig.direction || sig.impact || '') : '';
            const isUp = direction.toLowerCase?.().includes('positive') || direction.toLowerCase?.().includes('bullish');
            const isDown = direction.toLowerCase?.().includes('negative') || direction.toLowerCase?.().includes('bearish');
            return (
              <div key={i}>
                <span style={{ color: isUp ? '#17c964' : isDown ? '#f31260' : '#f5a524' }}>
                  {isUp ? '▲' : isDown ? '▼' : '●'}
                </span>{' '}
                {text}
              </div>
            );
          })}
          {topSignals.length === 0 && thesis && (
            <div className="text-white/30 text-[0.75rem]">Supporting signals will appear here</div>
          )}
        </div>
      </div>
    </div>
  );
}
