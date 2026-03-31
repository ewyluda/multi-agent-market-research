/**
 * CouncilPanel — Investor Council qualitative analysis layer.
 *
 * Opt-in panel: user triggers the council run explicitly via "Convene Council".
 * Renders 5 primary investor cards (+ any "add voice" extras) in parallel,
 * each showing: stance, thesis health, qualitative analysis, and if-then scenarios.
 * Disagreements between investors are surfaced prominently as the most valuable signal.
 */

import React, { useState, useCallback, useEffect } from 'react';
import { motion as Motion, AnimatePresence } from 'framer-motion';
import {
  runCouncilAPI,
  getCouncilResultsAPI,
  upsertThesisCardAPI,
  getThesisCardAPI,
} from '../utils/api';

// ── Investor metadata ────────────────────────────────────────────────────────

const ALL_INVESTORS = {
  druckenmiller: { name: 'Stanley Druckenmiller', initials: 'SD', role: 'Macro conviction · timing', primary: true },
  ptj:           { name: 'Paul Tudor Jones',       initials: 'PTJ', role: 'Defense · pre-defined exits', primary: true },
  munger:        { name: 'Charlie Munger',         initials: 'CM', role: 'Inversion · moat quality', primary: true },
  dalio:         { name: 'Ray Dalio',              initials: 'RD', role: 'Macro regime · correlation', primary: true },
  marks:         { name: 'Howard Marks',           initials: 'HM', role: 'Cycle position · consensus', primary: true },
  buffett:       { name: 'Warren Buffett',         initials: 'WB', role: 'Economic moat · management', primary: false },
  graham:        { name: 'Benjamin Graham',        initials: 'BG', role: 'Margin of safety · value traps', primary: false },
  klarman:       { name: 'Seth Klarman',           initials: 'SK', role: 'Distressed assets · patience', primary: false },
  soros:         { name: 'George Soros',           initials: 'GS', role: 'Reflexivity · boom-bust cycles', primary: false },
  lynch:         { name: 'Peter Lynch',            initials: 'PL', role: 'Growth · PEG · consumer insight', primary: false },
  fisher:        { name: 'Philip Fisher',          initials: 'PF', role: 'Super-growth · scuttlebutt', primary: false },
  grantham:      { name: 'Jeremy Grantham',        initials: 'JG', role: 'Bubble detection · mean reversion', primary: false },
  ackman:        { name: 'Bill Ackman',            initials: 'BA', role: 'Activist value · free cash flow', primary: false },
  icahn:         { name: 'Carl Icahn',             initials: 'CI', role: 'Corporate governance · catalysts', primary: false },
  robertson:     { name: 'Julian Robertson',       initials: 'JR', role: 'Long/short pairs · fundamentals', primary: false },
  simons:        { name: 'Jim Simons',             initials: 'JS', role: 'Quant signals · pattern recognition', primary: false },
  greenblatt:    { name: 'Joel Greenblatt',        initials: 'JGL', role: 'ROIC · earnings yield · Magic Formula', primary: false },
  rogers:        { name: 'Jim Rogers',             initials: 'JRO', role: 'Commodity cycles · global macro', primary: false },
  templeton:     { name: 'John Templeton',         initials: 'JT', role: 'Maximum pessimism · global value', primary: false },
  neff:          { name: 'John Neff',              initials: 'JN', role: 'Low P/E contrarian · total return', primary: false },
  swensen:       { name: 'David Swensen',          initials: 'DS', role: 'Asset allocation · illiquidity premium', primary: false },
  bogle:         { name: 'John Bogle',             initials: 'JBO', role: 'Cost discipline · behavioral check', primary: false },
  li_lu:         { name: 'Li Lu',                  initials: 'LL', role: 'Emerging markets · management culture', primary: false },
  duan_yongping: { name: 'Duan Yongping',          initials: 'DY', role: 'Consumer brands · right biz/people/price', primary: false },
  livermore:     { name: 'Jesse Livermore',        initials: 'JL', role: 'Trend confirmation · pivotal levels', primary: false },
  gann:          { name: 'William Gann',           initials: 'WG', role: 'Time cycles · geometric price levels', primary: false },
};

const PRIMARY_KEYS = Object.keys(ALL_INVESTORS).filter((k) => ALL_INVESTORS[k].primary);

// ── Color helpers ────────────────────────────────────────────────────────────

const stanceConfig = {
  BULLISH:      { label: 'Bullish',      color: '#17c964', bg: 'rgba(23,201,100,0.10)', border: 'rgba(23,201,100,0.30)', dim: 'rgba(23,201,100,0.50)' },
  CAUTIOUS:     { label: 'Cautious',     color: '#f5a524', bg: 'rgba(245,165,36,0.10)', border: 'rgba(245,165,36,0.30)', dim: 'rgba(245,165,36,0.50)' },
  BEARISH:      { label: 'Bearish',      color: '#f31260', bg: 'rgba(243,18,96,0.10)',  border: 'rgba(243,18,96,0.30)',  dim: 'rgba(243,18,96,0.50)' },
  PASS:         { label: 'Pass',         color: '#52525b', bg: 'rgba(82,82,91,0.10)',   border: 'rgba(82,82,91,0.30)',   dim: 'rgba(82,82,91,0.50)' },
};

const healthConfig = {
  INTACT:       { label: 'Intact',       cls: 'text-success-400 bg-success/10 border-success/25' },
  WATCHING:     { label: 'Watching',     cls: 'text-warning-400 bg-warning/10 border-warning/25' },
  DETERIORATING:{ label: 'Deteriorating',cls: 'text-danger-400 bg-danger/20 border-danger/40' },
  BROKEN:       { label: 'Broken',       cls: 'text-danger-400 bg-danger/10 border-danger/25' },
  UNKNOWN:      { label: 'No thesis',    cls: 'text-zinc-500 bg-zinc-800/50 border-zinc-700/30' },
};

const scenarioTypeConfig = {
  macro:    { label: 'Macro',    cls: 'text-accent-cyan border-accent-cyan/30 bg-accent-cyan/8' },
  event:    { label: 'Event',    cls: 'text-accent-amber border-amber-500/30 bg-amber-500/8' },
  price:    { label: 'Price',    cls: 'text-accent-blue border-accent-blue/30 bg-accent-blue/8' },
  catalyst: { label: 'Catalyst', cls: 'text-accent-purple border-accent-purple/30 bg-accent-purple/8' },
};

// ── Sub-components ───────────────────────────────────────────────────────────

const StanceDot = ({ stance }) => {
  const cfg = stanceConfig[stance] || stanceConfig.PASS;
  return (
    <span
      className="inline-block w-2 h-2 rounded-full flex-shrink-0"
      style={{ backgroundColor: cfg.color, boxShadow: `0 0 6px ${cfg.dim}` }}
    />
  );
};

const StanceBadge = ({ stance }) => {
  const cfg = stanceConfig[stance] || stanceConfig.PASS;
  return (
    <span
      className="text-[11px] font-bold px-2.5 py-0.5 rounded-full tracking-wider uppercase"
      style={{ color: cfg.color, background: cfg.bg, border: `1px solid ${cfg.border}` }}
    >
      {cfg.label}
    </span>
  );
};

const HealthBadge = ({ health }) => {
  const cfg = healthConfig[health] || healthConfig.UNKNOWN;
  return (
    <span className={`text-[10px] font-semibold px-2 py-0.5 rounded border tracking-wider uppercase ${cfg.cls}`}>
      {cfg.label}
    </span>
  );
};

const InvestorAvatar = ({ investorKey, stance }) => {
  const meta = ALL_INVESTORS[investorKey] || {};
  const cfg = stanceConfig[stance] || stanceConfig.PASS;
  return (
    <div
      className="w-9 h-9 rounded-lg flex items-center justify-center text-[10px] font-bold flex-shrink-0 tracking-wide"
      style={{
        background: cfg.bg,
        border: `1px solid ${cfg.border}`,
        color: cfg.color,
        fontFamily: 'var(--font-mono)',
      }}
    >
      {meta.initials || investorKey.slice(0, 2).toUpperCase()}
    </div>
  );
};

const ScenarioPill = ({ scenario, idx }) => {
  const type = (scenario.type || 'event').toLowerCase();
  const typeCfg = scenarioTypeConfig[type] || scenarioTypeConfig.event;
  const convictionMap = { high: '●●●', medium: '●●○', low: '●○○' };
  const conviction = (scenario.conviction || 'medium').toLowerCase();

  return (
    <Motion.div
      initial={{ opacity: 0, x: -6 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ delay: idx * 0.06, duration: 0.2 }}
      className="rounded-lg border border-white/5 bg-dark-inset/60 p-3 space-y-1.5"
    >
      <div className="flex items-center gap-2">
        <span className={`text-[9px] font-bold px-1.5 py-0.5 rounded border uppercase tracking-widest ${typeCfg.cls}`}>
          {typeCfg.label}
        </span>
        <span className="text-[9px] text-gray-600 font-mono tracking-widest ml-auto" title={`Conviction: ${conviction}`}>
          {convictionMap[conviction] || '●●○'}
        </span>
      </div>
      <p className="text-[11px] text-gray-300 leading-relaxed">
        <span className="text-accent-amber font-semibold">{scenario.condition}</span>
        {' '}
        <span className="text-gray-400">{scenario.action}</span>
      </p>
    </Motion.div>
  );
};

const InvestorCard = ({ result, idx }) => {
  const [expanded, setExpanded] = useState(false);
  const meta = ALL_INVESTORS[result.investor] || {};
  const stance = result.stance || 'PASS';
  const cfg = stanceConfig[stance] || stanceConfig.PASS;
  const scenarios = result.if_then_scenarios || [];
  const observations = result.key_observations || [];

  return (
    <Motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: idx * 0.07, duration: 0.3, ease: [0.16, 1, 0.3, 1] }}
      className="glass-card-elevated rounded-xl overflow-hidden flex flex-col"
      style={{ borderLeft: `3px solid ${cfg.color}` }}
    >
      {/* Card header */}
      <div className="px-4 pt-4 pb-3 border-b border-white/5">
        <div className="flex items-start gap-3">
          <InvestorAvatar investorKey={result.investor} stance={stance} />
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 flex-wrap">
              <span className="text-sm font-semibold text-white truncate">{result.investor_name}</span>
              <StanceBadge stance={stance} />
            </div>
            <div className="flex items-center gap-2 mt-1 flex-wrap">
              <span className="text-[10px] text-gray-500 leading-none">{meta.role}</span>
              {result.thesis_health && result.thesis_health !== 'UNKNOWN' && (
                <>
                  <span className="text-gray-700 text-[10px]">·</span>
                  <HealthBadge health={result.thesis_health} />
                </>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Primary question answered */}
      {result.primary_question_answered && (
        <div className="px-4 py-2.5 border-b border-white/5">
          <p
            className="text-[11px] font-semibold leading-relaxed"
            style={{ color: cfg.color, opacity: 0.9 }}
          >
            {result.primary_question_answered}
          </p>
        </div>
      )}

      {/* Qualitative analysis */}
      <div className="px-4 py-3 flex-1">
        <p className="text-xs text-gray-300 leading-relaxed">
          {result.qualitative_analysis || (result.error ? `Error: ${result.error}` : '—')}
        </p>
      </div>

      {/* Key observations */}
      {observations.length > 0 && (
        <div className="px-4 pb-3 space-y-1">
          {observations.slice(0, 3).map((obs, i) => (
            <div key={i} className="flex items-start gap-2">
              <span className="text-[9px] mt-0.5 flex-shrink-0" style={{ color: cfg.dim }}>▸</span>
              <span className="text-[11px] text-gray-400 leading-relaxed">{obs}</span>
            </div>
          ))}
        </div>
      )}

      {/* Scenarios toggle */}
      {scenarios.length > 0 && (
        <div className="border-t border-white/5">
          <button
            onClick={() => setExpanded((p) => !p)}
            className="w-full flex items-center justify-between px-4 py-2.5 text-[11px] text-gray-500 hover:text-gray-300 transition-colors cursor-pointer"
          >
            <span className="font-semibold uppercase tracking-wider">
              {scenarios.length} If-Then Scenario{scenarios.length !== 1 ? 's' : ''}
            </span>
            <span
              className="transition-transform duration-200"
              style={{ transform: expanded ? 'rotate(180deg)' : 'rotate(0deg)' }}
            >
              ▾
            </span>
          </button>
          <AnimatePresence>
            {expanded && (
              <Motion.div
                initial={{ height: 0, opacity: 0 }}
                animate={{ height: 'auto', opacity: 1 }}
                exit={{ height: 0, opacity: 0 }}
                transition={{ duration: 0.22 }}
                className="overflow-hidden"
              >
                <div className="px-4 pb-4 space-y-2">
                  {scenarios.map((s, i) => (
                    <ScenarioPill key={i} scenario={s} idx={i} />
                  ))}
                </div>
              </Motion.div>
            )}
          </AnimatePresence>
        </div>
      )}

      {/* Disagreement flag */}
      {result.disagreement_flag && (
        <div className="px-4 py-2 border-t border-white/5">
          <p className="text-[10px] text-warning-400 leading-relaxed italic">{result.disagreement_flag}</p>
        </div>
      )}
    </Motion.div>
  );
};

const DisagreementBanner = ({ disagreements }) => {
  if (!disagreements || disagreements.length === 0) return null;
  return (
    <Motion.div
      initial={{ opacity: 0, y: -8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.25 }}
      className="rounded-xl border border-warning/30 bg-warning/5 px-4 py-3 flex items-start gap-3"
    >
      <span className="text-warning-400 text-sm flex-shrink-0 mt-0.5">⚡</span>
      <div className="space-y-1">
        <p className="text-xs font-semibold text-warning-400 uppercase tracking-wider">Council Disagreement Detected</p>
        {disagreements.map((d, i) => (
          <p key={i} className="text-xs text-gray-300 leading-relaxed">{d}</p>
        ))}
        <p className="text-[11px] text-gray-500 mt-1">
          Disagreement is the highest-value output. Pressure-test which assumption is load-bearing before acting.
        </p>
      </div>
    </Motion.div>
  );
};

const PlaybookSection = ({ results }) => {
  const allScenarios = [];
  results.forEach((r) => {
    (r.if_then_scenarios || []).forEach((s) => {
      allScenarios.push({ ...s, investor: r.investor_name });
    });
  });
  if (allScenarios.length === 0) return null;

  const grouped = allScenarios.reduce((acc, s) => {
    const type = (s.type || 'event').toLowerCase();
    if (!acc[type]) acc[type] = [];
    acc[type].push(s);
    return acc;
  }, {});

  const typeOrder = ['macro', 'catalyst', 'price', 'event'];
  const sortedTypes = [...new Set([...typeOrder, ...Object.keys(grouped)])].filter((t) => grouped[t]);

  return (
    <Motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3, delay: 0.2 }}
      className="glass-card-elevated rounded-xl overflow-hidden"
    >
      <div className="px-5 py-4 border-b border-white/5 flex items-center gap-2">
        <span className="text-[10px] font-bold uppercase tracking-widest text-gray-500">Position Playbook</span>
        <span className="text-[10px] text-gray-700">·</span>
        <span className="text-[10px] text-gray-600">
          {allScenarios.length} pre-committed conditional rules across {results.length} investors
        </span>
      </div>
      <div className="p-4 grid grid-cols-1 lg:grid-cols-2 xl:grid-cols-4 gap-4">
        {sortedTypes.map((type) => {
          const typeCfg = scenarioTypeConfig[type] || scenarioTypeConfig.event;
          return (
            <div key={type} className="space-y-2">
              <div className={`text-[9px] font-bold uppercase tracking-widest px-1.5 py-0.5 rounded border w-fit ${typeCfg.cls}`}>
                {typeCfg.label}
              </div>
              {grouped[type].map((s, i) => (
                <div key={i} className="rounded-lg bg-dark-inset/50 border border-white/5 p-3 space-y-1">
                  <div className="flex items-center gap-1.5">
                    <span className="text-[9px] font-mono text-gray-600">{s.investor?.split(' ').pop()}</span>
                  </div>
                  <p className="text-[11px] text-gray-300 leading-relaxed">
                    <span className="text-accent-amber font-medium">{s.condition}</span>
                    {' '}
                    <span className="text-gray-500">{s.action}</span>
                  </p>
                </div>
              ))}
            </div>
          );
        })}
      </div>
    </Motion.div>
  );
};

const ThesisCardForm = ({ initial, onSave, saving }) => {
  const [form, setForm] = useState({
    structural_thesis: initial?.structural_thesis || '',
    near_term_thesis: initial?.near_term_thesis || '',
    load_bearing_assumption: initial?.load_bearing_assumption || '',
    exit_conditions: initial?.exit_conditions || '',
    time_horizon: initial?.time_horizon || 'MEDIUM_TERM',
    sizing_class: initial?.sizing_class || 'TRADE',
  });

  const handleChange = (field) => (e) => setForm((p) => ({ ...p, [field]: e.target.value }));

  const inputCls =
    'w-full rounded-lg bg-dark-inset border border-white/8 px-3 py-2 text-xs text-gray-200 placeholder-gray-600 focus:outline-none focus:border-accent-blue/50 transition-colors resize-none';

  return (
    <Motion.div
      initial={{ opacity: 0, height: 0 }}
      animate={{ opacity: 1, height: 'auto' }}
      exit={{ opacity: 0, height: 0 }}
      transition={{ duration: 0.25 }}
      className="glass-card-elevated rounded-xl overflow-hidden"
    >
      <div className="px-5 py-4 border-b border-white/5">
        <p className="text-[10px] font-bold uppercase tracking-widest text-gray-500">Thesis Card</p>
        <p className="text-[11px] text-gray-600 mt-0.5">Context passed to each investor. Enables thesis health assessment.</p>
      </div>
      <div className="p-4 grid grid-cols-1 md:grid-cols-2 gap-3">
        <div className="md:col-span-2">
          <label className="text-[10px] font-semibold uppercase tracking-wider text-gray-500 block mb-1">Structural Thesis</label>
          <textarea className={inputCls} rows={2} placeholder="Why is this a great business long-term?" value={form.structural_thesis} onChange={handleChange('structural_thesis')} />
        </div>
        <div className="md:col-span-2">
          <label className="text-[10px] font-semibold uppercase tracking-wider text-gray-500 block mb-1">Near-Term Thesis</label>
          <textarea className={inputCls} rows={2} placeholder="Why now, sized this way?" value={form.near_term_thesis} onChange={handleChange('near_term_thesis')} />
        </div>
        <div className="md:col-span-2">
          <label className="text-[10px] font-semibold uppercase tracking-wider text-gray-500 block mb-1">Load-Bearing Assumption</label>
          <input className={inputCls} placeholder="The single thing that must remain true" value={form.load_bearing_assumption} onChange={handleChange('load_bearing_assumption')} />
        </div>
        <div className="md:col-span-2">
          <label className="text-[10px] font-semibold uppercase tracking-wider text-gray-500 block mb-1">Pre-Defined Exit Conditions</label>
          <input className={inputCls} placeholder="e.g. BTC -30% in 30 days AND ETH fails $3k retest" value={form.exit_conditions} onChange={handleChange('exit_conditions')} />
        </div>
        <div>
          <label className="text-[10px] font-semibold uppercase tracking-wider text-gray-500 block mb-1">Time Horizon</label>
          <select className={inputCls} value={form.time_horizon} onChange={handleChange('time_horizon')}>
            <option value="SHORT_TERM">Short-Term</option>
            <option value="MEDIUM_TERM">Medium-Term</option>
            <option value="LONG_TERM">Long-Term</option>
          </select>
        </div>
        <div>
          <label className="text-[10px] font-semibold uppercase tracking-wider text-gray-500 block mb-1">Position Type</label>
          <select className={inputCls} value={form.sizing_class} onChange={handleChange('sizing_class')}>
            <option value="TRADE">Near-Term Trade</option>
            <option value="COMPOUNDER">Long-Term Compounder</option>
            <option value="SPECULATIVE">Speculative</option>
          </select>
        </div>
        <div className="md:col-span-2 flex justify-end">
          <button
            onClick={() => onSave(form)}
            disabled={saving}
            className="text-xs font-semibold px-4 py-2 rounded-lg bg-accent-blue/15 border border-accent-blue/30 text-accent-cyan hover:bg-accent-blue/25 transition-colors disabled:opacity-40 cursor-pointer"
          >
            {saving ? 'Saving…' : 'Save Thesis Card'}
          </button>
        </div>
      </div>
    </Motion.div>
  );
};

const AddVoiceModal = ({ selected, onToggle, onClose }) => {
  const secondary = Object.entries(ALL_INVESTORS).filter(([, m]) => !m.primary);
  return (
    <Motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
      style={{ background: 'rgba(0,0,0,0.7)', backdropFilter: 'blur(4px)' }}
      onClick={onClose}
    >
      <Motion.div
        initial={{ scale: 0.94, opacity: 0 }}
        animate={{ scale: 1, opacity: 1 }}
        exit={{ scale: 0.94, opacity: 0 }}
        transition={{ duration: 0.18 }}
        onClick={(e) => e.stopPropagation()}
        className="glass-card-elevated rounded-xl w-full max-w-2xl overflow-hidden"
        style={{ border: '1px solid rgba(255,255,255,0.08)' }}
      >
        <div className="px-5 py-4 border-b border-white/5 flex items-center justify-between">
          <div>
            <p className="text-sm font-semibold text-white">Add Voice</p>
            <p className="text-[11px] text-gray-500 mt-0.5">Select up to 2 additional investors. Cap: 7 total.</p>
          </div>
          <button onClick={onClose} className="text-gray-600 hover:text-gray-300 transition-colors text-lg leading-none cursor-pointer">✕</button>
        </div>
        <div className="p-4 grid grid-cols-2 sm:grid-cols-3 gap-2 max-h-[60vh] overflow-y-auto">
          {secondary.map(([key, meta]) => {
            const isSelected = selected.has(key);
            const primaryCount = PRIMARY_KEYS.length;
            const totalSelected = selected.size;
            const wouldExceed = !isSelected && (totalSelected + primaryCount) >= 7;
            return (
              <button
                key={key}
                onClick={() => !wouldExceed && onToggle(key)}
                disabled={wouldExceed && !isSelected}
                className={`flex items-center gap-2.5 rounded-lg px-3 py-2.5 border text-left transition-all cursor-pointer ${
                  isSelected
                    ? 'border-accent-blue/40 bg-accent-blue/10'
                    : wouldExceed
                    ? 'border-white/5 opacity-40 cursor-not-allowed'
                    : 'border-white/8 hover:border-white/15 hover:bg-white/[0.03]'
                }`}
              >
                <div
                  className="w-7 h-7 rounded flex items-center justify-center text-[9px] font-bold flex-shrink-0"
                  style={{
                    background: isSelected ? 'rgba(0,111,238,0.2)' : 'rgba(255,255,255,0.05)',
                    color: isSelected ? '#338ef7' : '#71717a',
                    fontFamily: 'var(--font-mono)',
                  }}
                >
                  {meta.initials}
                </div>
                <div className="min-w-0">
                  <p className="text-[11px] font-medium text-gray-200 truncate">{meta.name.split(' ').slice(-1)[0]}</p>
                  <p className="text-[9px] text-gray-600 truncate">{meta.role.split('·')[0].trim()}</p>
                </div>
              </button>
            );
          })}
        </div>
        <div className="px-5 py-3 border-t border-white/5 flex justify-end">
          <button
            onClick={onClose}
            className="text-xs font-semibold px-4 py-2 rounded-lg bg-accent-blue/15 border border-accent-blue/30 text-accent-cyan hover:bg-accent-blue/25 transition-colors cursor-pointer"
          >
            Done
          </button>
        </div>
      </Motion.div>
    </Motion.div>
  );
};

// ── Main component ───────────────────────────────────────────────────────────

const CouncilPanel = ({ analysis, ticker }) => {
  const [councilData, setCouncilData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [showThesisForm, setShowThesisForm] = useState(false);
  const [thesisCard, setThesisCard] = useState(null);
  const [savingThesis, setSavingThesis] = useState(false);
  const [additionalInvestors, setAdditionalInvestors] = useState(new Set());
  const [showAddVoice, setShowAddVoice] = useState(false);

  const analysisId = analysis?.analysis_id || analysis?.id;

  // Load existing thesis card and any cached council results
  useEffect(() => {
    if (!ticker) return;
    getThesisCardAPI(ticker)
      .then((data) => { if (data?.thesis_card) setThesisCard(data.thesis_card); })
      .catch(() => {});
    getCouncilResultsAPI(ticker)
      .then((data) => { if (data?.results?.length) setCouncilData(data); })
      .catch(() => {});
  }, [ticker]);

  const handleRunCouncil = useCallback(async () => {
    if (!ticker) return;
    setLoading(true);
    setError(null);
    try {
      const allKeys = [...PRIMARY_KEYS, ...Array.from(additionalInvestors)];
      const data = await runCouncilAPI(ticker, allKeys.join(','), analysisId);
      setCouncilData(data);
    } catch (err) {
      setError(err?.response?.data?.detail || err.message || 'Council run failed');
    } finally {
      setLoading(false);
    }
  }, [ticker, additionalInvestors, analysisId]);

  const handleSaveThesis = useCallback(async (formData) => {
    if (!ticker) return;
    setSavingThesis(true);
    try {
      const data = await upsertThesisCardAPI(ticker, formData);
      if (data?.thesis_card) setThesisCard(data.thesis_card);
      setShowThesisForm(false);
    } catch (err) {
      console.error('Thesis card save failed:', err);
    } finally {
      setSavingThesis(false);
    }
  }, [ticker]);

  const toggleAdditional = useCallback((key) => {
    setAdditionalInvestors((prev) => {
      const next = new Set(prev);
      next.has(key) ? next.delete(key) : next.add(key);
      return next;
    });
  }, []);

  const results = councilData?.results || [];
  const disagreements = councilData?.disagreements || [];
  const hasResults = results.length > 0;
  const hasAnalysis = !!analysisId;

  // Stance summary for header
  const stanceCounts = results.reduce((acc, r) => {
    if (r.stance && r.stance !== 'PASS') acc[r.stance] = (acc[r.stance] || 0) + 1;
    return acc;
  }, {});

  return (
    <div className="space-y-4">

      {/* Header bar */}
      <div className="flex items-center gap-3 flex-wrap">
        <div className="flex-1 flex items-center gap-3 flex-wrap">
          <p className="text-[10px] font-bold uppercase tracking-widest text-gray-500">Investor Council</p>

          {/* Stance summary pills */}
          {hasResults && (
            <div className="flex items-center gap-1.5">
              {Object.entries(stanceCounts).map(([stance, count]) => {
                const cfg = stanceConfig[stance] || stanceConfig.PASS;
                return (
                  <span
                    key={stance}
                    className="text-[10px] font-semibold px-2 py-0.5 rounded-full"
                    style={{ color: cfg.color, background: cfg.bg, border: `1px solid ${cfg.border}` }}
                  >
                    {count} {cfg.label}
                  </span>
                );
              })}
            </div>
          )}

          {/* Thesis card toggle */}
          <button
            onClick={() => setShowThesisForm((p) => !p)}
            className="text-[11px] font-medium px-3 py-1.5 rounded-lg border border-white/8 text-gray-400 hover:text-gray-200 hover:border-white/15 transition-colors cursor-pointer flex items-center gap-1.5"
          >
            {thesisCard ? '✓ Thesis Card' : '+ Add Thesis'}
            {showThesisForm ? ' ▴' : ' ▾'}
          </button>

          {/* Add voice */}
          <button
            onClick={() => setShowAddVoice(true)}
            className="text-[11px] font-medium px-3 py-1.5 rounded-lg border border-white/8 text-gray-400 hover:text-gray-200 hover:border-white/15 transition-colors cursor-pointer flex items-center gap-1.5"
          >
            + Add Voice
            {additionalInvestors.size > 0 && (
              <span className="text-[10px] font-bold text-accent-cyan">({additionalInvestors.size})</span>
            )}
          </button>
        </div>

        {/* Run Council button */}
        <button
          onClick={handleRunCouncil}
          disabled={loading || !hasAnalysis}
          className={`flex items-center gap-2 text-xs font-bold px-4 py-2 rounded-lg transition-all cursor-pointer ${
            hasAnalysis
              ? 'bg-accent-blue/15 border border-accent-blue/35 text-accent-cyan hover:bg-accent-blue/25'
              : 'bg-white/5 border border-white/8 text-gray-600 cursor-not-allowed'
          } ${loading ? 'opacity-70' : ''}`}
          title={!hasAnalysis ? 'Run an analysis first to provide market data context' : ''}
        >
          {loading ? (
            <>
              <span className="w-3 h-3 border border-accent-blue/60 border-t-accent-cyan rounded-full animate-spin" />
              Convening…
            </>
          ) : (
            <>
              <span>◈</span>
              Convene Council
            </>
          )}
        </button>
      </div>

      {/* Thesis card form */}
      <AnimatePresence>
        {showThesisForm && (
          <ThesisCardForm
            initial={thesisCard}
            onSave={handleSaveThesis}
            saving={savingThesis}
          />
        )}
      </AnimatePresence>

      {/* Error */}
      {error && (
        <div className="rounded-xl border border-danger/30 bg-danger/5 px-4 py-3 text-xs text-danger-400">
          {error}
        </div>
      )}

      {/* No analysis warning */}
      {!hasAnalysis && !loading && (
        <div className="glass-card-elevated rounded-xl px-5 py-8 text-center">
          <p className="text-sm font-semibold text-gray-400 mb-1">No analysis data yet</p>
          <p className="text-xs text-gray-600">Run an analysis for {ticker || 'this ticker'} first, then convene the council.</p>
        </div>
      )}

      {/* Disagreement banner */}
      <AnimatePresence>
        {hasResults && <DisagreementBanner disagreements={disagreements} />}
      </AnimatePresence>

      {/* Loading skeleton */}
      {loading && (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5 gap-3">
          {[...Array(PRIMARY_KEYS.length + additionalInvestors.size)].map((_, i) => (
            <div key={i} className="glass-card-elevated rounded-xl p-4 space-y-3 animate-pulse" style={{ animationDelay: `${i * 80}ms` }}>
              <div className="flex items-center gap-3">
                <div className="w-9 h-9 rounded-lg bg-white/5" />
                <div className="flex-1 space-y-1.5">
                  <div className="h-3 bg-white/5 rounded w-3/4" />
                  <div className="h-2 bg-white/5 rounded w-1/2" />
                </div>
              </div>
              <div className="space-y-2">
                <div className="h-2 bg-white/5 rounded" />
                <div className="h-2 bg-white/5 rounded w-4/5" />
                <div className="h-2 bg-white/5 rounded w-3/5" />
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Investor cards grid */}
      {!loading && hasResults && (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5 gap-3">
          {results.map((result, i) => (
            <InvestorCard key={result.investor} result={result} idx={i} />
          ))}
        </div>
      )}

      {/* Position Playbook */}
      {!loading && hasResults && <PlaybookSection results={results} />}

      {/* Add Voice modal */}
      <AnimatePresence>
        {showAddVoice && (
          <AddVoiceModal
            selected={additionalInvestors}
            onToggle={toggleAdditional}
            onClose={() => setShowAddVoice(false)}
          />
        )}
      </AnimatePresence>
    </div>
  );
};

export default CouncilPanel;
