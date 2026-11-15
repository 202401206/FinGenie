import React from 'react';
import Sidebar from './Sidebar.jsx';
import './AppLayout.css';

export const PAGE_INFO = {
  home: {
    title: 'Upload Bank Statement',
    subtitle: 'Upload your bank statement (CSV or XLSX) to parse records and generate financial insights'
  },
  transactions: {
    title: 'Transaction History & Ledger',
    subtitle: 'High-density verifiable ledger with multi-parameter filtering and row provenance'
  },
  dashboard: {
    title: 'Financial Dashboard',
    subtitle: 'Visual overview of your financial health, cash flows, and performance'
  },
  assistant: {
    title: 'AI Financial Assistant',
    subtitle: 'Conversational assistant with deterministic financial tools and number verification'
  },
  'chat-history': {
    title: 'Audit & Chat History',
    subtitle: 'Review historical questions, tool executions, and data provenance traces'
  },
  settings: {
    title: 'Settings',
    subtitle: 'Account preferences, format conventions, and workspace configuration'
  }
};

export function AppLayout({ activePage, onNavigate, user, onLogout, children }) {
  const pageInfo = PAGE_INFO[activePage] || PAGE_INFO.home;

  return (
    <div className="fg-app-layout">
      <Sidebar
        activePage={activePage}
        onNavigate={onNavigate}
        user={user}
        onLogout={onLogout}
      />

      <div className="fg-main-area">
        <header className="fg-topbar">
          <div className="fg-topbar-page-info">
            <h1>{pageInfo.title}</h1>
            <p>{pageInfo.subtitle}</p>
          </div>
        </header>

        <main className="fg-page-content">{children}</main>
      </div>
    </div>
  );
}

export default AppLayout;
