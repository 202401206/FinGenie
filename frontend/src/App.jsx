import React, { useState, useEffect } from 'react';
import { LoginPage } from './features/auth/LoginPage.jsx';
import { SignUpPage } from './features/auth/SignUpPage.jsx';
import { TransactionHistoryPage } from './features/transactions/TransactionHistoryPage.jsx';
import { TransactionDetailDrawer } from './features/transactions/TransactionDetailDrawer.jsx';
import { Sidebar } from './components/layout/Sidebar.jsx';
import { TopNav } from './components/layout/TopNav.jsx';
import { adaptTransactionList } from './utils/transactionAdapter.js';
import { supabase, signOutUser } from './services/auth.js';

const DEMO_TRANSACTIONS = [
  { id: '1', date: '2026-10-24', description: 'UPI/Zomato Media Ltd/Order-94821', debit: 649.00, credit: null, balance: 142350.50, source_row: 142 },
  { id: '2', date: '2026-10-22', description: 'TCS LTD / OCT SALARY / CMS NEFT', debit: null, credit: 125000.00, balance: 142999.50, source_row: 141 },
  { id: '3', date: '2026-10-15', description: 'RENT PAYMENT TO LANDLORD S BALAJI', debit: 28000.00, credit: null, balance: 45419.50, source_row: 140 }
];

export function App() {
  const [view, setView] = useState('login'); // 'login' | 'signup' | 'app'
  const [activeTab, setActiveTab] = useState('transactions');
  const [session, setSession] = useState(null);
  const [isDemoMode, setIsDemoMode] = useState(false);
  const [selectedTx, setSelectedTx] = useState(null);

  useEffect(() => {
    if (supabase) {
      supabase.auth.getSession().then(({ data: { session } }) => {
        if (session) {
          setSession(session);
          setView('app');
        }
      });
      const { data: { subscription } } = supabase.auth.onAuthStateChange((_event, session) => {
        if (session) {
          setSession(session);
          setView('app');
        } else if (!isDemoMode) {
          setSession(null);
          setView('login');
        }
      });
      return () => subscription.unsubscribe();
    }
  }, [isDemoMode]);

  const handleLogout = async () => {
    await signOutUser();
    setSession(null);
    setIsDemoMode(false);
    setView('login');
  };

  const adaptedList = adaptTransactionList(DEMO_TRANSACTIONS, { filename: 'HDFC_Statement_Oct2026.csv', currency: 'INR' });

  if (view === 'login') {
    return (
      <LoginPage
        onLoginSuccess={(sess) => { setSession(sess); setView('app'); }}
        onEnableDemoMode={() => { setIsDemoMode(true); setView('app'); }}
        onNavigateSignUp={() => setView('signup')}
      />
    );
  }

  if (view === 'signup') {
    return (
      <SignUpPage
        onSignUpSuccess={(sess) => { setSession(sess); setView('app'); }}
        onNavigateLogin={() => setView('login')}
      />
    );
  }

  return (
    <div style={{ display: 'flex', minHeight: '100vh', width: '100%' }}>
      <Sidebar
        activeTab={activeTab}
        onNavigate={setActiveTab}
        onLogout={handleLogout}
        user={session?.user || (isDemoMode ? { email: 'Demo User (Preview)' } : null)}
      />
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column' }}>
        <TopNav title={activeTab.charAt(0).toUpperCase() + activeTab.slice(1)} documentName="HDFC_Statement_Oct2026.csv" />
        <main style={{ flex: 1, overflowY: 'auto' }}>
          {activeTab === 'transactions' ? (
            <TransactionHistoryPage
              transactions={adaptedList}
              documentMetadata={{ filename: 'HDFC_Statement_Oct2026.csv', currency: 'INR' }}
              analysisKpis={{ total_inflow: 125000, total_outflow: 28649, closing_balance: 142350.50 }}
              onSelectTransaction={setSelectedTx}
            />
          ) : (
            <div style={{ padding: '48px', textAlign: 'center' }}>
              <h2>{activeTab.toUpperCase()} Section</h2>
              <p style={{ color: 'var(--fg-muted-grey)' }}>Select Transactions in the sidebar to view the high-density ledger.</p>
            </div>
          )}
        </main>
      </div>

      <TransactionDetailDrawer
        transaction={selectedTx}
        isOpen={Boolean(selectedTx)}
        onClose={() => setSelectedTx(null)}
      />
    </div>
  );
}
