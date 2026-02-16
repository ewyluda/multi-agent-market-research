/**
 * PortfolioPanel - Manage singleton portfolio profile + holdings
 */

import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  getPortfolio,
  updatePortfolioProfile,
  createPortfolioHolding,
  updatePortfolioHolding,
  deletePortfolioHolding,
} from '../utils/api';
import {
  ArrowLeftIcon,
  BuildingIcon,
  LoadingSpinner,
  TrashIcon,
  CheckCircleIcon,
  XCircleIcon,
} from './Icons';

const DEFAULT_PROFILE = {
  name: 'Primary',
  base_currency: 'USD',
  max_position_pct: 0.1,
  max_sector_pct: 0.3,
  risk_budget_pct: 1.0,
};

const EMPTY_HOLDING = {
  ticker: '',
  shares: '',
  avg_cost: '',
  market_value: '',
  sector: '',
  beta: '',
};

const pct = (value) => `${((Number(value) || 0) * 100).toFixed(1)}%`;

const ConstraintStatus = ({ value, limit }) => {
  if (value <= limit) {
    return <span className="inline-flex items-center gap-1 text-[11px] text-success-400"><CheckCircleIcon className="w-3 h-3" />Within</span>;
  }
  return <span className="inline-flex items-center gap-1 text-[11px] text-danger-400"><XCircleIcon className="w-3 h-3" />Over</span>;
};

const PortfolioPanel = ({ onBack }) => {
  const [loading, setLoading] = useState(false);
  const [savingProfile, setSavingProfile] = useState(false);
  const [savingHolding, setSavingHolding] = useState(false);
  const [error, setError] = useState(null);

  const [portfolio, setPortfolio] = useState({ profile: DEFAULT_PROFILE, holdings: [], snapshot: null });
  const [profileForm, setProfileForm] = useState(DEFAULT_PROFILE);
  const [holdingForm, setHoldingForm] = useState(EMPTY_HOLDING);
  const [editingHoldingId, setEditingHoldingId] = useState(null);

  const loadPortfolio = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await getPortfolio();
      const profile = data?.profile || DEFAULT_PROFILE;
      setPortfolio({
        profile,
        holdings: data?.holdings || [],
        snapshot: data?.snapshot || null,
      });
      setProfileForm({
        name: profile.name || 'Primary',
        base_currency: (profile.base_currency || 'USD').toUpperCase(),
        max_position_pct: Number(profile.max_position_pct ?? 0.1),
        max_sector_pct: Number(profile.max_sector_pct ?? 0.3),
        risk_budget_pct: Number(profile.risk_budget_pct ?? 1.0),
      });
    } catch (err) {
      setError(err.response?.data?.detail || err.message || 'Failed to load portfolio');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadPortfolio();
  }, [loadPortfolio]);

  const sectorRows = useMemo(() => portfolio?.snapshot?.by_sector || [], [portfolio]);
  const holdingsRows = useMemo(() => {
    const snapshotRows = portfolio?.snapshot?.by_ticker;
    if (Array.isArray(snapshotRows) && snapshotRows.length > 0) {
      return snapshotRows;
    }
    return portfolio?.holdings || [];
  }, [portfolio]);

  const handleProfileSave = async (e) => {
    e.preventDefault();
    setSavingProfile(true);
    setError(null);
    try {
      await updatePortfolioProfile({
        name: profileForm.name,
        base_currency: profileForm.base_currency?.toUpperCase(),
        max_position_pct: Number(profileForm.max_position_pct),
        max_sector_pct: Number(profileForm.max_sector_pct),
        risk_budget_pct: Number(profileForm.risk_budget_pct),
      });
      await loadPortfolio();
    } catch (err) {
      setError(err.response?.data?.detail || err.message || 'Failed to update portfolio profile');
    } finally {
      setSavingProfile(false);
    }
  };

  const resetHoldingForm = () => {
    setHoldingForm(EMPTY_HOLDING);
    setEditingHoldingId(null);
  };

  const handleHoldingSubmit = async (e) => {
    e.preventDefault();
    if (!holdingForm.ticker.trim()) return;

    setSavingHolding(true);
    setError(null);
    const payload = {
      ticker: holdingForm.ticker.toUpperCase().trim(),
      shares: Number(holdingForm.shares),
      avg_cost: holdingForm.avg_cost === '' ? null : Number(holdingForm.avg_cost),
      market_value: Number(holdingForm.market_value),
      sector: holdingForm.sector || null,
      beta: holdingForm.beta === '' ? null : Number(holdingForm.beta),
    };

    try {
      if (editingHoldingId) {
        await updatePortfolioHolding(editingHoldingId, payload);
      } else {
        await createPortfolioHolding(payload);
      }
      resetHoldingForm();
      await loadPortfolio();
    } catch (err) {
      setError(err.response?.data?.detail || err.message || 'Failed to save holding');
    } finally {
      setSavingHolding(false);
    }
  };

  const startEditHolding = (holding) => {
    setEditingHoldingId(holding.id);
    setHoldingForm({
      ticker: holding.ticker || '',
      shares: String(holding.shares ?? ''),
      avg_cost: holding.avg_cost == null ? '' : String(holding.avg_cost),
      market_value: String(holding.market_value ?? ''),
      sector: holding.sector || '',
      beta: holding.beta == null ? '' : String(holding.beta),
    });
  };

  const handleDeleteHolding = async (holdingId) => {
    setError(null);
    try {
      await deletePortfolioHolding(holdingId);
      if (editingHoldingId === holdingId) resetHoldingForm();
      await loadPortfolio();
    } catch (err) {
      setError(err.response?.data?.detail || err.message || 'Failed to delete holding');
    }
  };

  return (
    <div className="animate-fade-in space-y-5">
      <div className="flex items-center justify-between">
        <div className="flex items-center space-x-3">
          <button
            onClick={onBack}
            className="p-2 rounded-lg border border-white/5 text-gray-400 hover:text-white hover:border-white/15 transition-all"
          >
            <ArrowLeftIcon className="w-4 h-4" />
          </button>
          <div className="flex items-center space-x-2">
            <BuildingIcon className="w-5 h-5 text-accent-blue" />
            <h2 className="text-lg font-bold tracking-tight">Portfolio</h2>
          </div>
        </div>
        {portfolio?.snapshot?.total_market_value != null && (
          <div className="text-xs text-gray-400">
            Total Market Value: <span className="font-mono text-white">${Number(portfolio.snapshot.total_market_value).toLocaleString()}</span>
          </div>
        )}
      </div>

      {loading ? (
        <div className="glass-card-elevated rounded-xl p-8 flex justify-center">
          <LoadingSpinner size={18} className="text-gray-500" />
        </div>
      ) : (
        <>
          <div className="grid grid-cols-1 xl:grid-cols-2 gap-5">
            <div className="glass-card-elevated rounded-xl p-5">
              <h3 className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-4">Profile</h3>
              <form onSubmit={handleProfileSave} className="space-y-3">
                <div className="grid grid-cols-2 gap-3">
                  <label className="text-xs text-gray-400">
                    Name
                    <input
                      type="text"
                      value={profileForm.name}
                      onChange={(e) => setProfileForm((prev) => ({ ...prev, name: e.target.value }))}
                      className="mt-1 w-full px-3 py-2 bg-dark-inset border border-dark-border rounded-lg text-sm focus:outline-none focus:border-primary/40"
                    />
                  </label>
                  <label className="text-xs text-gray-400">
                    Currency
                    <input
                      type="text"
                      value={profileForm.base_currency}
                      maxLength={3}
                      onChange={(e) => setProfileForm((prev) => ({ ...prev, base_currency: e.target.value.toUpperCase() }))}
                      className="mt-1 w-full px-3 py-2 bg-dark-inset border border-dark-border rounded-lg text-sm uppercase focus:outline-none focus:border-primary/40"
                    />
                  </label>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                  <label className="text-xs text-gray-400">
                    Max Position (%)
                    <input
                      type="number"
                      min="0"
                      max="100"
                      step="0.1"
                      value={(Number(profileForm.max_position_pct) * 100).toString()}
                      onChange={(e) => setProfileForm((prev) => ({ ...prev, max_position_pct: Number(e.target.value) / 100 }))}
                      className="mt-1 w-full px-3 py-2 bg-dark-inset border border-dark-border rounded-lg text-sm focus:outline-none focus:border-primary/40"
                    />
                  </label>
                  <label className="text-xs text-gray-400">
                    Max Sector (%)
                    <input
                      type="number"
                      min="0"
                      max="100"
                      step="0.1"
                      value={(Number(profileForm.max_sector_pct) * 100).toString()}
                      onChange={(e) => setProfileForm((prev) => ({ ...prev, max_sector_pct: Number(e.target.value) / 100 }))}
                      className="mt-1 w-full px-3 py-2 bg-dark-inset border border-dark-border rounded-lg text-sm focus:outline-none focus:border-primary/40"
                    />
                  </label>
                  <label className="text-xs text-gray-400">
                    Risk Budget (%)
                    <input
                      type="number"
                      min="0"
                      max="100"
                      step="0.1"
                      value={(Number(profileForm.risk_budget_pct) * 100).toString()}
                      onChange={(e) => setProfileForm((prev) => ({ ...prev, risk_budget_pct: Number(e.target.value) / 100 }))}
                      className="mt-1 w-full px-3 py-2 bg-dark-inset border border-dark-border rounded-lg text-sm focus:outline-none focus:border-primary/40"
                    />
                  </label>
                </div>

                <button
                  type="submit"
                  disabled={savingProfile}
                  className="inline-flex items-center gap-2 px-4 py-2 bg-primary/20 text-accent-blue rounded-lg text-sm font-medium hover:bg-primary/30 transition-all disabled:opacity-40"
                >
                  {savingProfile && <LoadingSpinner size={12} />}
                  Save Profile
                </button>
              </form>
            </div>

            <div className="glass-card-elevated rounded-xl p-5">
              <h3 className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-4">Exposure Summary</h3>
              <div className="space-y-2">
                {sectorRows.length === 0 ? (
                  <p className="text-sm text-gray-500">No holdings yet.</p>
                ) : (
                  sectorRows.map((row) => (
                    <div key={row.sector} className="space-y-1">
                      <div className="flex items-center justify-between text-xs">
                        <span className="text-gray-300">{row.sector}</span>
                        <span className="font-mono text-gray-400">{pct(row.exposure_pct)}</span>
                      </div>
                      <div className="h-2 bg-dark-inset rounded-full overflow-hidden">
                        <div className="h-full bg-accent-blue/70" style={{ width: `${Math.min(100, Number(row.exposure_pct || 0) * 100)}%` }} />
                      </div>
                    </div>
                  ))
                )}
              </div>
            </div>
          </div>

          <div className="glass-card-elevated rounded-xl p-5">
            <h3 className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-4">
              {editingHoldingId ? 'Edit Holding' : 'Add Holding'}
            </h3>
            <form onSubmit={handleHoldingSubmit} className="grid grid-cols-1 md:grid-cols-6 gap-3 items-end">
              <label className="text-xs text-gray-400 md:col-span-1">
                Ticker
                <input
                  type="text"
                  maxLength={5}
                  value={holdingForm.ticker}
                  onChange={(e) => setHoldingForm((prev) => ({ ...prev, ticker: e.target.value.toUpperCase() }))}
                  className="mt-1 w-full px-3 py-2 bg-dark-inset border border-dark-border rounded-lg text-sm uppercase focus:outline-none focus:border-primary/40"
                />
              </label>
              <label className="text-xs text-gray-400">
                Shares
                <input
                  type="number"
                  min="0"
                  step="0.0001"
                  value={holdingForm.shares}
                  onChange={(e) => setHoldingForm((prev) => ({ ...prev, shares: e.target.value }))}
                  className="mt-1 w-full px-3 py-2 bg-dark-inset border border-dark-border rounded-lg text-sm focus:outline-none focus:border-primary/40"
                />
              </label>
              <label className="text-xs text-gray-400">
                Avg Cost
                <input
                  type="number"
                  min="0"
                  step="0.01"
                  value={holdingForm.avg_cost}
                  onChange={(e) => setHoldingForm((prev) => ({ ...prev, avg_cost: e.target.value }))}
                  className="mt-1 w-full px-3 py-2 bg-dark-inset border border-dark-border rounded-lg text-sm focus:outline-none focus:border-primary/40"
                />
              </label>
              <label className="text-xs text-gray-400">
                Market Value
                <input
                  type="number"
                  min="0"
                  step="0.01"
                  value={holdingForm.market_value}
                  onChange={(e) => setHoldingForm((prev) => ({ ...prev, market_value: e.target.value }))}
                  className="mt-1 w-full px-3 py-2 bg-dark-inset border border-dark-border rounded-lg text-sm focus:outline-none focus:border-primary/40"
                />
              </label>
              <label className="text-xs text-gray-400">
                Sector
                <input
                  type="text"
                  value={holdingForm.sector}
                  onChange={(e) => setHoldingForm((prev) => ({ ...prev, sector: e.target.value }))}
                  className="mt-1 w-full px-3 py-2 bg-dark-inset border border-dark-border rounded-lg text-sm focus:outline-none focus:border-primary/40"
                />
              </label>
              <div className="flex gap-2 md:col-span-1">
                <button
                  type="submit"
                  disabled={savingHolding}
                  className="flex-1 px-3 py-2 bg-primary/20 text-accent-blue rounded-lg text-sm font-medium hover:bg-primary/30 transition-all disabled:opacity-40"
                >
                  {savingHolding ? 'Saving...' : editingHoldingId ? 'Update' : 'Add'}
                </button>
                {editingHoldingId && (
                  <button
                    type="button"
                    onClick={resetHoldingForm}
                    className="px-3 py-2 bg-dark-inset border border-dark-border text-gray-300 rounded-lg text-sm hover:border-white/20"
                  >
                    Cancel
                  </button>
                )}
              </div>
            </form>
          </div>

          <div className="glass-card-elevated rounded-xl p-5">
            <h3 className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-3">Holdings</h3>
            {holdingsRows.length === 0 ? (
              <p className="text-sm text-gray-500">No holdings added.</p>
            ) : (
              <div className="divide-y divide-white/[0.04]">
                {holdingsRows.map((holding) => {
                  const positionPct = Number(holding.position_pct || 0);
                  const sectorPct = Number(holding.sector_exposure_pct || 0);
                  return (
                    <div key={holding.id} className="py-3 grid grid-cols-1 lg:grid-cols-12 gap-3 items-center">
                      <div className="lg:col-span-2 font-mono font-semibold">{holding.ticker}</div>
                      <div className="lg:col-span-3 text-sm text-gray-400">
                        Shares: <span className="text-gray-200 font-mono">{Number(holding.shares).toFixed(2)}</span>
                        <br />
                        Value: <span className="text-gray-200 font-mono">${Number(holding.market_value).toLocaleString()}</span>
                      </div>
                      <div className="lg:col-span-4 text-xs text-gray-400 space-y-1">
                        <div className="flex items-center justify-between">
                          <span>Position {pct(positionPct)}</span>
                          <ConstraintStatus value={positionPct} limit={Number(portfolio.profile.max_position_pct || 0)} />
                        </div>
                        <div className="flex items-center justify-between">
                          <span>Sector {holding.sector || 'Unspecified'} {pct(sectorPct)}</span>
                          <ConstraintStatus value={sectorPct} limit={Number(portfolio.profile.max_sector_pct || 0)} />
                        </div>
                      </div>
                      <div className="lg:col-span-3 flex items-center justify-end gap-2">
                        <button
                          onClick={() => startEditHolding(holding)}
                          className="px-3 py-1.5 text-xs rounded-md border border-white/10 text-gray-300 hover:text-white hover:border-white/25"
                        >
                          Edit
                        </button>
                        <button
                          onClick={() => handleDeleteHolding(holding.id)}
                          className="p-1.5 rounded-md text-gray-600 hover:text-danger-400 hover:bg-danger/10 transition-all"
                          title="Delete holding"
                        >
                          <TrashIcon className="w-3.5 h-3.5" />
                        </button>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        </>
      )}

      {error && (
        <div className="p-3 bg-danger/10 border border-danger/30 rounded-lg text-danger-400 text-sm">
          {error}
        </div>
      )}
    </div>
  );
};

export default PortfolioPanel;
