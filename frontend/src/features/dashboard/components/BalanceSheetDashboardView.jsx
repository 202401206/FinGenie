import React from 'react';
import MetricCard from './MetricCard.jsx';

/**
 * Balance Sheet Dashboard View
 * Displays Working Capital, Current Ratio, and Balance Difference metrics.
 * Note: Balance sheets have NO transaction ledger, so transaction table is intentionally omitted.
 */
export function BalanceSheetDashboardView({ metrics = [], onInspectEvidence, children }) {
  const order = ['working_capital', 'current_ratio', 'balance_difference'];
  const sortedMetrics = [...metrics].sort((a, b) => {
    const idxA = order.indexOf(a.key);
    const idxB = order.indexOf(b.key);
    if (idxA !== -1 && idxB !== -1) return idxA - idxB;
    if (idxA !== -1) return -1;
    if (idxB !== -1) return 1;
    return 0;
  });

  return (
    <div className="fg-balance-dashboard-view">
      <div className="fg-section-header">
        <h3 className="fg-section-title">Balance Sheet & Liquidity Health</h3>
        <span className="fg-section-badge balance">Corporate Audit V1</span>
      </div>

      <div className="fg-kpi-grid">
        {sortedMetrics.map((m) => (
          <MetricCard
            key={m.key}
            metric={m}
            onInspectEvidence={onInspectEvidence}
          />
        ))}
      </div>

      <div className="fg-balance-info-notice" role="note">
        <span className="fg-info-icon" aria-hidden="true">💡</span>
        <div className="fg-info-content">
          <strong>Balance Sheet Exploration:</strong>
          <p>
            Balance sheets represent instantaneous financial position rather than cash flow transactions. 
            Transaction logs are not applicable to balance sheets per Sprint 2 architecture contracts.
          </p>
        </div>
      </div>

      {children}
    </div>
  );
}

export default BalanceSheetDashboardView;
