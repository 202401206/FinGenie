import React from 'react';
import MetricCard from './MetricCard.jsx';

/**
 * Bank Statement Dashboard View
 * Displays Inflow, Outflow, Net Cash Flow cards + slot for transaction exploration
 */
export function BankDashboardView({ metrics = [], onInspectEvidence, children }) {
  // Sort known bank metrics in logical order
  const order = ['total_credit', 'total_debit', 'net_cash_flow'];
  const sortedMetrics = [...metrics].sort((a, b) => {
    const idxA = order.indexOf(a.key);
    const idxB = order.indexOf(b.key);
    if (idxA !== -1 && idxB !== -1) return idxA - idxB;
    if (idxA !== -1) return -1;
    if (idxB !== -1) return 1;
    return 0;
  });

  return (
    <div className="fg-bank-dashboard-view">
      <div className="fg-section-header">
        <h3 className="fg-section-title">Bank Statement Financial Metrics</h3>
        <span className="fg-section-badge">Deterministic V1 Analysis</span>
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

      {/* Slot for children (e.g. Transactions Table, Summary Panel, Charts) */}
      {children}
    </div>
  );
}

export default BankDashboardView;
