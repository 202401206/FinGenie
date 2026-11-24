import React, { useState } from 'react';
import { formatCurrency } from '../../../utils/formatters.js';

const METRIC_LABELS = {
  total_credit: { label: 'Total Inflow / Credits', icon: '💰', description: 'Total deposits recorded in statement' },
  total_debit: { label: 'Total Outflow / Debits', icon: '💸', description: 'Total withdrawals and expenses' },
  net_cash_flow: { label: 'Net Cash Flow', icon: '📊', description: 'Net surplus or deficit (Credits - Debits)' },
  working_capital: { label: 'Working Capital', icon: '💼', description: 'Current Assets minus Current Liabilities' },
  current_ratio: { label: 'Current Ratio (Liquidity)', icon: '⚖️', description: 'Current Assets divided by Current Liabilities' },
  balance_difference: { label: 'Balance Difference', icon: '🔍', description: 'Assets minus (Liabilities + Equity)' }
};

/**
 * Renders an individual KPI card from the backend analysis contract.
 */
export function MetricCard({ metric, onInspectEvidence }) {
  const [showEvidence, setShowEvidence] = useState(false);

  if (!metric) return null;

  const {
    key,
    value,
    unit,
    status = 'available',
    reason = null,
    calculation_id = null,
    source_refs = []
  } = metric;

  const meta = METRIC_LABELS[key] || {
    label: key.replace(/_/g, ' ').toUpperCase(),
    icon: '📈',
    description: null
  };

  const isAvailable = status === 'available' && value !== null && value !== undefined;

  let displayValue;
  if (!isAvailable) {
    displayValue = '—';
  } else if (unit === 'ratio') {
    displayValue = Number(value).toFixed(2);
  } else {
    displayValue = formatCurrency(value, unit || 'INR');
  }

  const isNegative = isAvailable && unit !== 'ratio' && Number(value) < 0;

  return (
    <div className={`fg-kpi-card ${!isAvailable ? 'unavailable' : ''}`} data-metric-key={key}>
      <div className="fg-kpi-card-header">
        <span className="fg-kpi-card-label">{meta.label}</span>
        <span className="fg-kpi-card-icon" aria-hidden="true">{meta.icon}</span>
      </div>

      <div className="fg-kpi-card-body">
        <div className={`fg-kpi-card-value ${isNegative ? 'negative' : ''}`}>
          {displayValue}
        </div>

        {!isAvailable && reason && (
          <p className="fg-kpi-unavailable-reason" role="note">
            ⚠️ {reason}
          </p>
        )}

        {meta.description && isAvailable && (
          <p className="fg-kpi-card-desc">{meta.description}</p>
        )}
      </div>

      <div className="fg-kpi-card-footer">
        {calculation_id && (
          <span className="fg-kpi-calc-id" title={`Engine calculation ID: ${calculation_id}`}>
            {calculation_id}
          </span>
        )}

        {source_refs && source_refs.length > 0 && (
          <button
            type="button"
            className="fg-kpi-evidence-btn"
            onClick={() => {
              setShowEvidence(!showEvidence);
              if (onInspectEvidence) onInspectEvidence(metric);
            }}
            aria-expanded={showEvidence}
          >
            {showEvidence ? 'Hide Source' : `Evidence (${source_refs.length})`}
          </button>
        )}
      </div>

      {showEvidence && source_refs && source_refs.length > 0 && (
        <div className="fg-kpi-evidence-drawer">
          <div className="fg-evidence-title">Source Rows & Fields:</div>
          <ul className="fg-evidence-list">
            {source_refs.map((ref, idx) => (
              <li key={idx}>
                {ref.sheet_name && <span>Sheet: <strong>{ref.sheet_name}</strong> • </span>}
                {ref.source_rows && ref.source_rows.length > 0 && (
                  <span>Row(s): <strong>{ref.source_rows.join(', ')}</strong></span>
                )}
                {ref.field_paths && ref.field_paths.length > 0 && (
                  <div className="fg-evidence-fields">Fields: {ref.field_paths.join(', ')}</div>
                )}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

export default MetricCard;
