/**
 * FinGenie Persistent Sidebar Navigation Component
 * 240px fixed/sticky width, 8px grid, active state highlighting
 */

export function renderSidebar({ activeTab = 'transactions', user = null, onNavigate, onLogout }) {
  const currentTab = activeTab.toLowerCase();
  const userName = (user && user.profile && user.profile.full_name) || 'Aditya Sharma';
  const accountType = (user && user.profile && user.profile.account_type) || 'Personal';
  const bankName = (user && user.profile && user.profile.bank_name) || 'HDFC Bank';

  return `
    <aside class="fg-sidebar" style="
      width: var(--sidebar-width);
      height: 100vh;
      background: var(--fg-pure-white);
      border-right: 1px solid var(--fg-light-grey-green);
      display: flex;
      flex-direction: column;
      position: sticky;
      top: 0;
      flex-shrink: 0;
      z-index: 40;
    ">
      <!-- FinGenie Brand Header -->
      <div style="padding: 24px 20px 20px 20px; display: flex; align-items: center; gap: 12px; border-bottom: 1px solid var(--fg-warm-white);">
        <div style="
          width: 38px;
          height: 38px;
          background: linear-gradient(135deg, var(--fg-forest-green) 0%, var(--fg-emerald-green) 100%);
          border-radius: 10px;
          display: flex;
          align-items: center;
          justify-content: center;
          color: white;
          box-shadow: 0 4px 10px rgba(29, 138, 96, 0.25);
        ">
          <!-- Abstract Financial Trajectory SVG Icon -->
          <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
            <polyline points="22 7 13.5 15.5 8.5 10.5 2 17"></polyline>
            <polyline points="16 7 22 7 22 13"></polyline>
          </svg>
        </div>
        <div>
          <div style="font-weight: 700; font-size: 19px; letter-spacing: -0.5px; color: var(--fg-forest-green); line-height: 1.1;">
            FinGenie
          </div>
          <div style="font-size: 11px; color: var(--fg-muted-grey); font-weight: 500; letter-spacing: 0.3px;">
            INTELLIGENT FINANCE
          </div>
        </div>
      </div>

      <!-- Main Navigation Menu -->
      <nav style="flex: 1; padding: 20px 12px; overflow-y: auto;">
        <div style="font-size: 11px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.8px; color: var(--fg-muted-grey); padding: 0 12px 10px 12px;">
          WORKSPACE
        </div>

        <ul style="list-style: none; padding: 0; margin: 0; display: flex; flex-direction: column; gap: 4px;">
          <!-- 1. Home -->
          <li>
            <button onclick="window.fgNavigate('home')" class="fg-nav-item ${currentTab === 'home' ? 'active' : ''}" style="
              width: 100%;
              display: flex;
              align-items: center;
              gap: 12px;
              padding: 10px 14px;
              border-radius: var(--radius-md);
              font-size: 14px;
              font-weight: ${currentTab === 'home' ? '600' : '500'};
              color: ${currentTab === 'home' ? 'var(--fg-emerald-green)' : 'var(--fg-charcoal)'};
              background: ${currentTab === 'home' ? 'var(--fg-pale-mint)' : 'transparent'};
              border: none;
              cursor: pointer;
              text-align: left;
              transition: all var(--transition-fast);
            ">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"></path>
                <polyline points="9 22 9 12 15 12 15 22"></polyline>
              </svg>
              <span>Home</span>
            </button>
          </li>

          <!-- 2. Financial Dashboard -->
          <li>
            <button onclick="window.fgNavigate('dashboard')" class="fg-nav-item ${currentTab === 'dashboard' ? 'active' : ''}" style="
              width: 100%;
              display: flex;
              align-items: center;
              gap: 12px;
              padding: 10px 14px;
              border-radius: var(--radius-md);
              font-size: 14px;
              font-weight: ${currentTab === 'dashboard' ? '600' : '500'};
              color: ${currentTab === 'dashboard' ? 'var(--fg-emerald-green)' : 'var(--fg-charcoal)'};
              background: ${currentTab === 'dashboard' ? 'var(--fg-pale-mint)' : 'transparent'};
              border: none;
              cursor: pointer;
              text-align: left;
              transition: all var(--transition-fast);
            ">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <rect x="3" y="3" width="7" height="9"></rect>
                <rect x="14" y="3" width="7" height="5"></rect>
                <rect x="14" y="12" width="7" height="9"></rect>
                <rect x="3" y="16" width="7" height="5"></rect>
              </svg>
              <span>Financial Dashboard</span>
            </button>
          </li>

          <!-- 3. Transactions (Active ledger) -->
          <li>
            <button onclick="window.fgNavigate('transactions')" class="fg-nav-item ${currentTab === 'transactions' ? 'active' : ''}" style="
              width: 100%;
              display: flex;
              align-items: center;
              gap: 12px;
              padding: 10px 14px;
              border-radius: var(--radius-md);
              font-size: 14px;
              font-weight: ${currentTab === 'transactions' ? '600' : '500'};
              color: ${currentTab === 'transactions' ? 'var(--fg-emerald-green)' : 'var(--fg-charcoal)'};
              background: ${currentTab === 'transactions' ? 'var(--fg-pale-mint)' : 'transparent'};
              border: none;
              cursor: pointer;
              text-align: left;
              transition: all var(--transition-fast);
            ">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <line x1="8" y1="6" x2="21" y2="6"></line>
                <line x1="8" y1="12" x2="21" y2="12"></line>
                <line x1="8" y1="18" x2="21" y2="18"></line>
                <line x1="3" y1="6" x2="3.01" y2="6"></line>
                <line x1="3" y1="12" x2="3.01" y2="12"></line>
                <line x1="3" y1="18" x2="3.01" y2="18"></line>
              </svg>
              <span>Transactions</span>
              ${currentTab === 'transactions' ? `
                <span style="margin-left: auto; width: 6px; height: 6px; border-radius: 50%; background: var(--fg-emerald-green);"></span>
              ` : ''}
            </button>
          </li>

          <!-- 4. AI Assistant -->
          <li>
            <button onclick="window.fgNavigate('assistant')" class="fg-nav-item ${currentTab === 'assistant' ? 'active' : ''}" style="
              width: 100%;
              display: flex;
              align-items: center;
              gap: 12px;
              padding: 10px 14px;
              border-radius: var(--radius-md);
              font-size: 14px;
              font-weight: ${currentTab === 'assistant' ? '600' : '500'};
              color: ${currentTab === 'assistant' ? 'var(--fg-emerald-green)' : 'var(--fg-charcoal)'};
              background: ${currentTab === 'assistant' ? 'var(--fg-pale-mint)' : 'transparent'};
              border: none;
              cursor: pointer;
              text-align: left;
              transition: all var(--transition-fast);
            ">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <path d="M21 11.5a8.38 8.38 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.38 8.38 0 0 1-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.38 8.38 0 0 1 3.8-.9h.5a8.48 8.48 0 0 1 8 8v.5z"></path>
              </svg>
              <span>AI Assistant</span>
            </button>
          </li>

          <!-- 5. Chat History -->
          <li>
            <button onclick="window.fgNavigate('chats')" class="fg-nav-item ${currentTab === 'chats' ? 'active' : ''}" style="
              width: 100%;
              display: flex;
              align-items: center;
              gap: 12px;
              padding: 10px 14px;
              border-radius: var(--radius-md);
              font-size: 14px;
              font-weight: ${currentTab === 'chats' ? '600' : '500'};
              color: ${currentTab === 'chats' ? 'var(--fg-emerald-green)' : 'var(--fg-charcoal)'};
              background: ${currentTab === 'chats' ? 'var(--fg-pale-mint)' : 'transparent'};
              border: none;
              cursor: pointer;
              text-align: left;
              transition: all var(--transition-fast);
            ">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <circle cx="12" cy="12" r="10"></circle>
                <polyline points="12 6 12 12 16 14"></polyline>
              </svg>
              <span>Chat History</span>
            </button>
          </li>
        </ul>

        <!-- Divider -->
        <hr style="border: none; border-top: 1px solid var(--fg-light-grey-green); margin: 20px 8px;" />

        <div style="font-size: 11px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.8px; color: var(--fg-muted-grey); padding: 0 12px 10px 12px;">
          PREFERENCES
        </div>

        <ul style="list-style: none; padding: 0; margin: 0; display: flex; flex-direction: column; gap: 4px;">
          <!-- 6. Settings -->
          <li>
            <button onclick="window.fgNavigate('settings')" class="fg-nav-item ${currentTab === 'settings' ? 'active' : ''}" style="
              width: 100%;
              display: flex;
              align-items: center;
              gap: 12px;
              padding: 10px 14px;
              border-radius: var(--radius-md);
              font-size: 14px;
              font-weight: ${currentTab === 'settings' ? '600' : '500'};
              color: ${currentTab === 'settings' ? 'var(--fg-emerald-green)' : 'var(--fg-charcoal)'};
              background: ${currentTab === 'settings' ? 'var(--fg-pale-mint)' : 'transparent'};
              border: none;
              cursor: pointer;
              text-align: left;
              transition: all var(--transition-fast);
            ">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <circle cx="12" cy="12" r="3"></circle>
                <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"></path>
              </svg>
              <span>Settings</span>
            </button>
          </li>

          <!-- 7. Help and Support -->
          <li>
            <button onclick="window.fgNavigate('help')" class="fg-nav-item ${currentTab === 'help' ? 'active' : ''}" style="
              width: 100%;
              display: flex;
              align-items: center;
              gap: 12px;
              padding: 10px 14px;
              border-radius: var(--radius-md);
              font-size: 14px;
              font-weight: ${currentTab === 'help' ? '600' : '500'};
              color: ${currentTab === 'help' ? 'var(--fg-emerald-green)' : 'var(--fg-charcoal)'};
              background: ${currentTab === 'help' ? 'var(--fg-pale-mint)' : 'transparent'};
              border: none;
              cursor: pointer;
              text-align: left;
              transition: all var(--transition-fast);
            ">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <circle cx="12" cy="12" r="10"></circle>
                <path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3"></path>
                <line x1="12" y1="17" x2="12.01" y2="17"></line>
              </svg>
              <span>Help & Support</span>
            </button>
          </li>
        </ul>
      </nav>

      <!-- Bottom User Profile Card -->
      <div style="padding: 16px; border-top: 1px solid var(--fg-light-grey-green); background: #FAFBF9;">
        <div style="display: flex; align-items: center; justify-content: space-between;">
          <div style="display: flex; align-items: center; gap: 10px; min-width: 0;">
            <div style="
              width: 36px;
              height: 36px;
              border-radius: 50%;
              background: var(--fg-pale-mint);
              color: var(--fg-emerald-green);
              font-weight: 700;
              font-size: 13px;
              display: flex;
              align-items: center;
              justify-content: center;
              flex-shrink: 0;
              border: 1px solid rgba(29, 138, 96, 0.2);
            ">
              ${userName.split(' ').map(n => n[0]).join('').substring(0, 2).toUpperCase()}
            </div>
            <div style="min-width: 0;">
              <div style="font-size: 13px; font-weight: 600; color: var(--fg-charcoal); white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">
                ${userName}
              </div>
              <div style="font-size: 11px; color: var(--fg-muted-grey); display: flex; align-items: center; gap: 4px;">
                <span>${accountType}</span> • <span>${bankName}</span>
              </div>
            </div>
          </div>

          <button onclick="window.fgLogout()" title="Log out" style="
            background: none;
            border: none;
            color: var(--fg-muted-grey);
            cursor: pointer;
            padding: 6px;
            border-radius: var(--radius-sm);
            display: flex;
            align-items: center;
            justify-content: center;
            transition: color var(--transition-fast);
          ">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"></path>
              <polyline points="16 17 21 12 16 7"></polyline>
              <line x1="21" y1="12" x2="9" y2="12"></line>
            </svg>
          </button>
        </div>
      </div>
    </aside>
  `;
}
