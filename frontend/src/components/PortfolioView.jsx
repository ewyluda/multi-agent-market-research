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
    <div style={{
      display: 'grid',
      gridTemplateColumns: 'repeat(3, 1fr)',
      gap: 12,
      marginBottom: 24,
    }}>
      {[
        { label: 'Total Value', value: fmtCurrency(totalVal) },
        { label: 'Holdings', value: holdingsCount.toString() },
        { label: 'Top Sector', value: topSector || '—' },
      ].map(({ label, value }) => (
        <div key={label} style={{
          background: 'rgba(255,255,255,0.02)',
          border: '1px solid rgba(255,255,255,0.06)',
          borderRadius: 10,
          padding: '14px 18px',
        }}>
          <div style={{ fontSize: '0.65rem', color: 'rgba(255,255,255,0.4)', textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: 6 }}>
            {label}
          </div>
          <div style={{ fontSize: '1.1rem', fontWeight: 700, color: 'rgba(255,255,255,0.9)', fontFamily: 'monospace' }}>
            {value}
          </div>
        </div>
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
    <tr style={{ borderBottom: '1px solid rgba(255,255,255,0.04)', transition: 'background 0.15s' }}
      onMouseEnter={(e) => { e.currentTarget.style.background = 'rgba(255,255,255,0.02)'; }}
      onMouseLeave={(e) => { e.currentTarget.style.background = 'transparent'; }}
    >
      <td style={{ padding: '10px 14px' }}>
        <button
          onClick={() => onSelectTicker?.(holding.ticker)}
          style={{
            background: 'none',
            border: 'none',
            cursor: 'pointer',
            fontFamily: 'monospace',
            fontWeight: 700,
            fontSize: '0.85rem',
            color: '#006fee',
            padding: 0,
          }}
        >
          {holding.ticker}
        </button>
      </td>
      <td style={{ padding: '10px 14px', fontSize: '0.82rem', color: 'rgba(255,255,255,0.7)', fontFamily: 'monospace' }}>
        {Number(holding.shares || 0).toLocaleString(undefined, { maximumFractionDigits: 4 })}
      </td>
      <td style={{ padding: '10px 14px', fontSize: '0.82rem', color: 'rgba(255,255,255,0.7)', fontFamily: 'monospace' }}>
        {fmtCurrency(holding.market_value)}
      </td>
      <td style={{ padding: '10px 14px', fontSize: '0.82rem', fontFamily: 'monospace' }}>
        {returnPct != null ? (
          <span style={{ color: returnPct >= 0 ? '#17c964' : '#f31260', fontWeight: 600 }}>
            {returnPct >= 0 ? '+' : ''}{returnPct.toFixed(2)}%
          </span>
        ) : <span style={{ color: 'rgba(255,255,255,0.25)' }}>—</span>}
      </td>
      <td style={{ padding: '10px 14px', fontSize: '0.75rem', color: 'rgba(255,255,255,0.5)' }}>
        {holding.sector || '—'}
      </td>
      <td style={{ padding: '10px 14px' }}>
        <div style={{ display: 'flex', gap: 6, justifyContent: 'flex-end' }}>
          <button
            onClick={() => onEdit(holding)}
            style={{
              background: 'rgba(255,255,255,0.04)',
              border: '1px solid rgba(255,255,255,0.08)',
              borderRadius: 6,
              padding: '4px 10px',
              fontSize: '0.72rem',
              color: 'rgba(255,255,255,0.6)',
              cursor: 'pointer',
              transition: 'all 0.15s',
            }}
            onMouseEnter={(e) => { e.currentTarget.style.color = 'rgba(255,255,255,0.9)'; e.currentTarget.style.borderColor = 'rgba(255,255,255,0.2)'; }}
            onMouseLeave={(e) => { e.currentTarget.style.color = 'rgba(255,255,255,0.6)'; e.currentTarget.style.borderColor = 'rgba(255,255,255,0.08)'; }}
          >
            Edit
          </button>
          <button
            onClick={() => onDelete(holding.id)}
            style={{
              background: 'none',
              border: 'none',
              cursor: 'pointer',
              fontSize: '0.75rem',
              color: 'rgba(255,255,255,0.2)',
              padding: '4px 6px',
              borderRadius: 6,
              transition: 'color 0.15s',
            }}
            onMouseEnter={(e) => { e.currentTarget.style.color = '#f31260'; }}
            onMouseLeave={(e) => { e.currentTarget.style.color = 'rgba(255,255,255,0.2)'; }}
            title="Delete holding"
          >
            ✕
          </button>
        </div>
      </td>
    </tr>
  );
};

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

  const inputStyle = {
    background: 'rgba(255,255,255,0.04)',
    border: '1px solid rgba(255,255,255,0.06)',
    borderRadius: 8,
    padding: '8px 12px',
    fontSize: '0.82rem',
    color: 'rgba(255,255,255,0.9)',
    outline: 'none',
    width: '100%',
  };

  const labelStyle = {
    fontSize: '0.65rem',
    color: 'rgba(255,255,255,0.4)',
    fontWeight: 600,
    textTransform: 'uppercase',
    letterSpacing: '0.06em',
    display: 'block',
    marginBottom: 4,
  };

  const cardStyle = {
    background: 'rgba(255,255,255,0.02)',
    border: '1px solid rgba(255,255,255,0.06)',
    borderRadius: 12,
    padding: '20px',
    marginBottom: 20,
  };

  return (
    <div className="flex-1 p-6">
      <h2 className="text-lg font-bold text-white/90 mb-4">Portfolio</h2>

      {loading && holdingsRows.length === 0 ? (
        <div style={{ textAlign: 'center', padding: '48px', color: 'rgba(255,255,255,0.3)', fontSize: '0.82rem' }}>
          Loading...
        </div>
      ) : (
        <>
          {/* Summary strip */}
          <SummaryStrip snapshot={portfolio.snapshot} />

          {/* Add / Edit holding form */}
          <div style={cardStyle}>
            <div style={{ fontSize: '0.65rem', fontWeight: 700, color: 'rgba(255,255,255,0.4)', textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: 14 }}>
              {editingHoldingId ? 'Edit Holding' : 'Add Holding'}
            </div>
            <form onSubmit={handleHoldingSubmit}>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5, 1fr) auto', gap: 12, alignItems: 'end' }}>
                <div>
                  <label style={labelStyle}>Ticker</label>
                  <input
                    type="text"
                    maxLength={5}
                    value={holdingForm.ticker}
                    onChange={(e) => setHoldingForm((prev) => ({ ...prev, ticker: e.target.value.toUpperCase() }))}
                    style={{ ...inputStyle, textTransform: 'uppercase' }}
                    placeholder="AAPL"
                  />
                </div>
                <div>
                  <label style={labelStyle}>Shares</label>
                  <input
                    type="number"
                    min="0"
                    step="0.0001"
                    value={holdingForm.shares}
                    onChange={(e) => setHoldingForm((prev) => ({ ...prev, shares: e.target.value }))}
                    style={inputStyle}
                    placeholder="100"
                  />
                </div>
                <div>
                  <label style={labelStyle}>Avg Cost</label>
                  <input
                    type="number"
                    min="0"
                    step="0.01"
                    value={holdingForm.avg_cost}
                    onChange={(e) => setHoldingForm((prev) => ({ ...prev, avg_cost: e.target.value }))}
                    style={inputStyle}
                    placeholder="150.00"
                  />
                </div>
                <div>
                  <label style={labelStyle}>Market Value</label>
                  <input
                    type="number"
                    min="0"
                    step="0.01"
                    value={holdingForm.market_value}
                    onChange={(e) => setHoldingForm((prev) => ({ ...prev, market_value: e.target.value }))}
                    style={inputStyle}
                    placeholder="Optional"
                  />
                </div>
                <div>
                  <label style={labelStyle}>Sector</label>
                  <input
                    type="text"
                    value={holdingForm.sector}
                    onChange={(e) => setHoldingForm((prev) => ({ ...prev, sector: e.target.value }))}
                    style={inputStyle}
                    placeholder="Technology"
                  />
                </div>
                <div style={{ display: 'flex', gap: 8 }}>
                  <button
                    type="submit"
                    disabled={savingHolding || !holdingForm.ticker.trim()}
                    style={{
                      background: savingHolding || !holdingForm.ticker.trim() ? 'rgba(255,255,255,0.06)' : '#006fee',
                      color: savingHolding || !holdingForm.ticker.trim() ? 'rgba(255,255,255,0.3)' : '#fff',
                      border: 'none',
                      borderRadius: 8,
                      padding: '9px 16px',
                      fontSize: '0.82rem',
                      fontWeight: 600,
                      cursor: savingHolding || !holdingForm.ticker.trim() ? 'not-allowed' : 'pointer',
                      whiteSpace: 'nowrap',
                    }}
                  >
                    {savingHolding ? 'Saving...' : editingHoldingId ? 'Update' : 'Add'}
                  </button>
                  {editingHoldingId && (
                    <button
                      type="button"
                      onClick={resetHoldingForm}
                      style={{
                        background: 'rgba(255,255,255,0.04)',
                        border: '1px solid rgba(255,255,255,0.08)',
                        borderRadius: 8,
                        padding: '9px 12px',
                        fontSize: '0.82rem',
                        color: 'rgba(255,255,255,0.6)',
                        cursor: 'pointer',
                        whiteSpace: 'nowrap',
                      }}
                    >
                      Cancel
                    </button>
                  )}
                </div>
              </div>
            </form>
          </div>

          {/* Holdings table */}
          <div style={cardStyle}>
            <div style={{ fontSize: '0.65rem', fontWeight: 700, color: 'rgba(255,255,255,0.4)', textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: 14 }}>
              Holdings
            </div>
            {holdingsRows.length === 0 ? (
              <div style={{ textAlign: 'center', padding: '24px', color: 'rgba(255,255,255,0.25)', fontSize: '0.82rem' }}>
                No holdings added yet.
              </div>
            ) : (
              <div style={{ overflowX: 'auto' }}>
                <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                  <thead>
                    <tr style={{ borderBottom: '1px solid rgba(255,255,255,0.06)' }}>
                      {['Ticker', 'Shares', 'Market Value', 'Return %', 'Sector', ''].map((h) => (
                        <th key={h} style={{
                          padding: '8px 14px',
                          textAlign: h === '' ? 'right' : 'left',
                          fontSize: '0.65rem',
                          fontWeight: 700,
                          color: 'rgba(255,255,255,0.35)',
                          textTransform: 'uppercase',
                          letterSpacing: '0.08em',
                        }}>{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {holdingsRows.map((holding) => (
                      <HoldingRow
                        key={holding.id || holding.ticker}
                        holding={holding}
                        onEdit={startEditHolding}
                        onDelete={handleDeleteHolding}
                        onSelectTicker={onSelectTicker}
                      />
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </>
      )}

      {/* Error */}
      {error && (
        <div style={{
          marginTop: 16,
          padding: '10px 14px',
          background: 'rgba(243,18,96,0.1)',
          border: '1px solid rgba(243,18,96,0.3)',
          borderRadius: 8,
          color: '#f31260',
          fontSize: '0.82rem',
        }}>
          {error}
        </div>
      )}
    </div>
  );
};

export default PortfolioView;
