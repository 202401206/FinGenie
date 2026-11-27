import React from 'react';
import MetricCard from './MetricCard.jsx';
import TransactionExplorer from './TransactionExplorer.jsx';

/**
 * Bank Statement Dashboard View
 * Displays Inflow, Outflow, Net Cash Flow cards + Bank Transaction Explorer
 */
export function BankDashboardView({
  metrics = [],
  transactions = [],
  total = 0,
  offset = 0,
  limit = 50,
  currency = 'INR',
  highlightSourceRow = null,
  onPageChange = null,
  onInspectEvidence = null,
  children = null
}) {
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

      {/* Paginated Bank Transactions Ledger */}
      <TransactionExplorer
        transactions={transactions}
        total={total}
        offset={offset}
        limit={limit}
        currency={currency}
        highlightSourceRow={highlightSourceRow}
        onPageChange={onPageChange}
      />

      {/* Slot for children (e.g. Summary Panel, Charts) */}
      {children}
    </div>
  );
}

export default BankDashboardView;
