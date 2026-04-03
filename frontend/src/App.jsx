import { Routes, Route } from 'react-router-dom'
import { AnalysisProvider } from './context/AnalysisContext'
import AppLayout from './components/layout/AppLayout'
import AnalysisView from './components/analysis/AnalysisView'

// Import existing views from their current location (will be moved in Tasks 8-9)
import MacroPage from './components/MacroPage'
import HistoryView from './components/HistoryView'
import WatchlistView from './components/WatchlistView'
import PortfolioView from './components/PortfolioView'
import SchedulesView from './components/SchedulesView'
import AlertsView from './components/AlertsView'
import InflectionView from './components/InflectionView'

export default function App() {
  return (
    <AnalysisProvider>
      <Routes>
        <Route element={<AppLayout />}>
          <Route index element={<AnalysisView />} />
          <Route path="analysis/:ticker" element={<AnalysisView />} />
          <Route path="macro" element={<MacroPage />} />
          <Route path="history" element={<HistoryView />} />
          <Route path="watchlist" element={<WatchlistView />} />
          <Route path="portfolio" element={<PortfolioView />} />
          <Route path="schedules" element={<SchedulesView />} />
          <Route path="alerts" element={<AlertsView />} />
          <Route path="inflections" element={<InflectionView />} />
        </Route>
      </Routes>
    </AnalysisProvider>
  )
}
