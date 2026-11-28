import React from 'react';
import { formatCurrency } from '../../../utils/formatters.js';

/**
 * Accessible, responsive visualization for verified analysis metrics.
 * Strictly visualizes actual returned data without fabricating time-series.
 * Keeps unitless ratios strictly separated from monetary currency values.
 */
export function FinancialMetricsChart({ metrics = [], documentType = 'bank_statement', currency = 'INR' }) {
  if (!metrics || metrics.length === 0) return null;

  if (documentType === 'balance_sheet') {
    const wcMetric = metrics.find(m => m.key === 'working_capital');
    const ratioMetric = metrics.find(m => m.key === 'current_ratio');
    const diffMetric = metrics.find(m => m.key === 'balance_difference');

    const wcValue = wcMetric && wcMetric.status === 'available' ? Number(wcMetric.value) : null;
    const ratioValue = ratioMetric && ratioMetric.status === 'available' ? Number(ratioMetric.value) : null;
    const diffValue = diffMetric && diffMetric.status === 'available' ? Number(diffMetric.value) : null;

    return (
      <section className="fg-metrics-chart-panel" aria-label="Balance Sheet Liquidity Analysis">
        <div className="fg-chart-header">
          <h4 className="fg-chart-title">Balance Sheet Visual Position</h4>
          <span className="fg-chart-legend-unit">Base Currency: {currency}</span>
        </div>

        <div className="fg-chart-grid-balance">
          {/* Working Capital Bar */}
          <div className="fg-chart-card">
            <span className="fg-chart-card-label">Working Capital Position</span>
            <div className="fg-chart-card-val">
              {wcValue !== null ? formatCurrency(wcValue, currency) : '—'}
            </div>
            <div className="fg-bar-track">
              <div
                className={`fg-bar-fill ${wcValue && wcValue >= 0 ? 'positive' : 'negative'}`}
                style={{ width: wcValue !== null ? '100%' : '0%' }}
                role="progressbar"
                aria-valuenow={wcValue || 0}
                aria-label="Working Capital"
              />
            </div>
            <span className="fg-chart-subtext">
              {wcValue !== null && wcValue >= 0 ? 'Adequate short-term liquidity cushion' : 'Negative working capital warning'}
            </span>
          </div>

          {/* Current Ratio Gauge - strictly separated from currency */}
          <div className="fg-chart-card">
            <span className="fg-chart-card-label">Current Ratio (Unitless)</span>
            <div className="fg-chart-card-val ratio">
              {ratioValue !== null ? ratioValue.toFixed(2) : '—'}
            </div>
            <div className="fg-bar-track">
              <div
                className={`fg-bar-fill ${ratioValue && ratioValue >= 1.5 ? 'healthy' : 'warning'}`}
                style={{ width: ratioValue !== null ? `${Math.min(100, (ratioValue / 3) * 100)}%` : '0%' }}
                role="progressbar"
                aria-valuenow={ratioValue || 0}
                aria-label="Current Ratio"
              />
            </div>
            <span className="fg-chart-subtext">
              Target standard: ≥ 1.50 • Current: {ratioValue !== null ? ratioValue.toFixed(2) : 'Unavailable'}
            </span>
          </div>

          {/* Balance Reconciliation Difference */}
          <div className="fg-chart-card">
            <span className="fg-chart-card-label">Assets vs (Liabilities + Equity)</span>
            <div className="fg-chart-card-val">
              {diffValue !== null ? formatCurrency(diffValue, currency) : '—'}
            </div>
            <div className="fg-bar-track">
              <div
                className={`fg-bar-fill ${diffValue === 0 ? 'balanced' : 'negative'}`}
                style={{ width: '100%' }}
              />
            </div>
            <span className="fg-chart-subtext">
              {diffValue === 0 ? 'Perfect mathematical balance (Difference: 0)' : 'Discrepancy detected'}
            </span>
          </div>
        </div>
      </section>
    );
  }

  // Bank Statement Mode
  const creditMetric = metrics.find(m => m.key === 'total_credit');
  const debitMetric = metrics.find(m => m.key === 'total_debit');
  const netMetric = metrics.find(m => m.key === 'net_cash_flow');

  const creditVal = creditMetric && creditMetric.status === 'available' ? Math.max(0, Number(creditMetric.value)) : 0;
  const debitVal = debitMetric && debitMetric.status === 'available' ? Math.max(0, Number(debitMetric.value)) : 0;
  const netVal = netMetric && netMetric.status === 'available' ? Number(netMetric.value) : 0;

  const maxVal = Math.max(creditVal, debitVal, Math.abs(netVal), 1);
  const creditPct = Math.min(100, Math.round((creditVal / maxVal) * 100));
  const debitPct = Math.min(100, Math.round((debitVal / maxVal) * 100));
  const netPct = Math.min(100, Math.round((Math.abs(netVal) / maxVal) * 100));

  return (
    <section className="fg-metrics-chart-panel" aria-label="Statement Cash Flow Distribution Chart">
      <div className="fg-chart-header">
        <h4 className="fg-chart-title">Inflow vs. Outflow Distribution</h4>
        <span className="fg-chart-legend-unit">Unit: {currency}</span>
      </div>

      <div className="fg-chart-bars">
        {/* Credits / Inflow Bar */}
        <div className="fg-chart-row">
          <div className="fg-chart-row-meta">
            <span className="fg-chart-row-label">Total Inflow (Credits)</span>
            <span className="fg-chart-row-val">{formatCurrency(creditVal, currency)}</span>
          </div>
          <div className="fg-bar-track">
            <div
              className="fg-bar-fill credit"
              style={{ width: `${creditPct}%` }}
              role="progressbar"
              aria-valuenow={creditVal}
              aria-valuemin={0}
              aria-valuemax={maxVal}
              aria-label="Total Inflow"
            />
          </div>
        </div>

        {/* Debits / Outflow Bar */}
        <div className="fg-chart-row">
          <div className="fg-chart-row-meta">
            <span className="fg-chart-row-label">Total Outflow (Debits)</span>
            <span className="fg-chart-row-val">{formatCurrency(debitVal, currency)}</span>
          </div>
          <div className="fg-bar-track">
            <div
              className="fg-bar-fill debit"
              style={{ width: `${debitPct}%` }}
              role="progressbar"
              aria-valuenow={debitVal}
              aria-valuemin={0}
              aria-valuemax={maxVal}
              aria-label="Total Outflow"
            />
          </div>
        </div>

        {/* Net Cash Flow Bar */}
        <div className="fg-chart-row">
          <div className="fg-chart-row-meta">
            <span className="fg-chart-row-label">Net Cash Flow</span>
            <span className={`fg-chart-row-val ${netVal >= 0 ? 'positive' : 'negative'}`}>
              {formatCurrency(netVal, currency)}
            </span>
          </div>
          <div className="fg-bar-track">
            <div
              className={`fg-bar-fill ${netVal >= 0 ? 'net-positive' : 'net-negative'}`}
              style={{ width: `${netPct}%` }}
              role="progressbar"
              aria-valuenow={netVal}
              aria-label="Net Cash Flow"
            />
          </div>
        </div>
      </div>
    </section>
  );
}

export default FinancialMetricsChart;
