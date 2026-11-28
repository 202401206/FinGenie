import React from 'react';

/**
 * Renders the document reliability banner and any verification warnings.
 * Reliability status: 'valid' | 'unreliable' | 'insufficient_data'
 */
export function ReliabilityBanner({ reliability = 'valid', warnings = [] }) {
  if (reliability === 'valid' && (!warnings || warnings.length === 0)) {
    return (
      <div className="fg-reliability-banner fg-banner-valid" role="status" aria-live="polite">
        <div className="fg-banner-icon">✓</div>
        <div className="fg-banner-body">
          <span className="fg-banner-badge valid">Verified Analysis</span>
          <p className="fg-banner-text">
            All arithmetic, dates, and balance figures reconciled deterministically against source records.
          </p>
        </div>
      </div>
    );
  }

  const isUnreliable = reliability === 'unreliable';
  const bannerClass = isUnreliable ? 'fg-banner-unreliable' : 'fg-banner-insufficient';
  const badgeClass = isUnreliable ? 'unreliable' : 'insufficient';
  const title = isUnreliable
    ? 'Reconciliation Discrepancy Detected'
    : 'Insufficient Statement Data';

  return (
    <div className={`fg-reliability-banner ${bannerClass}`} role="alert">
      <div className="fg-banner-icon">{isUnreliable ? '⚠️' : 'ℹ️'}</div>
      <div className="fg-banner-body">
        <span className={`fg-banner-badge ${badgeClass}`}>
          {isUnreliable ? 'Unreliable Reconciliation' : 'Insufficient Data'}
        </span>
        <h4 className="fg-banner-title">{title}</h4>
        {warnings && warnings.length > 0 ? (
          <ul className="fg-banner-warnings">
            {warnings.map((w, idx) => (
              <li key={idx}>{w}</li>
            ))}
          </ul>
        ) : (
          <p className="fg-banner-text">
            Some figures could not be fully reconciled against statement controls. Review individual metric flags below.
          </p>
        )}
      </div>
    </div>
  );
}

export default ReliabilityBanner;
