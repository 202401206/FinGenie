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

export function App() {
  const { session, user, loading, signOut } = useAuth();
  const [authView, setAuthView] = useState('login'); // 'login' | 'signup'
  const [activePage, setActivePage] = useState('home'); // 'home' | 'transactions' | 'dashboard' | 'assistant' | 'chat-history' | 'settings'
  const [isDemoMode, setIsDemoMode] = useState(false);

  // Selected workspace and transaction ledger state
  const [selectedWorkspaceId, setSelectedWorkspaceId] = useState(null);
  const [selectedWorkspace, setSelectedWorkspace] = useState(null);
  const [documentMetadata, setDocumentMetadata] = useState(null);
  const [transactions, setTransactions] = useState([]);
  const [totalTransactions, setTotalTransactions] = useState(0);
  const [transactionsOffset, setTransactionsOffset] = useState(0);
  const transactionsLimit = 50;

  const [ledgerLoading, setLedgerLoading] = useState(false);
  const [ledgerError, setLedgerError] = useState(null);
  const [selectedTx, setSelectedTx] = useState(null);

  // Stale request guard ref
  const activeRequestIdRef = useRef(0);

  // Clear financial state on account change or logout
  const currentUserId = user?.id || null;
  useEffect(() => {
    setSelectedWorkspaceId(null);
    setSelectedWorkspace(null);
    setDocumentMetadata(null);
    setTransactions([]);
    setTotalTransactions(0);
    setTransactionsOffset(0);
    setLedgerError(null);
    setSelectedTx(null);
    setIsDemoMode(false);
    activeRequestIdRef.current += 1;
  }, [currentUserId]);

  const loadWorkspaceLedger = useCallback(async (workspaceId, offset = 0) => {
    if (!workspaceId) return;

    const requestId = ++activeRequestIdRef.current;
    setLedgerLoading(true);
    setLedgerError(null);

    try {
      // 1. Load workspace details and document metadata
      const details = await getWorkspaceDetail(workspaceId);
      if (activeRequestIdRef.current !== requestId) return;

      const ws = details?.workspace || null;
      setSelectedWorkspace(ws);

      // Only parsed documents represent completed processing per Sprint 1 spec
      const parsedDoc = Array.isArray(details?.documents)
        ? details.documents.find(d => d.status === 'parsed') || details.documents[0]
        : null;

      const docMeta = parsedDoc ? {
        id: parsedDoc.id,
        original_filename: parsedDoc.original_filename,
        currency: parsedDoc.currency || null,
        status: parsedDoc.status,
        period_start: parsedDoc.period_start,
        period_end: parsedDoc.period_end
      } : {
        original_filename: ws?.name || 'Workspace Document',
        currency: null,
        status: 'parsed'
      };

      setDocumentMetadata(docMeta);

      // 2. Load paginated transactions from backend
      const txPage = await getWorkspaceTransactions(workspaceId, transactionsLimit, offset);
      if (activeRequestIdRef.current !== requestId) return;

      const rawItems = Array.isArray(txPage?.items) ? txPage.items : [];
      const totalCount = typeof txPage?.total === 'number' ? txPage.total : rawItems.length;

      const adapted = adaptTransactionList(rawItems, docMeta);
      setTransactions(adapted);
      setTotalTransactions(totalCount);
      setTransactionsOffset(offset);
      setLedgerLoading(false);
    } catch (err) {
      if (activeRequestIdRef.current !== requestId) return;
      setLedgerLoading(false);
      if (err.status === 404) {
        setLedgerError('Workspace unavailable or not found. It may belong to another user or have been removed.');
      } else {
        setLedgerError(err.message || 'Failed to load workspace transactions.');
      }
    }
  }, [transactionsLimit]);

  // When a workspace is selected (from Upload page or Recent Documents list)
  const handleSelectWorkspace = (workspaceId, workspaceData = null) => {
    setSelectedWorkspaceId(workspaceId);
    if (workspaceData) setSelectedWorkspace(workspaceData);
    setTransactionsOffset(0);
    setActivePage('transactions');
    loadWorkspaceLedger(workspaceId, 0);
  };

  const handlePageChange = (newOffset) => {
    if (isDemoMode) {
      setTransactionsOffset(newOffset);
      return;
    }
    if (selectedWorkspaceId) {
      loadWorkspaceLedger(selectedWorkspaceId, newOffset);
    }
  };

  const handleLogout = async () => {
    setIsDemoMode(false);
    setSelectedWorkspaceId(null);
    setSelectedWorkspace(null);
    setDocumentMetadata(null);
    setTransactions([]);
    setSelectedTx(null);
    await signOut();
  };

  if (loading) {
    return (
      <div style={{ display: 'flex', height: '100vh', alignItems: 'center', justifyContent: 'center', background: '#F4F7F5', color: '#18352F', fontFamily: 'sans-serif' }}>
        <div>Loading FinGenie authentication...</div>
      </div>
    );
  }

  // If not logged in and not in demo mode, show Auth flow
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

  // Prepared demo transactions ONLY when in explicit demo mode
  const demoList = adaptTransactionList(DEMO_TRANSACTIONS, {
    original_filename: 'HDFC_Statement_Oct2026.csv',
    currency: 'INR',
    status: 'parsed'
  });

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
              documentMetadata={{ original_filename: 'HDFC_Statement_Oct2026.csv', currency: 'INR', status: 'parsed' }}
              analysisKpis={{ total_inflow: 125000, total_outflow: 28649, closing_balance: 142350.50 }}
              onSelectTransaction={setSelectedTx}
              onNavigateUpload={() => setActivePage('home')}
            />
          );
        }

        if (!selectedWorkspaceId) {
          return (
            <div style={{ padding: '64px 32px', textAlign: 'center' }}>
              <div style={{ maxWidth: '480px', margin: '0 auto', background: 'white', padding: '36px', borderRadius: '12px', border: '1px solid #e5ebe7' }}>
                <div style={{ fontSize: '32px', marginBottom: '12px' }}>📊</div>
                <h2 style={{ fontSize: '20px', fontWeight: 700, margin: '0 0 8px 0', color: '#18352f' }}>No workspace selected</h2>
                <p style={{ color: '#66776d', fontSize: '14px', lineHeight: 1.5, margin: '0 0 20px 0' }}>
                  Please upload a bank statement or select an existing workspace from your Recent Documents to inspect its transactions ledger.
                </p>
                <button
                  type="button"
                  onClick={() => setActivePage('home')}
                  style={{
                    background: '#1d8a60',
                    color: 'white',
                    border: 'none',
                    padding: '10px 18px',
                    borderRadius: '8px',
                    fontWeight: 600,
                    cursor: 'pointer'
                  }}
                >
                  Go to Upload / Recent Documents →
                </button>
              </div>
            </div>
          );
        }

        return (
          <TransactionHistoryPage
            transactions={transactions}
            total={totalTransactions}
            offset={transactionsOffset}
            limit={transactionsLimit}
            loading={ledgerLoading}
            error={ledgerError}
            documentMetadata={documentMetadata || { original_filename: selectedWorkspace?.name || 'Workspace Document', currency: null }}
            analysisKpis={null}
            onPageChange={handlePageChange}
            onSelectTransaction={setSelectedTx}
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
        isOpen={Boolean(selectedTx)}
        onClose={() => setSelectedTx(null)}
      />
    </>
  );
}

export default App;
