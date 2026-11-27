import React from 'react';
import ReliabilityBanner from './components/ReliabilityBanner.jsx';
import BankDashboardView from './components/BankDashboardView.jsx';
import BalanceSheetDashboardView from './components/BalanceSheetDashboardView.jsx';
import {
  DashboardLoadingState,
  DashboardEmptyState,
  DashboardErrorState
} from './components/DashboardStates.jsx';
import { formatCurrencyLabel } from '../../utils/formatters.js';
import { useDashboardAnalysis } from './useDashboardAnalysis.js';
import './DashboardPage.css';

// Default development fixtures for offline inspection
import defaultBankFixture from '../../mocks/dashboard/bankAnalysisValid.json';

/**
 * Person 3: DashboardPage
 * Default export required by Person 1 router at /workspaces/:workspaceId/dashboard
 */
export function DashboardPage({
  workspaceId = null,
  analysis = null,
  documentMetadata = null,
  loading = false,
  error = null,
  onNavigate = null,
  onRetry = null,
  onInspectEvidence = null,
  children = null
}) {
  // Use custom hook if analysis is not explicitly injected as a prop
  const hookResult = useDashboardAnalysis(workspaceId, {
    skip: Boolean(analysis) || !workspaceId
  });

  const activeLoading = loading || (Boolean(workspaceId) && !analysis && hookResult.loading);
  const activeError = error || (!analysis && hookResult.error);
  const handleRetryAction = onRetry || hookResult.reload;

  // 1. Loading State
  if (activeLoading) {
    return (
      <main className="fg-dashboard-page" aria-busy="true">
        <DashboardLoadingState />
      </main>
    );
  }

  // 2. Error State
  if (activeError) {
    return (
      <main className="fg-dashboard-page">
        <DashboardErrorState
          error={activeError}
          onRetry={handleRetryAction}
          onNavigateUpload={onNavigate ? () => onNavigate('upload') : null}
        />
      </main>
    );
  }

  // Determine active analysis data: injected analysis, fetched analysis, or dev fixture
  const activeAnalysis = analysis || hookResult.analysis || (workspaceId ? null : defaultBankFixture);

  // 3. Empty State (no workspace or document)
  if (!activeAnalysis && !documentMetadata) {
    return (
      <main className="fg-dashboard-page">
        <DashboardEmptyState
          onNavigateUpload={onNavigate ? () => onNavigate('upload') : null}
        />
      </main>
    );
  }

  const docType = activeAnalysis?.document_type || documentMetadata?.document_type || 'bank_statement';
  const currency = activeAnalysis?.currency || documentMetadata?.currency || 'INR';
  const filename = documentMetadata?.original_filename || documentMetadata?.filename || null;
  const reliability = activeAnalysis?.reliability || 'valid';
  const warnings = activeAnalysis?.warnings || [];
  const metrics = activeAnalysis?.metrics || [];

  const isBalanceSheet = docType === 'balance_sheet';

  return (
    <main className="fg-dashboard-page">
      {/* Workspace / Document Header */}
      <header className="fg-dashboard-page-header">
        <div>
          <h1 className="fg-dashboard-page-title">
            {isBalanceSheet ? 'Corporate Balance Sheet Dashboard' : 'Financial Statement Dashboard'}
          </h1>
          <div className="fg-dashboard-page-meta">
            {filename && (
              <>
                <span>Source: <strong>{filename}</strong></span>
                <span>•</span>
              </>
            )}
            <span>Currency: <strong>{formatCurrencyLabel(currency)}</strong></span>
            <span>•</span>
            <span className={`fg-doc-type-badge ${isBalanceSheet ? 'balance' : ''}`}>
              {isBalanceSheet ? 'Balance Sheet' : 'Bank Statement'}
            </span>
          </div>
        </div>

        {onNavigate && (
          <button
            type="button"
            className="fg-state-btn secondary"
            onClick={() => onNavigate('upload')}
          >
            Upload Document ↑
          </button>
        )}
      </header>

      {/* Reliability & Verification Warnings Banner */}
      <ReliabilityBanner reliability={reliability} warnings={warnings} />

      {/* Variant View: Bank vs Balance Sheet */}
      {isBalanceSheet ? (
        <BalanceSheetDashboardView
          metrics={metrics}
          onInspectEvidence={onInspectEvidence}
        >
          {children}
        </BalanceSheetDashboardView>
      ) : (
        <BankDashboardView
          metrics={metrics}
          onInspectEvidence={onInspectEvidence}
        >
          {children}
        </BankDashboardView>
      )}
    </main>
  );
}

export default DashboardPage;
