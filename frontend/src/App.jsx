import React, { useState } from 'react';
import { useAuth } from './hooks/useAuth.js';
import { LoginPage } from './features/auth/LoginPage.jsx';
import { SignUpPage } from './features/auth/SignUpPage.jsx';
import { TransactionHistoryPage } from './features/transactions/TransactionHistoryPage.jsx';
import { TransactionDetailDrawer } from './features/transactions/TransactionDetailDrawer.jsx';
import { Sidebar } from './components/layout/Sidebar.jsx';
import { TopNav } from './components/layout/TopNav.jsx';
import { adaptTransactionList } from './utils/transactionAdapter.js';

const DEMO_TRANSACTIONS = [
  { id: '1', date: '2026-10-24', description: 'UPI/Zomato Media Ltd/Order-94821', debit: 649.00, credit: null, balance: 142350.50, source_row: 142 },
  { id: '2', date: '2026-10-22', description: 'TCS LTD / OCT SALARY / CMS NEFT', debit: null, credit: 125000.00, balance: 142999.50, source_row: 141 },
  { id: '3', date: '2026-10-15', description: 'RENT PAYMENT TO LANDLORD S BALAJI', debit: 28000.00, credit: null, balance: 45419.50, source_row: 140 }
];

export function App() {
  const { session, user, loading, signOut } = useAuth();
  const [view, setView] = useState('app'); // 'app' | 'signup'
  const [activeTab, setActiveTab] = useState('transactions');
  const [isDemoMode, setIsDemoMode] = useState(false);
  const [selectedTx, setSelectedTx] = useState(null);

  if (loading) {
    return (
      <div style={{ display: 'flex', height: '100vh', alignItems: 'center', justifyContent: 'center' }}>
        <div>Loading FinGenie authentication...</div>
      </div>
    );
  }

  // If not logged in and not explicitly in demo mode, show Login/Signup
  if (!session && !isDemoMode) {
    if (view === 'signup') {
      return (
        <SignUpPage
          onSignUpSuccess={() => setView('app')}
          onNavigateLogin={() => setView('app')}
        />
      );
    }
    return (
      <LoginPage
        onLoginSuccess={() => setView('app')}
        onEnableDemoMode={() => setIsDemoMode(true)}
        onNavigateSignUp={() => setView('signup')}
      />
    );
  }

  const handleLogout = async () => {
    setIsDemoMode(false);
    await signOut();
  };

  const adaptedList = adaptTransactionList(DEMO_TRANSACTIONS, { filename: 'HDFC_Statement_Oct2026.csv', currency: 'INR' });

  return (
    <div style={{ display: 'flex', minHeight: '100vh', width: '100%' }}>
      <Sidebar
        activeTab={activeTab}
        onNavigate={setActiveTab}
        onLogout={handleLogout}
        user={user || (isDemoMode ? { email: 'Demo Mode (Preview)' } : null)}
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
