/**
 * Main App Component
 */

import React from 'react';
import { AnalysisProvider } from './context/AnalysisContext';
import Dashboard from './components/Dashboard';

function App() {
  return (
    <AnalysisProvider>
      <Dashboard />
    </AnalysisProvider>
  );
}

export default App;
