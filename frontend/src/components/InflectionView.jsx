import { useState, useEffect } from 'react';
import { getWatchlists } from '../utils/api';
import InflectionHeatmap from './InflectionHeatmap';
import InflectionChart from './InflectionChart';
import InflectionFeed from './InflectionFeed';

const InflectionView = () => {
  const [watchlists, setWatchlists] = useState([]);
  const [activeWatchlistId, setActiveWatchlistId] = useState(null);
  const [selectedTicker, setSelectedTicker] = useState(null);

  useEffect(() => {
    getWatchlists()
      .then((wls) => {
        setWatchlists(wls);
        if (wls.length > 0 && !activeWatchlistId) setActiveWatchlistId(wls[0].id);
      })
      .catch(() => setWatchlists([]));
  }, []);

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center justify-between px-4 py-3 border-b border-zinc-800">
        <h2 className="text-sm font-medium text-zinc-200">Inflection Radar</h2>
        <select value={activeWatchlistId || ''} onChange={(e) => setActiveWatchlistId(Number(e.target.value))}
          className="bg-zinc-800 text-zinc-300 text-xs rounded px-2 py-1 border border-zinc-700">
          {watchlists.map((wl) => (<option key={wl.id} value={wl.id}>{wl.name}</option>))}
        </select>
      </div>
      <div className="flex flex-1 min-h-0">
        <div className="w-60 shrink-0 border-r border-zinc-800 overflow-y-auto p-2">
          <InflectionHeatmap watchlistId={activeWatchlistId} selectedTicker={selectedTicker} onSelectTicker={setSelectedTicker} />
        </div>
        <div className="flex-1 min-w-0">
          <InflectionChart ticker={selectedTicker} />
        </div>
      </div>
      <div className="h-48 shrink-0 border-t border-zinc-800 overflow-y-auto">
        <InflectionFeed watchlistId={activeWatchlistId} onSelectTicker={setSelectedTicker} />
      </div>
    </div>
  );
};

export default InflectionView;
