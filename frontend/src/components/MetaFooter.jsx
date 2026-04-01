import { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';

function DiagnosticsSlideOver({ analysis, onClose }) {
  const payload = analysis?.analysis || analysis || {};
  const agentResults = analysis?.agent_results || payload?.agent_results || {};
  const diagnostics = payload.diagnostics || {};
  const disagreement = diagnostics.disagreement || {};
  const dataQuality = diagnostics.data_quality || {};

  return (
    <>
      <motion.div
        className="slide-over-backdrop"
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        onClick={onClose}
      />
      <motion.div
        className="slide-over-panel"
        initial={{ x: '100%' }}
        animate={{ x: 0 }}
        exit={{ x: '100%' }}
        transition={{ type: 'spring', damping: 30, stiffness: 300 }}
      >
        <div className="flex justify-between items-center mb-6">
          <h3 className="text-[1rem] font-semibold text-white/90">Diagnostics</h3>
          <button onClick={onClose} className="text-white/40 hover:text-white/70 text-lg bg-transparent border-none cursor-pointer">✕</button>
        </div>

        <div className="mb-6">
          <h4 className="text-[0.8rem] font-semibold text-white/60 mb-3">Agent Performance</h4>
          <div className="flex flex-col gap-1.5">
            {Object.entries(agentResults).map(([key, result]) => (
              <div key={key} className="flex items-center justify-between py-1.5 px-3 rounded-md" style={{ background: 'rgba(255,255,255,0.02)' }}>
                <div className="flex items-center gap-2">
                  <div className="w-1.5 h-1.5 rounded-full" style={{ background: result?.success ? '#17c964' : '#f31260' }} />
                  <span className="text-[0.78rem] text-white/70 capitalize">{key}</span>
                </div>
                <span className="text-[0.72rem] text-white/40 tabular-nums">
                  {result?.duration_seconds != null ? `${result.duration_seconds.toFixed(1)}s` : '—'}
                </span>
              </div>
            ))}
          </div>
        </div>

        {dataQuality.quality_level && (
          <div className="mb-6">
            <h4 className="text-[0.8rem] font-semibold text-white/60 mb-3">Data Quality</h4>
            <div className="flex gap-4 text-[0.75rem]">
              <div><span className="text-white/30">Level</span>{' '}<span className="text-white/70 font-medium capitalize">{dataQuality.quality_level}</span></div>
              <div><span className="text-white/30">Success Rate</span>{' '}<span className="text-white/70 font-medium">{((dataQuality.agent_success_rate || 0) * 100).toFixed(0)}%</span></div>
            </div>
            {dataQuality.warnings?.length > 0 && (
              <div className="mt-2 flex flex-col gap-1">
                {dataQuality.warnings.map((w, i) => (
                  <div key={i} className="text-[0.72rem] text-[#f5a524]/70">⚠ {w}</div>
                ))}
              </div>
            )}
          </div>
        )}

        {disagreement.is_conflicted && (
          <div className="mb-6">
            <h4 className="text-[0.8rem] font-semibold text-white/60 mb-3">Signal Disagreement</h4>
            <div className="flex gap-3 text-[0.75rem] mb-2">
              <span className="text-[#17c964]">▲ {disagreement.bullish_count || 0} bullish</span>
              <span className="text-[#f5a524]">● {disagreement.neutral_count || 0} neutral</span>
              <span className="text-[#f31260]">▼ {disagreement.bearish_count || 0} bearish</span>
            </div>
            {disagreement.agent_directions && (
              <div className="flex flex-wrap gap-2">
                {Object.entries(disagreement.agent_directions).map(([agent, direction]) => (
                  <span key={agent} className="text-[0.68rem] px-2 py-0.5 rounded text-white/50" style={{ background: 'rgba(255,255,255,0.03)' }}>
                    {agent}: <span className="capitalize font-medium">{direction}</span>
                  </span>
                ))}
              </div>
            )}
          </div>
        )}

        {payload.guardrail_warnings?.length > 0 && (
          <div className="mb-6">
            <h4 className="text-[0.8rem] font-semibold text-white/60 mb-3">Guardrail Warnings</h4>
            {payload.guardrail_warnings.map((w, i) => (
              <div key={i} className="text-[0.72rem] text-[#f5a524]/70 mb-1">⚠ {w}</div>
            ))}
          </div>
        )}
      </motion.div>
    </>
  );
}

export default function MetaFooter({ analysis }) {
  const [showDiagnostics, setShowDiagnostics] = useState(false);
  if (!analysis) return null;

  const timestamp = analysis.timestamp;
  const agentResults = analysis.agent_results || analysis.analysis?.agent_results || {};
  const agentCount = Object.keys(agentResults).length;
  const successCount = Object.values(agentResults).filter((r) => r?.success).length;
  const totalDuration = Object.values(agentResults).reduce((sum, r) => sum + (r?.duration_seconds || 0), 0);

  const formatDate = (ts) => {
    if (!ts) return '—';
    const d = new Date(ts);
    return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' }) +
      ' ' + d.toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' });
  };

  return (
    <>
      <div className="mx-6 mb-6 px-5 py-4 rounded-[10px] flex items-center gap-6"
        style={{ background: 'rgba(255,255,255,0.015)', border: '1px solid rgba(255,255,255,0.04)' }}>
        <span className="text-[0.72rem] text-white/30">Analyzed <span className="text-white/50 font-medium">{formatDate(timestamp)}</span></span>
        <span className="text-[0.72rem] text-white/30">Duration <span className="text-white/50 font-medium">{totalDuration.toFixed(1)}s</span></span>
        <span className="text-[0.72rem] text-white/30">Agents <span className="text-white/50 font-medium">{successCount}/{agentCount} succeeded</span></span>
        <button onClick={() => setShowDiagnostics(true)} className="ml-auto text-[0.72rem] font-medium bg-transparent border-none cursor-pointer"
          style={{ color: 'rgba(0,111,238,0.5)' }}
          onMouseEnter={(e) => (e.target.style.color = '#006fee')}
          onMouseLeave={(e) => (e.target.style.color = 'rgba(0,111,238,0.5)')}>
          View Diagnostics →
        </button>
      </div>
      <AnimatePresence>
        {showDiagnostics && <DiagnosticsSlideOver analysis={analysis} onClose={() => setShowDiagnostics(false)} />}
      </AnimatePresence>
    </>
  );
}
