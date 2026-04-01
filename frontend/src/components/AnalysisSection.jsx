import { useState, forwardRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';

const STANCE_CONFIG = {
  bullish: { label: 'Bullish', className: 'badge-bullish' },
  bearish: { label: 'Bearish', className: 'badge-bearish' },
  neutral: { label: 'Neutral', className: 'badge-neutral' },
};

function MetricItem({ label, value, color }) {
  return (
    <div className="text-[0.75rem]">
      <span className="text-white/30">{label}</span>
      <span className="font-semibold tabular-nums ml-1.5" style={{ color: color || 'rgba(255,255,255,0.7)' }}>
        {value}
      </span>
    </div>
  );
}

const AnalysisSection = forwardRef(function AnalysisSection(
  { id, name, stance, stanceColor, summary, metrics, fullContent, dataSource, duration, children },
  ref
) {
  const [expanded, setExpanded] = useState(false);
  const config = STANCE_CONFIG[stance] || STANCE_CONFIG.neutral;

  return (
    <div
      ref={ref}
      id={id}
      className="rounded-[10px] p-5"
      style={{
        background: 'rgba(255,255,255,0.02)',
        border: '1px solid rgba(255,255,255,0.06)',
      }}
    >
      <div className="flex justify-between items-start mb-3">
        <div className="flex items-center gap-2.5">
          <div className="accent-bar" style={{ background: stanceColor || '#f5a524' }} />
          <span className="text-[0.95rem] font-semibold text-white/90">{name}</span>
          <span className={`text-[0.68rem] px-2 py-0.5 rounded font-medium ${config.className}`}>
            {config.label}
          </span>
        </div>
        <span className="text-[0.68rem] text-white/20">
          {dataSource}{duration != null ? ` · ${duration.toFixed(1)}s` : ''}
        </span>
      </div>

      {summary && (
        <div className="text-[0.88rem] text-white/65 leading-relaxed mb-3">{summary}</div>
      )}

      {metrics && metrics.length > 0 && (
        <div className="flex gap-6 mb-2.5">
          {metrics.map((m, i) => (
            <MetricItem key={i} label={m.label} value={m.value} color={m.color} />
          ))}
        </div>
      )}

      {(fullContent || children) && (
        <>
          <button
            onClick={() => setExpanded(!expanded)}
            className="text-[0.75rem] font-medium cursor-pointer border-none bg-transparent"
            style={{ color: 'rgba(0,111,238,0.7)' }}
            onMouseEnter={(e) => (e.target.style.color = '#006fee')}
            onMouseLeave={(e) => (e.target.style.color = 'rgba(0,111,238,0.7)')}
          >
            {expanded ? 'Hide details ▲' : 'Show full analysis ▼'}
          </button>
          <AnimatePresence>
            {expanded && (
              <motion.div
                initial={{ height: 0, opacity: 0 }}
                animate={{ height: 'auto', opacity: 1 }}
                exit={{ height: 0, opacity: 0 }}
                transition={{ duration: 0.2 }}
                className="overflow-hidden"
              >
                <div className="mt-3 pt-3" style={{ borderTop: '1px solid rgba(255,255,255,0.05)' }}>
                  {children || (
                    <div className="text-[0.82rem] text-white/55 leading-relaxed whitespace-pre-wrap">
                      {typeof fullContent === 'string' ? fullContent : JSON.stringify(fullContent, null, 2)}
                    </div>
                  )}
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </>
      )}
    </div>
  );
});

export default AnalysisSection;
