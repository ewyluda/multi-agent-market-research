/**
 * Analysis Context - Global state for current analysis
 */

import React, { createContext, useContext, useState } from 'react';

const AnalysisContext = createContext();

export const useAnalysisContext = () => {
  const context = useContext(AnalysisContext);
  if (!context) {
    throw new Error('useAnalysisContext must be used within AnalysisProvider');
  }
  return context;
};

export const AnalysisProvider = ({ children }) => {
  const [currentTicker, setCurrentTicker] = useState('');
  const [analysis, setAnalysis] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [progress, setProgress] = useState(0);
  const [stage, setStage] = useState('');

  const resetAnalysis = () => {
    setAnalysis(null);
    setError(null);
    setProgress(0);
    setStage('');
  };

  const value = {
    currentTicker,
    setCurrentTicker,
    analysis,
    setAnalysis,
    loading,
    setLoading,
    error,
    setError,
    progress,
    setProgress,
    stage,
    setStage,
    resetAnalysis,
  };

  return (
    <AnalysisContext.Provider value={value}>
      {children}
    </AnalysisContext.Provider>
  );
};

export default AnalysisContext;
