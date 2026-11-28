import React, { useState, useEffect } from 'react';
import ReliabilityBanner from './components/ReliabilityBanner.jsx';
import EvidenceFocusBanner from './components/EvidenceFocusBanner.jsx';
import FinancialSummaryMount from './components/FinancialSummaryMount.jsx';
import BankDashboardView from './components/BankDashboardView.jsx';
import BalanceSheetDashboardView from './components/BalanceSheetDashboardView.jsx';
import {
  DashboardLoadingState,
  DashboardEmptyState,
  DashboardErrorState,
  DashboardDeletionPendingState
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
  transactions = [],
  total = 0,
  offset = 0,
  limit = 50,
  highlightSourceRow = null,
  deletionPending = false,
  SummaryComponent = null,
  loading = false,
  error = null,
  onNavigate = null,
  onRetry = null,
  onPageChange = null,
  onInspectEvidence = null,
  children = null
}) {
  // Use custom hook if analysis is not explicitly injected as a prop
  const hookResult = useDashboardAnalysis(workspaceId, {
    skip: Boolean(analysis) || !workspaceId
  });

  // Evidence query handling: read ?documentId=...&sourceRow=...
  const [activeSourceRow, setActiveSourceRow] = useState(highlightSourceRow);
  const [activeDocId, setActiveDocId] = useState(null);

  useEffect(() => {
    if (typeof window !== 'undefined' && window.location?.search) {
      const params = new URLSearchParams(window.location.search);
      const rowParam = params.get('sourceRow');
      const docParam = params.get('documentId');
      if (rowParam && !isNaN(Number(rowParam))) {
        setActiveSourceRow(Number(rowParam));
      }
      if (docParam) {
        setActiveDocId(docParam);
      }
    } else if (highlightSourceRow !== null) {
      setActiveSourceRow(Number(highlightSourceRow));
    }
  }, [highlightSourceRow]);

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

  // 3. Deletion Pending State (from Person 1 useFinancialData)
  if (deletionPending) {
    return (
      <main className="fg-dashboard-page">
        <DashboardDeletionPendingState />
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

  const isRowLoaded = transactions.some(tx => tx.source_row === Number(activeSourceRow));

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

      {/* Evidence Focus Banner when query ?sourceRow=... is present */}
      {activeSourceRow !== null && (
        <EvidenceFocusBanner
          sourceRow={activeSourceRow}
          documentId={activeDocId}
          isRowLoaded={isRowLoaded}
          offset={offset}
          limit={limit}
          total={total}
          isBalanceSheet={isBalanceSheet}
          onClearFocus={() => setActiveSourceRow(null)}
        />
      )}

      {/* Reliability & Verification Warnings Banner */}
      <ReliabilityBanner reliability={reliability} warnings={warnings} />

      {/* Variant View: Bank vs Balance Sheet */}
      {isBalanceSheet ? (
        <BalanceSheetDashboardView
          metrics={metrics}
          currency={currency}
          onInspectEvidence={onInspectEvidence}
        >
          {children}
        </BalanceSheetDashboardView>
      ) : (
        <BankDashboardView
          metrics={metrics}
          transactions={transactions}
          total={total}
          offset={offset}
          limit={limit}
          currency={currency}
          highlightSourceRow={activeSourceRow}
          onPageChange={onPageChange}
          onInspectEvidence={onInspectEvidence}
        >
          {children}
        </BankDashboardView>
      )}

      {/* AI Financial Executive Summary Panel (Person 4 Component Mount) */}
      <FinancialSummaryMount
        workspaceId={workspaceId}
        SummaryComponent={SummaryComponent}
        onNavigateChat={onNavigate ? () => onNavigate('chat') : null}
      />
    </main>
  );
}

export default DashboardPage;
