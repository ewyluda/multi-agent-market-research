import { useState } from 'react';
import { SearchIcon } from './Icons';

const STAGE_TEXT = {
  starting: 'Initializing...',
  gathering_data: 'Gathering data...',
  running_market: 'Market data...',
  running_fundamentals: 'Fundamentals...',
  running_news: 'Fetching news...',
  running_technical: 'Technical analysis...',
  running_options: 'Options flow...',
  running_macro: 'Macro environment...',
  analyzing_sentiment: 'Sentiment...',
  synthesizing: 'Synthesizing...',
  saving: 'Saving...',
  complete: 'Complete',
  error: 'Failed',
};

const AGENT_KEYS = ['market', 'fundamentals', 'technical', 'news', 'sentiment', 'macro', 'options'];

function AgentDots({ analysis, loading, stage }) {
  if (!loading && !analysis) return null;

  return (
    <div className="flex items-center gap-1.5 ml-auto">
      {loading && stage && stage !== 'complete' && (
        <span className="text-[0.7rem] text-white/30 mr-2">{STAGE_TEXT[stage] || stage}</span>
      )}
      {AGENT_KEYS.map((key) => {
        const result = analysis?.agent_results?.[key];
        let color = 'bg-white/10';
        if (result?.success) color = 'bg-[#17c964]';
        else if (result?.success === false) color = 'bg-[#f31260]';
        else if (loading) color = 'bg-[#006fee] animate-pulse';
        return <div key={key} className={`w-[7px] h-[7px] rounded-full ${color}`} title={key} />;
      })}
    </div>
  );
}

export default function SearchBar({ tickerInput, setTickerInput, onAnalyze, loading, analysis, stage }) {
  const handleSubmit = (e) => {
    e.preventDefault();
    if (tickerInput.trim() && !loading) {
      onAnalyze(e);
    }
  };

  return (
    <div
      className="sticky top-0 z-40 flex items-center gap-3 px-6 py-3"
      style={{
        background: 'rgba(9,9,11,0.85)',
        backdropFilter: 'blur(12px)',
        borderBottom: '1px solid rgba(255,255,255,0.05)',
      }}
    >
      <form onSubmit={handleSubmit} className="flex items-center gap-2">
        <div className="relative">
          <SearchIcon className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-white/25" />
          <input
            type="text"
            value={tickerInput}
            onChange={(e) => setTickerInput(e.target.value.toUpperCase())}
            placeholder="Enter ticker..."
            maxLength={5}
            disabled={loading}
            className="pl-9 pr-3 py-2 rounded-lg text-[0.85rem] text-white/80 placeholder:text-white/25 outline-none w-[200px]"
            style={{
              background: 'rgba(255,255,255,0.04)',
              border: '1px solid rgba(255,255,255,0.08)',
            }}
          />
        </div>
        <button
          type="submit"
          disabled={loading || !tickerInput.trim()}
          className="px-4 py-2 rounded-lg border-none text-[0.82rem] font-semibold text-white cursor-pointer disabled:opacity-40 disabled:cursor-not-allowed"
          style={{ background: '#006fee' }}
        >
          {loading ? 'Analyzing...' : 'Analyze'}
        </button>
      </form>
      <AgentDots analysis={analysis} loading={loading} stage={stage} />
    </div>
  );
}
