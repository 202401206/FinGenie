import React, { useState } from 'react';
import { useAuth } from './hooks/useAuth.js';
import { LoginPage } from './features/auth/LoginPage.jsx';
import { SignUpPage } from './features/auth/SignUpPage.jsx';
import { TransactionHistoryPage } from './features/transactions/TransactionHistoryPage.jsx';
import { TransactionDetailDrawer } from './features/transactions/TransactionDetailDrawer.jsx';
import UploadPage from './features/upload/UploadPage.jsx';
import SettingsPage from './features/settings/SettingsPage.jsx';
import AppLayout from './components/layout/AppLayout.jsx';
import { adaptTransactionList } from './utils/transactionAdapter.js';

const DEMO_TRANSACTIONS = [
  { id: '1', date: '2026-10-24', description: 'UPI/Zomato Media Ltd/Order-94821', debit: 649.00, credit: null, balance: 142350.50, source_row: 142 },
  { id: '2', date: '2026-10-22', description: 'TCS LTD / OCT SALARY / CMS NEFT', debit: null, credit: 125000.00, balance: 142999.50, source_row: 141 },
  { id: '3', date: '2026-10-15', description: 'RENT PAYMENT TO LANDLORD S BALAJI', debit: 28000.00, credit: null, balance: 45419.50, source_row: 140 }
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
  const [selectedTx, setSelectedTx] = useState(null);

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

  const handleLogout = async () => {
    setIsDemoMode(false);
    await signOut();
  };

  const adaptedList = adaptTransactionList(DEMO_TRANSACTIONS, {
    filename: 'HDFC_Statement_Oct2026.csv',
    currency: 'INR'
  });

  function renderPageContent() {
    switch (activePage) {
      case 'home':
      case 'upload':
        return <UploadPage />;

      case 'transactions':
        return (
          <TransactionHistoryPage
            transactions={adaptedList}
            documentMetadata={{ filename: 'HDFC_Statement_Oct2026.csv', currency: 'INR' }}
            analysisKpis={{ total_inflow: 125000, total_outflow: 28649, closing_balance: 142350.50 }}
            onSelectTransaction={setSelectedTx}
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
        return <UploadPage />;
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
