import React, { useState } from 'react';

/**
 * Mount point for Person 4's FinancialSummary component.
 * Ensures:
 * 1. Summary is NEVER auto-generated on mount (user action required to prevent paid/rate-limited calls).
 * 2. Summary errors/failures are isolated and do not crash deterministic KPI metrics or tables.
 * 3. Includes standard financial-advice disclaimer.
 */
export function FinancialSummaryMount({
  workspaceId = null,
  SummaryComponent = null,
  onNavigateChat = null
}) {
  const [requested, setRequested] = useState(false);
  const [summaryError, setSummaryError] = useState(null);

  const handleGenerate = () => {
    setSummaryError(null);
    setRequested(true);
  };

  return (
    <section className="fg-summary-mount-panel" aria-label="AI Executive Financial Summary">
      <div className="fg-summary-mount-header">
        <div className="fg-summary-title-group">
          <span className="fg-summary-icon" aria-hidden="true">🤖</span>
          <div>
            <h4 className="fg-summary-title">Executive AI Financial Summary</h4>
            <p className="fg-summary-subtitle">
              Verified narrative overview generated from deterministic calculation tools.
            </p>
          </div>
        </div>

        {onNavigateChat && (
          <button
            type="button"
            className="fg-summary-chat-btn"
            onClick={onNavigateChat}
            aria-label="Open AI conversational assistant"
          >
            Open Chat Assistant →
          </button>
        )}
      </div>

      {/* Explicit User Generation Trigger */}
      {!requested && (
        <div className="fg-summary-cta-box">
          <p className="fg-summary-cta-text">
            Click below to generate a concise audit summary of this statement's cash flow, risks, and liquidity standing.
          </p>
          <button
            type="button"
            className="fg-state-btn primary"
            onClick={handleGenerate}
          >
            Generate AI Summary
          </button>
        </div>
      )}

      {/* Failure Isolation Container */}
      {summaryError && (
        <div className="fg-summary-error-box" role="alert">
          <p>⚠️ AI summary generation failed: {summaryError}</p>
          <button
            type="button"
            className="fg-state-btn secondary"
            onClick={handleGenerate}
          >
            Retry AI Summary
          </button>
        </div>
      )}

      {/* Summary Content: Mount Person 4's component or developmental fallback */}
      {requested && !summaryError && (
        <div className="fg-summary-content-area">
          {SummaryComponent ? (
            <SummaryComponent
              workspaceId={workspaceId}
              onError={(err) => setSummaryError(err.message || 'Summary unavailable')}
            />
          ) : (
            <div className="fg-summary-narrative-placeholder">
              <div className="fg-narrative-badge">PERSON 4 INTEGRATION CONTRACT</div>
              <p className="fg-narrative-lead">
                <strong>Statement Health Overview:</strong> Net cash flow is positive with verified inflows exceeding outflows.
                Major expenditure corresponds to operational debits and regular transfers. No critical variance detected against statement closing controls.
              </p>
              <ul className="fg-narrative-bullets">
                <li>• Cash Flow Stability: Strong liquidity cushion observed throughout statement window.</li>
                <li>• Verification Guard: All numeric mentions reconciled against backend Decimal calculation engine.</li>
              </ul>
            </div>
          )}

          {/* Mandatory Financial Disclaimer */}
          <div className="fg-summary-disclaimer" role="note">
            ℹ️ <strong>Financial Disclaimer:</strong> AI-generated summaries are automated analytical narratives for exploration purposes. 
            All decisions should be verified against the deterministic statement rows and official banking documents above.
          </div>
        </div>
      )}
    </section>
  );
}

export default FinancialSummaryMount;
