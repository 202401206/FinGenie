import React, { useState, useEffect, useRef, useCallback } from 'react';
import { useAuth } from './hooks/useAuth.js';
import { LoginPage } from './features/auth/LoginPage.jsx';
import { SignUpPage } from './features/auth/SignUpPage.jsx';
import { TransactionHistoryPage } from './features/transactions/TransactionHistoryPage.jsx';
import { TransactionDetailDrawer } from './features/transactions/TransactionDetailDrawer.jsx';
import UploadPage from './features/upload/UploadPage.jsx';
import SettingsPage from './features/settings/SettingsPage.jsx';
import AppLayout from './components/layout/AppLayout.jsx';
import { getWorkspaceDetail, getWorkspaceTransactions } from './services/api.js';
import { adaptTransactionList } from './utils/transactionAdapter.js';

const DEMO_TRANSACTIONS = [
  { id: 'demo-1', date: '2026-10-24', description: 'UPI/Zomato Media Ltd/Order-94821', debit: 649.00, credit: null, balance: 142350.50, source_row: 142 },
  { id: 'demo-2', date: '2026-10-22', description: 'TCS LTD / OCT SALARY / CMS NEFT', debit: null, credit: 125000.00, balance: 142999.50, source_row: 141 },
  { id: 'demo-3', date: '2026-10-15', description: 'RENT PAYMENT TO LANDLORD S BALAJI', debit: 28000.00, credit: null, balance: 45419.50, source_row: 140 }
];

function PlaceholderPage({ title, description }) {
  return (
    <section className="fg-placeholder-page" style={{ padding: '64px 24px', textAlign: 'center' }}>
      <span style={{
        display: 'inline-block',
        fontSize: '11px',
        fontWeight: 700,
        color: '#1D8A60',
        background: '#E7F3EB',
        padding: '4px 10px',
        borderRadius: '20px',
        marginBottom: '12px',
        letterSpacing: '0.8px'
      }}>
        SPRINT 2 ROADMAP
      </span>
      <h2 style={{ fontSize: '22px', fontWeight: 700, margin: '8px 0', color: '#18352F' }}>{title}</h2>
      <p style={{ color: '#66776D', fontSize: '14px', maxWidth: '480px', margin: '0 auto 16px auto', lineHeight: 1.5 }}>
        {description}
      </p>
      <div style={{ fontSize: '12px', color: '#88998E' }}>
        This module is scheduled for Sprint 2 per team specification.
      </div>
    </section>
  );
}

/**
 * Ledger state: holds everything associated with one workspace+page load.
 * Published atomically so the UI never mixes results from different contexts.
 */
const EMPTY_LEDGER = {
  workspaceId: null,
  workspace: null,
  documentMetadata: null,
  transactions: [],
  total: 0,
  offset: 0,
  loading: false,
  error: null,
};

export function App() {
  const { session, user, loading, signOut } = useAuth();
  const [authView, setAuthView] = useState('login'); // 'login' | 'signup'
  const [activePage, setActivePage] = useState('home');
  const [isDemoMode, setIsDemoMode] = useState(false);

  // The drawer binds to the workspace it was opened from.
  // Clearing ledger also closes the drawer.
  const [selectedTx, setSelectedTx] = useState(null);
  const [ledgerCtxId, setLedgerCtxId] = useState(null); // workspace context the drawer belongs to

  // Single atomic ledger state — never partially updated across workspaces
  const [ledger, setLedger] = useState(EMPTY_LEDGER);

  // Request-generation counter: incremented on every new workspace selection,
  // account change, or unmount. Any response carrying an older generation is dropped.
  const requestGenRef = useRef(0);
  const transactionsLimit = 50;

  // ── Account boundary ────────────────────────────────────────────────────────
  // When the authenticated user ID changes (login, logout, account switch),
  // invalidate all in-flight requests and clear all workspace/ledger state.
  const currentUserId = user?.id ?? null;
  useEffect(() => {
    requestGenRef.current += 1;
    setLedger(EMPTY_LEDGER);
    setSelectedTx(null);
    setLedgerCtxId(null);
    setIsDemoMode(false);
  }, [currentUserId]);

  // ── Core ledger loader ───────────────────────────────────────────────────────
  const loadWorkspaceLedger = useCallback(async (workspaceId, offset = 0) => {
    if (!workspaceId) return;

    // Stamp this request so stale responses can be discarded
    const gen = ++requestGenRef.current;

    // Clear stale data immediately so the UI never shows old rows under a new workspace
    setLedger({
      ...EMPTY_LEDGER,
      workspaceId,
      loading: true,
    });
    setSelectedTx(null); // close any open drawer from the previous context

    try {
      // ── Step 1: workspace detail + document metadata ──────────────────────
      const details = await getWorkspaceDetail(workspaceId);

      // Drop if a newer request has started (account change or different workspace)
      if (requestGenRef.current !== gen) return;

      // Validate that the response has the expected shape
      if (!details || typeof details !== 'object') {
        setLedger({ ...EMPTY_LEDGER, workspaceId, error: 'Received an unexpected response from the server.' });
        return;
      }

      const ws = details.workspace ?? null;

      // Validate documents array — a missing or non-array field is a shape error, not "empty"
      if (!Array.isArray(details.documents)) {
        setLedger({ ...EMPTY_LEDGER, workspaceId, workspace: ws, error: 'Server response is missing document information.' });
        return;
      }

      // Determine document readiness
      // Per Sprint 1 spec, only 'parsed' status means processing is complete.
      const parsedDoc = details.documents.find(d => d.status === 'parsed') ?? null;
      const firstDoc  = details.documents[0] ?? null;

      let documentMetadata = null;
      let preError = null;

      if (details.documents.length === 0) {
        // No document associated — may be an interrupted upload
        preError = 'No document is available for this workspace. The upload may have been interrupted.';
      } else if (!parsedDoc) {
        // Document exists but is not yet parsed — represent the actual status
        const actualStatus = firstDoc?.status ?? 'unknown';
        if (actualStatus === 'failed') {
          preError = 'Document processing failed. Please upload a new statement or contact support.';
        } else {
          preError = `Document is not yet ready (status: ${actualStatus}). Sprint 1 has no background polling — please re-open this workspace later.`;
        }
        // Surface the real doc metadata even though it's not parsed, so the UI can show the filename
        documentMetadata = {
          id: firstDoc?.id ?? null,
          original_filename: firstDoc?.original_filename ?? null,
          currency: firstDoc?.currency ?? null,
          status: actualStatus,
          period_start: firstDoc?.period_start ?? null,
          period_end: firstDoc?.period_end ?? null,
        };
      } else {
        documentMetadata = {
          id: parsedDoc.id,
          original_filename: parsedDoc.original_filename,
          currency: parsedDoc.currency ?? null,
          status: parsedDoc.status,
          period_start: parsedDoc.period_start ?? null,
          period_end: parsedDoc.period_end ?? null,
        };
      }

      // If there's a doc readiness error, surface it and stop — do not attempt to load transactions
      if (preError) {
        setLedger({ ...EMPTY_LEDGER, workspaceId, workspace: ws, documentMetadata, error: preError });
        return;
      }

      // ── Step 2: paginated transactions ────────────────────────────────────
      const txPage = await getWorkspaceTransactions(workspaceId, transactionsLimit, offset);

      if (requestGenRef.current !== gen) return;

      // Validate transaction page shape — missing/non-array items is a shape error
      if (!txPage || typeof txPage !== 'object' || !Array.isArray(txPage.items)) {
        setLedger({ ...EMPTY_LEDGER, workspaceId, workspace: ws, documentMetadata, error: 'Server returned an unexpected transaction response shape.' });
        return;
      }

      const rawItems = txPage.items;
      const totalCount = typeof txPage.total === 'number' ? txPage.total : rawItems.length;
      const adapted = adaptTransactionList(rawItems, documentMetadata);

      // Publish workspace + document + transactions atomically
      setLedger({
        workspaceId,
        workspace: ws,
        documentMetadata,
        transactions: adapted,
        total: totalCount,
        offset,
        loading: false,
        error: null,
      });
      setLedgerCtxId(workspaceId);
    } catch (err) {
      if (requestGenRef.current !== gen) return;

      let errorMsg;
      if (err.status === 404) {
        errorMsg = 'Workspace not found. It may belong to another account or have been removed.';
      } else {
        errorMsg = err.message || 'Failed to load workspace data.';
      }

      // On error: clear rows — never show stale rows from a different workspace
      setLedger({ ...EMPTY_LEDGER, workspaceId, error: errorMsg });
    }
  }, [transactionsLimit]);

  // ── Workspace selection ─────────────────────────────────────────────────────
  const handleSelectWorkspace = useCallback((workspaceId) => {
    setActivePage('transactions');
    loadWorkspaceLedger(workspaceId, 0);
  }, [loadWorkspaceLedger]);

  // ── Page change ─────────────────────────────────────────────────────────────
  const handlePageChange = useCallback((newOffset) => {
    if (isDemoMode) {
      setLedger(prev => ({ ...prev, offset: newOffset }));
      return;
    }
    if (ledger.workspaceId) {
      loadWorkspaceLedger(ledger.workspaceId, newOffset);
    }
  }, [isDemoMode, ledger.workspaceId, loadWorkspaceLedger]);

  // ── Logout ──────────────────────────────────────────────────────────────────
  const handleLogout = async () => {
    requestGenRef.current += 1;
    setIsDemoMode(false);
    setLedger(EMPTY_LEDGER);
    setSelectedTx(null);
    setLedgerCtxId(null);
    await signOut();
  };

  // ── Auth loading screen ─────────────────────────────────────────────────────
  if (loading) {
    return (
      <div style={{ display: 'flex', height: '100vh', alignItems: 'center', justifyContent: 'center', background: '#F4F7F5', color: '#18352F', fontFamily: 'sans-serif' }}>
        <div>Loading FinGenie authentication...</div>
      </div>
    );
  }

  // ── Auth flow ───────────────────────────────────────────────────────────────
  if (!session && !isDemoMode) {
    if (authView === 'signup') {
      return (
        <SignUpPage
          onSignUpSuccess={() => setAuthView('login')}
          onNavigateLogin={() => setAuthView('login')}
        />
      );
    }
    return (
      <LoginPage
        onLoginSuccess={() => setAuthView('login')}
        onEnableDemoMode={() => setIsDemoMode(true)}
        onNavigateSignUp={() => setAuthView('signup')}
      />
    );
  }

  // ── Demo data (isolated from real workspace data) ───────────────────────────
  const demoDocMeta = { original_filename: 'HDFC_Statement_Oct2026.csv', currency: 'INR', status: 'parsed' };
  const demoList = adaptTransactionList(DEMO_TRANSACTIONS, demoDocMeta);

  // ── Page renderer ───────────────────────────────────────────────────────────
  function renderPageContent() {
    switch (activePage) {
      case 'home':
      case 'upload':
        return <UploadPage onSelectWorkspace={handleSelectWorkspace} />;

      case 'transactions':
        if (isDemoMode) {
          return (
            <TransactionHistoryPage
              transactions={demoList}
              total={demoList.length}
              offset={0}
              limit={50}
              documentMetadata={demoDocMeta}
              analysisKpis={{ total_inflow: 125000, total_outflow: 28649, closing_balance: 142350.50 }}
              onSelectTransaction={setSelectedTx}
              onNavigateUpload={() => setActivePage('home')}
            />
          );
        }

        if (!ledger.workspaceId) {
          return (
            <div style={{ padding: '64px 32px', textAlign: 'center' }}>
              <div style={{ maxWidth: '480px', margin: '0 auto', background: 'white', padding: '36px', borderRadius: '12px', border: '1px solid #e5ebe7' }}>
                <div style={{ fontSize: '32px', marginBottom: '12px' }}>📊</div>
                <h2 style={{ fontSize: '20px', fontWeight: 700, margin: '0 0 8px 0', color: '#18352f' }}>No workspace selected</h2>
                <p style={{ color: '#66776d', fontSize: '14px', lineHeight: 1.5, margin: '0 0 20px 0' }}>
                  Upload a bank statement or select an existing workspace from your Recent Documents.
                </p>
                <button
                  type="button"
                  onClick={() => setActivePage('home')}
                  style={{ background: '#1d8a60', color: 'white', border: 'none', padding: '10px 18px', borderRadius: '8px', fontWeight: 600, cursor: 'pointer' }}
                >
                  Go to Upload / Recent Documents →
                </button>
              </div>
            </div>
          );
        }

        return (
          <TransactionHistoryPage
            transactions={ledger.transactions}
            total={ledger.total}
            offset={ledger.offset}
            limit={transactionsLimit}
            loading={ledger.loading}
            error={ledger.error}
            documentMetadata={ledger.documentMetadata}
            analysisKpis={null}
            onPageChange={handlePageChange}
            onSelectTransaction={(tx) => {
              setSelectedTx(tx);
              setLedgerCtxId(ledger.workspaceId);
            }}
            onNavigateUpload={() => setActivePage('home')}
          />
        );

      case 'settings':
        return <SettingsPage />;

      case 'dashboard':
        return (
          <PlaceholderPage
            title="Financial Dashboard"
            description="Visual balance trends, income/expense distributions, and category breakdowns will appear here."
          />
        );

      case 'assistant':
        return (
          <PlaceholderPage
            title="AI Financial Assistant"
            description="Ask conversational questions about your financial statements and receive verified numeric insights."
          />
        );

      case 'chat-history':
        return (
          <PlaceholderPage
            title="Audit & Chat History"
            description="Your past AI questions and calculation provenance traces will be stored here."
          />
        );

      default:
        return <UploadPage onSelectWorkspace={handleSelectWorkspace} />;
    }
  }

  // The drawer is only shown when its context matches the currently loaded workspace.
  // Switching workspaces clears selectedTx which closes the drawer automatically.
  const drawerOpen = Boolean(selectedTx) && (!ledger.workspaceId || ledgerCtxId === ledger.workspaceId);

  return (
    <>
      <AppLayout
        activePage={activePage}
        onNavigate={setActivePage}
        user={user || (isDemoMode ? { email: 'Demo Mode (Preview)' } : null)}
        onLogout={handleLogout}
      >
        {renderPageContent()}
      </AppLayout>

      <TransactionDetailDrawer
        transaction={selectedTx}
        isOpen={drawerOpen}
        onClose={() => setSelectedTx(null)}
      />
    </>
  );
}

export default App;
