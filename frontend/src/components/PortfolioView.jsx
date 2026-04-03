/**
 * PortfolioView - Full-page portfolio management with summary strip + holdings table
 */

import React, { useState, useEffect, useCallback } from 'react';
import {
  getPortfolio,
  updatePortfolioProfile,
  createPortfolioHolding,
  updatePortfolioHolding,
  deletePortfolioHolding,
} from '../utils/api';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import {
  Table,
  TableHeader,
  TableBody,
  TableRow,
  TableCell,
  TableHead,
} from '@/components/ui/table';

const DEFAULT_PROFILE = {
  name: 'Primary',
  base_currency: 'USD',
  max_position_pct: 0.1,
  max_sector_pct: 0.3,
  risk_budget_pct: 1.0,
  target_portfolio_beta: 1.0,
  max_turnover_pct: 0.15,
  default_transaction_cost_bps: 10,
};

const EMPTY_HOLDING = {
  ticker: '',
  shares: '',
  avg_cost: '',
  market_value: '',
  sector: '',
  beta: '',
};

const fmtCurrency = (val) => {
  if (val == null || isNaN(Number(val))) return '—';
  return `$${Number(val).toLocaleString(undefined, { maximumFractionDigits: 2 })}`;
};

const fmtPct = (val) => {
  if (val == null || isNaN(Number(val))) return '—';
  return `${(Number(val) * 100).toFixed(1)}%`;
};

/* ──────── Summary strip ──────── */
const SummaryStrip = ({ snapshot }) => {
  if (!snapshot) return null;
  const totalVal = snapshot.total_market_value;
  const holdingsCount = snapshot.by_ticker?.length || 0;
  const topSector = snapshot.by_sector?.[0]?.sector;

  return (
    <div className="grid grid-cols-3 gap-3 mb-6">
      {[
        { label: 'Total Value', value: fmtCurrency(totalVal) },
        { label: 'Holdings', value: holdingsCount.toString() },
        { label: 'Top Sector', value: topSector || '—' },
      ].map(({ label, value }) => (
        <Card key={label}>
          <CardContent className="pt-4 pb-3">
            <div className="text-[0.65rem] uppercase tracking-widest mb-1.5" style={{ color: 'var(--text-muted)' }}>
              {label}
            </div>
            <div className="text-[1.1rem] font-bold font-data" style={{ color: 'var(--text-primary)' }}>
              {value}
            </div>
          </CardContent>
        </Card>
      ))}
    </div>
  );
};

/* ──────── Holdings table row ──────── */
const HoldingRow = ({ holding, onEdit, onDelete, onSelectTicker }) => {
  const returnPct = holding.avg_cost != null && holding.market_value != null && holding.shares != null
    ? ((Number(holding.market_value) / Number(holding.shares) - Number(holding.avg_cost)) / Number(holding.avg_cost)) * 100
    : null;

  return (
    <TableRow>
      <TableCell>
        <button
          onClick={() => onSelectTicker?.(holding.ticker)}
          className="font-data font-bold text-[0.85rem] p-0 bg-transparent border-none cursor-pointer transition-colors"
          style={{ color: 'var(--primary)' }}
        >
          {holding.ticker}
        </button>
      </TableCell>
      <TableCell className="font-data text-[0.82rem]" style={{ color: 'var(--text-secondary)' }}>
        {Number(holding.shares || 0).toLocaleString(undefined, { maximumFractionDigits: 4 })}
      </TableCell>
      <TableCell className="font-data text-[0.82rem]" style={{ color: 'var(--text-secondary)' }}>
        {fmtCurrency(holding.market_value)}
      </TableCell>
      <TableCell className="font-data text-[0.82rem]">
        {returnPct != null ? (
          <span style={{ color: returnPct >= 0 ? 'var(--success)' : 'var(--danger)', fontWeight: 600 }}>
            {returnPct >= 0 ? '+' : ''}{returnPct.toFixed(2)}%
          </span>
        ) : <span style={{ color: 'var(--text-muted)' }}>—</span>}
      </TableCell>
      <TableCell className="text-[0.75rem]" style={{ color: 'var(--text-muted)' }}>
        {holding.sector || '—'}
      </TableCell>
      <TableCell className="text-right">
        <div className="flex gap-1.5 justify-end">
          <Button
            variant="secondary"
            size="sm"
            onClick={() => onEdit(holding)}
            className="h-7 px-2.5 text-[0.72rem]"
          >
            Edit
          </Button>
          <button
            onClick={() => onDelete(holding.id)}
            className="text-[0.75rem] px-1.5 py-1 rounded transition-colors"
            style={{ color: 'var(--text-muted)' }}
            onMouseEnter={(e) => { e.currentTarget.style.color = 'var(--danger)'; }}
            onMouseLeave={(e) => { e.currentTarget.style.color = 'var(--text-muted)'; }}
            title="Delete holding"
          >
            ✕
          </button>
        </div>
      </TableCell>
    </TableRow>
  );
};

/* ──────── Label style ──────── */
const FieldLabel = ({ children }) => (
  <label className="text-[0.65rem] font-semibold uppercase tracking-wider block mb-1" style={{ color: 'var(--text-muted)' }}>
    {children}
  </label>
);

/* ──────── Main PortfolioView component ──────── */
const PortfolioView = ({ onSelectTicker }) => {
  const [loading, setLoading] = useState(false);
  const [savingHolding, setSavingHolding] = useState(false);
  const [error, setError] = useState(null);

  const [portfolio, setPortfolio] = useState({ profile: DEFAULT_PROFILE, holdings: [], snapshot: null });
  const [holdingForm, setHoldingForm] = useState(EMPTY_HOLDING);
  const [editingHoldingId, setEditingHoldingId] = useState(null);

  const loadPortfolio = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await getPortfolio();
      setPortfolio({
        profile: data?.profile || DEFAULT_PROFILE,
        holdings: data?.holdings || [],
        snapshot: data?.snapshot || null,
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

  // Derive holdings rows from snapshot (enriched) or raw holdings
  const holdingsRows = (() => {
    const snap = portfolio?.snapshot?.by_ticker;
    if (Array.isArray(snap) && snap.length > 0) return snap;
    return portfolio?.holdings || [];
  })();

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
      market_value: holdingForm.market_value === '' ? null : Number(holdingForm.market_value),
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
    <div className="flex-1 p-6">
      <h2 className="text-lg font-bold mb-4" style={{ color: 'var(--text-primary)' }}>Portfolio</h2>

      {loading && holdingsRows.length === 0 ? (
        <div className="text-center py-12 text-[0.82rem]" style={{ color: 'var(--text-muted)' }}>
          Loading...
        </div>
      ) : (
        <>
          {/* Summary strip */}
          <SummaryStrip snapshot={portfolio.snapshot} />

          {/* Add / Edit holding form */}
          <Card className="mb-5">
            <CardHeader className="pb-3">
              <CardTitle className="text-xs uppercase tracking-widest" style={{ color: 'var(--text-muted)' }}>
                {editingHoldingId ? 'Edit Holding' : 'Add Holding'}
              </CardTitle>
            </CardHeader>
            <CardContent className="pt-0">
              <form onSubmit={handleHoldingSubmit}>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5, 1fr) auto', gap: 12, alignItems: 'end' }}>
                  <div>
                    <FieldLabel>Ticker</FieldLabel>
                    <Input
                      type="text"
                      maxLength={5}
                      value={holdingForm.ticker}
                      onChange={(e) => setHoldingForm((prev) => ({ ...prev, ticker: e.target.value.toUpperCase() }))}
                      className="uppercase font-data"
                      placeholder="AAPL"
                    />
                  </div>
                  <div>
                    <FieldLabel>Shares</FieldLabel>
                    <Input
                      type="number"
                      min="0"
                      step="0.0001"
                      value={holdingForm.shares}
                      onChange={(e) => setHoldingForm((prev) => ({ ...prev, shares: e.target.value }))}
                      className="font-data"
                      placeholder="100"
                    />
                  </div>
                  <div>
                    <FieldLabel>Avg Cost</FieldLabel>
                    <Input
                      type="number"
                      min="0"
                      step="0.01"
                      value={holdingForm.avg_cost}
                      onChange={(e) => setHoldingForm((prev) => ({ ...prev, avg_cost: e.target.value }))}
                      className="font-data"
                      placeholder="150.00"
                    />
                  </div>
                  <div>
                    <FieldLabel>Market Value</FieldLabel>
                    <Input
                      type="number"
                      min="0"
                      step="0.01"
                      value={holdingForm.market_value}
                      onChange={(e) => setHoldingForm((prev) => ({ ...prev, market_value: e.target.value }))}
                      className="font-data"
                      placeholder="Optional"
                    />
                  </div>
                  <div>
                    <FieldLabel>Sector</FieldLabel>
                    <Input
                      type="text"
                      value={holdingForm.sector}
                      onChange={(e) => setHoldingForm((prev) => ({ ...prev, sector: e.target.value }))}
                      placeholder="Technology"
                    />
                  </div>
                  <div className="flex gap-2">
                    <Button
                      type="submit"
                      disabled={savingHolding || !holdingForm.ticker.trim()}
                      className="whitespace-nowrap"
                    >
                      {savingHolding ? 'Saving...' : editingHoldingId ? 'Update' : 'Add'}
                    </Button>
                    {editingHoldingId && (
                      <Button
                        type="button"
                        variant="secondary"
                        onClick={resetHoldingForm}
                        className="whitespace-nowrap"
                      >
                        Cancel
                      </Button>
                    )}
                  </div>
                </div>
              </form>
            </CardContent>
          </Card>

          {/* Holdings table */}
          <Card className="mb-5">
            <CardHeader className="pb-3">
              <CardTitle className="text-xs uppercase tracking-widest" style={{ color: 'var(--text-muted)' }}>
                Holdings
              </CardTitle>
            </CardHeader>
            <CardContent className="pt-0">
              {holdingsRows.length === 0 ? (
                <div className="text-center py-6 text-[0.82rem]" style={{ color: 'var(--text-muted)' }}>
                  No holdings added yet.
                </div>
              ) : (
                <div className="overflow-x-auto">
                  <Table>
                    <TableHeader>
                      <TableRow>
                        {['Ticker', 'Shares', 'Market Value', 'Return %', 'Sector', ''].map((h) => (
                          <TableHead
                            key={h}
                            className={`text-[0.65rem] uppercase tracking-widest ${h === '' ? 'text-right' : ''}`}
                            style={{ color: 'var(--text-muted)' }}
                          >
                            {h}
                          </TableHead>
                        ))}
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {holdingsRows.map((holding) => (
                        <HoldingRow
                          key={holding.id || holding.ticker}
                          holding={holding}
                          onEdit={startEditHolding}
                          onDelete={handleDeleteHolding}
                          onSelectTicker={onSelectTicker}
                        />
                      ))}
                    </TableBody>
                  </Table>
                </div>
              )}
            </CardContent>
          </Card>
        </>
      )}

      {/* Error */}
      {error && (
        <div
          className="mt-4 px-3.5 py-2.5 rounded-lg text-[0.82rem]"
          style={{
            background: 'rgba(243,18,96,0.1)',
            border: '1px solid rgba(243,18,96,0.3)',
            color: 'var(--danger)',
          }}
        >
          {error}
        </div>
      )}
    </div>
  );
};

export default PortfolioView;
