/**
 * FinGenie Main Application Controller & Reactive State Shell
 */

import { renderSidebar } from './components/Navigation/Sidebar.js';
import { renderTopNav } from './components/Navigation/TopNav.js';
import { renderLoginPage } from './components/Auth/LoginPage.js';
import { renderSignUpPage } from './components/Auth/SignUpPage.js';
import { renderTransactionHistoryPage } from './components/Transactions/TransactionHistoryPage.js';
import { renderTransactionDetailDrawer } from './components/Transactions/TransactionDetailDrawer.js';
import { 
  login, 
  signUp, 
  updateAccountType, 
  updateBankSelection, 
  completeOnboarding, 
  getCurrentSession, 
  logout 
} from './services/authService.js';
import { 
  filterTransactions, 
  sortTransactions, 
  paginateTransactions, 
  calculateFinancialKPIs, 
  exportTransactionsCSV,
  getTransactions 
} from './services/transactionService.js';

// Application Reactive State
const state = {
  view: 'transactions', // 'login' | 'signup' | 'transactions' | 'dashboard' | 'home' | 'assistant'
  activeTab: 'transactions',
  user: null,
  loginError: '',
  isLoggingIn: false,
  
  // Onboarding state
  signUpStep: 1,
  signUpFormData: { fullName: '', email: '', password: '', confirmPassword: '' },
  signUpAccountType: 'personal',
  signUpBankId: 'hdfc',
  signUpBankSearch: '',
  signUpError: '',

  // Transactions state
  rawTransactions: [],
  filteredTransactions: [],
  filters: {
    search: '',
    type: 'all',
    category: 'all',
    paymentMethod: 'all',
    minAmount: null,
    maxAmount: null
  },
  sortState: { sortBy: 'date', sortOrder: 'desc' },
  page: 1,
  pageSize: 6,
  selectedTransactionId: null,
  isDrawerOpen: false,

  // Toast notifications
  toastMessage: ''
};

// Global handlers attached to window for browser interactions
export async function initApp() {
  // Pre-load default session
  try {
    const sessionRes = await login({ email: 'demo@fingenie.app', password: 'Password@123' });
    state.user = sessionRes.user;
    state.rawTransactions = await getTransactions(state.user.id);
  } catch (err) {
    state.user = null;
    state.view = 'login';
  }

  window.fgNavigate = (tab) => {
    state.activeTab = tab;
    if (tab === 'login' || tab === 'signup') {
      state.view = tab;
    } else {
      state.view = tab;
    }
    renderApp();
  };

  window.fgSubmitLogin = async () => {
    const email = document.getElementById('login-email').value;
    const password = document.getElementById('login-password').value;
    state.isLoggingIn = true;
    state.loginError = '';
    renderApp();

    try {
      const res = await login({ email, password });
      state.user = res.user;
      state.view = 'transactions';
      state.activeTab = 'transactions';
      state.rawTransactions = await getTransactions(res.user.id);
      showToast(`Welcome back, ${res.user.profile.full_name}!`);
    } catch (e) {
      state.loginError = e.message;
    } finally {
      state.isLoggingIn = false;
      renderApp();
    }
  };

  window.fgLoginWithGoogle = async () => {
    showToast('Connecting to Google SSO...');
    setTimeout(async () => {
      const res = await login({ email: 'demo@fingenie.app', password: 'Password@123' });
      state.user = res.user;
      state.view = 'transactions';
      state.activeTab = 'transactions';
      renderApp();
    }, 600);
  };

  window.fgTogglePassword = (inputId, btn) => {
    const input = document.getElementById(inputId);
    if (!input) return;
    if (input.type === 'password') {
      input.type = 'text';
      btn.style.color = 'var(--fg-emerald-green)';
    } else {
      input.type = 'password';
      btn.style.color = 'var(--fg-muted-grey)';
    }
  };

  window.fgSubmitSignUpStep1 = async () => {
    const fullName = document.getElementById('su-fullname').value;
    const email = document.getElementById('su-email').value;
    const password = document.getElementById('su-password').value;
    const confirmPassword = document.getElementById('su-confirmpassword').value;
    const termsAccepted = document.getElementById('su-terms').checked;

    state.signUpFormData = { fullName, email, password, confirmPassword };
    state.signUpError = '';

    try {
      const res = await signUp({ fullName, email, password, confirmPassword, termsAccepted });
      state.user = res.user;
      state.signUpStep = 2;
      renderApp();
    } catch (e) {
      state.signUpError = e.message;
      renderApp();
    }
  };

  window.fgSelectAccountType = (type) => {
    state.signUpAccountType = type;
    renderApp();
  };

  window.fgConfirmAccountType = async () => {
    if (state.user) {
      await updateAccountType(state.user.id, state.signUpAccountType);
    }
    state.signUpStep = 3;
    renderApp();
  };

  window.fgFilterBanks = (query) => {
    state.signUpBankSearch = query;
    renderApp();
    const input = document.getElementById('bank-search-input');
    if (input) {
      input.focus();
      input.setSelectionRange(input.value.length, input.value.length);
    }
  };

  window.fgSelectBank = (bankId) => {
    state.signUpBankId = bankId;
    renderApp();
  };

  window.fgConfirmBankSelection = async () => {
    if (state.user) {
      await updateBankSelection(state.user.id, { bankId: state.signUpBankId });
      await completeOnboarding(state.user.id);
    }
    state.signUpStep = 4;
    renderApp();
  };

  window.fgGoToStep = (st) => {
    state.signUpStep = st;
    renderApp();
  };

  window.fgGoToDashboard = () => {
    state.view = 'transactions';
    state.activeTab = 'transactions';
    renderApp();
    showToast('Onboarding complete! Your ledger is ready.');
  };

  window.fgLogout = async () => {
    await logout();
    state.user = null;
    state.view = 'login';
    renderApp();
    showToast('Logged out securely.');
  };

  // Transaction Ledger Handlers
  window.fgApplyFilter = (key, val) => {
    state.filters[key] = val;
    state.page = 1; // reset to first page
    renderApp();
  };

  window.fgResetFilters = () => {
    state.filters = {
      search: '',
      type: 'all',
      category: 'all',
      paymentMethod: 'all',
      minAmount: null,
      maxAmount: null
    };
    state.page = 1;
    renderApp();
    showToast('Filters cleared.');
  };

  window.fgToggleSort = (sortBy) => {
    if (state.sortState.sortBy === sortBy) {
      state.sortState.sortOrder = state.sortState.sortOrder === 'asc' ? 'desc' : 'asc';
    } else {
      state.sortState.sortBy = sortBy;
      state.sortState.sortOrder = 'desc';
    }
    renderApp();
  };

  window.fgChangePage = (newPage) => {
    state.page = newPage;
    renderApp();
  };

  window.fgSelectTransaction = (txId) => {
    state.selectedTransactionId = txId;
    state.isDrawerOpen = true;
    renderApp();
  };

  window.fgCloseTransactionDrawer = () => {
    state.isDrawerOpen = false;
    renderApp();
  };

  window.fgAskAssistantAboutTx = (txId) => {
    state.isDrawerOpen = false;
    state.activeTab = 'assistant';
    state.view = 'assistant';
    renderApp();
    showToast(`Analyzing context for transaction #${txId}...`);
  };

  window.fgExportCSV = () => {
    const filtered = filterTransactions(state.rawTransactions, state.filters);
    const csvContent = exportTransactionsCSV(filtered);
    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.setAttribute('href', url);
    link.setAttribute('download', `FinGenie_Transactions_${Date.now()}.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    showToast('Exported CSV file successfully!');
  };

  window.fgOpenUploadModal = () => {
    showToast('Upload feature: select bank statement (CSV/XLSX)');
  };

  window.fgHandleGlobalSearch = (q) => {
    window.fgApplyFilter('search', q);
  };

  renderApp();
}

function showToast(msg) {
  state.toastMessage = msg;
  renderApp();
  setTimeout(() => {
    state.toastMessage = '';
    renderApp();
  }, 3200);
}

export function renderApp() {
  const root = document.getElementById('app-root');
  if (!root) return;

  // 1. Unauthenticated or Auth Views
  if (state.view === 'login') {
    root.innerHTML = renderLoginPage({
      error: state.loginError,
      isLoading: state.isLoggingIn
    });
    return;
  }

  if (state.view === 'signup') {
    root.innerHTML = renderSignUpPage({
      step: state.signUpStep,
      formData: state.signUpFormData,
      selectedAccountType: state.signUpAccountType,
      selectedBankId: state.signUpBankId,
      bankSearchQuery: state.signUpBankSearch,
      error: state.signUpError
    });
    return;
  }

  // 2. Authenticated Views (Sidebar + TopNav + Main Content Area)
  const filtered = filterTransactions(state.rawTransactions, state.filters);
  const sorted = sortTransactions(filtered, state.sortState);
  const paginated = paginateTransactions(sorted, { page: state.page, pageSize: state.pageSize });
  const kpis = calculateFinancialKPIs(filtered);
  const selectedTx = state.rawTransactions.find(t => t.id === state.selectedTransactionId);

  let mainContent = '';

  if (state.activeTab === 'transactions') {
    mainContent = renderTransactionHistoryPage({
      transactions: state.rawTransactions,
      paginatedData: paginated,
      kpis,
      filters: state.filters,
      sortState: state.sortState,
      selectedTransactionId: state.selectedTransactionId,
      activeBank: (state.user && state.user.profile && state.user.profile.bank_name) || 'HDFC Bank',
      activeDocument: 'HDFC_Statement_Oct2026.csv'
    });
  } else {
    // Elegant placeholder for Home, Dashboard, AI Assistant, etc.
    mainContent = `
      <div style="padding: 48px; text-align: center; max-width: 600px; margin: 40px auto;" class="fg-card">
        <div style="font-size: 36px; margin-bottom: 12px;">✨</div>
        <h2 style="font-size: 22px; font-weight: 700; color: var(--fg-charcoal); margin: 0 0 8px 0; text-transform: capitalize;">
          ${state.activeTab} Screen
        </h2>
        <p style="font-size: 14px; color: var(--fg-muted-grey); line-height: 1.6; margin: 0 0 20px 0;">
          The ${state.activeTab} view is fully integrated with FinGenie's design system. Switch back to the <strong>Transactions</strong> tab to explore the high-density financial ledger and interactive data provenance drawer.
        </p>
        <button onclick="window.fgNavigate('transactions')" class="fg-btn-primary" style="
          background: var(--fg-emerald-green); color: white; border: none; padding: 10px 20px; border-radius: var(--radius-md); font-weight: 600; cursor: pointer;
        ">
          Back to Transactions Ledger →
        </button>
      </div>
    `;
  }

  root.innerHTML = `
    <div style="display: flex; min-height: 100vh; width: 100%; background: var(--fg-warm-white);">
      <!-- Persistent 240px Sidebar -->
      ${renderSidebar({
        activeTab: state.activeTab,
        user: state.user
      })}

      <!-- Right Main Layout Area -->
      <div style="flex: 1; display: flex; flex-direction: column; min-width: 0; overflow-x: hidden;">
        <!-- Top Navigation Bar -->
        ${renderTopNav({
          title: state.activeTab === 'transactions' ? 'Transactions' : state.activeTab.charAt(0).toUpperCase() + state.activeTab.slice(1),
          bankName: (state.user && state.user.profile && state.user.profile.bank_name) || 'HDFC Bank'
        })}

        <!-- Main Workspace -->
        <main style="flex: 1; overflow-y: auto;">
          ${mainContent}
        </main>
      </div>

      <!-- Detail Drawer Modal -->
      ${renderTransactionDetailDrawer({
        transaction: selectedTx,
        isOpen: state.isDrawerOpen
      })}

      <!-- Toast Notification Alert -->
      ${state.toastMessage ? `
        <div style="
          position: fixed;
          bottom: 24px;
          right: 24px;
          background: var(--fg-forest-green);
          color: white;
          padding: 12px 20px;
          border-radius: var(--radius-md);
          font-size: 13px;
          font-weight: 500;
          box-shadow: var(--shadow-floating);
          z-index: 200;
          display: flex;
          align-items: center;
          gap: 10px;
          border: 1px solid rgba(255, 255, 255, 0.15);
          animation: fgSlideIn 200ms ease;
        ">
          <span style="color: #4ADE80;">✔</span>
          <span>${state.toastMessage}</span>
        </div>
      ` : ''}
    </div>
  `;
}
