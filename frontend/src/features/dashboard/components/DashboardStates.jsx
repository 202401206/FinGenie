import React from 'react';

export function DashboardLoadingState({ message = 'Loading workspace financial analysis...' }) {
  return (
    <div className="fg-dashboard-state-container" role="status" aria-live="polite">
      <div className="fg-loading-spinner" aria-hidden="true" />
      <p className="fg-loading-message">{message}</p>
    </div>
  );
}

export function DashboardEmptyState({ onNavigateUpload }) {
  return (
    <div className="fg-dashboard-state-container fg-empty-state">
      <div className="fg-state-icon" aria-hidden="true">📊</div>
      <h3 className="fg-state-title">No Document Loaded</h3>
      <p className="fg-state-desc">
        Select an active workspace from your documents or upload a new bank statement / balance sheet to explore financial KPIs.
      </p>
      {onNavigateUpload && (
        <button
          type="button"
          className="fg-state-btn"
          onClick={onNavigateUpload}
        >
          Go to Document Upload →
        </button>
      )}
    </div>
  );
}

export function DashboardErrorState({ error, onRetry, onNavigateUpload }) {
  const is409 = error && (error.includes('document_not_ready') || error.includes('409') || error.includes('processing'));
  const is404 = error && (error.includes('not found') || error.includes('404'));

  let title = 'Failed to Load Analysis';
  let desc = error || 'An unexpected error occurred while loading workspace analysis.';

  if (is409) {
    title = 'Document Still Processing';
    desc = 'The uploaded document is being parsed. Please refresh shortly once parsing completes.';
  } else if (is404) {
    title = 'Workspace Not Found';
    desc = 'The requested workspace could not be found or belongs to another account.';
  }

  return (
    <div className="fg-dashboard-state-container fg-error-state" role="alert">
      <div className="fg-state-icon" aria-hidden="true">⚠️</div>
      <h3 className="fg-state-title">{title}</h3>
      <p className="fg-state-desc">{desc}</p>
      <div className="fg-state-actions">
        {onRetry && (
          <button type="button" className="fg-state-btn primary" onClick={onRetry}>
            Retry Request
          </button>
        )}
        {onNavigateUpload && (
          <button type="button" className="fg-state-btn secondary" onClick={onNavigateUpload}>
            Back to Documents
          </button>
        )}
      </div>
    </div>
  );
}


export function DashboardDeletionPendingState() {
  return (
    <div className="fg-dashboard-state-container fg-deletion-state" role="status" aria-live="polite">
      <div className="fg-state-icon" aria-hidden="true">🗑️</div>
      <h3 className="fg-state-title">Deletion In Progress</h3>
      <p className="fg-state-desc">
        Workspace financial records and associated statement data are currently being deleted. 
        Financial content is hidden and new mutations are suspended.
      </p>
    </div>
  );
}
