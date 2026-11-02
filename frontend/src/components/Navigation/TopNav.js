/**
 * FinGenie Top Navigation Bar Component
 * Contextual breadcrumbs, active bank indicator, global search, and upload trigger
 */

export function renderTopNav({ title = 'Transactions', bankName = 'HDFC Bank', statementName = 'HDFC_Statement_Oct2026.csv', onSearch, onUploadClick }) {
  return `
    <header class="fg-topnav" style="
      height: var(--topbar-height);
      background: var(--fg-pure-white);
      border-bottom: 1px solid var(--fg-light-grey-green);
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 0 32px;
      position: sticky;
      top: 0;
      z-index: 30;
    ">
      <!-- Left: Breadcrumb & Title -->
      <div style="display: flex; align-items: center; gap: 16px;">
        <div>
          <div style="display: flex; align-items: center; gap: 8px; font-size: 12px; color: var(--fg-muted-grey); margin-bottom: 2px;">
            <span>FinGenie</span>
            <span>/</span>
            <span style="color: var(--fg-charcoal); font-weight: 500;">${title}</span>
          </div>
          <h1 style="margin: 0; font-size: 20px; font-weight: 700; color: var(--fg-charcoal); letter-spacing: -0.3px;">
            ${title}
          </h1>
        </div>

        <!-- Active Document / Bank Context Badge -->
        <div style="
          display: flex;
          align-items: center;
          gap: 8px;
          background: #F0F5F2;
          border: 1px solid var(--fg-light-grey-green);
          padding: 6px 12px;
          border-radius: var(--radius-pill);
          font-size: 12px;
          font-weight: 500;
          color: var(--fg-forest-green);
        ">
          <span style="width: 8px; height: 8px; border-radius: 50%; background: var(--fg-emerald-green);"></span>
          <span>${bankName}</span>
          <span style="color: var(--fg-muted-grey);">•</span>
          <span style="color: var(--fg-muted-grey);">${statementName}</span>
        </div>
      </div>

      <!-- Right: Global Search, Notifications, Primary Action -->
      <div style="display: flex; align-items: center; gap: 16px;">
        <!-- Global Search Bar -->
        <div style="position: relative; width: 260px;">
          <input 
            type="text" 
            id="fg-global-search"
            placeholder="Search records, UPI, tags..." 
            oninput="window.fgHandleGlobalSearch(this.value)"
            style="
              width: 100%;
              box-sizing: border-box;
              padding: 8px 12px 8px 34px;
              background: var(--fg-warm-white);
              border: 1px solid var(--fg-light-grey-green);
              border-radius: var(--radius-md);
              font-size: 13px;
              color: var(--fg-charcoal);
              outline: none;
              transition: all var(--transition-fast);
            "
            onfocus="this.style.borderColor='var(--fg-emerald-green)'; this.style.background='#fff';"
            onblur="this.style.borderColor='var(--fg-light-grey-green)'; this.style.background='var(--fg-warm-white)';"
          />
          <svg style="position: absolute; left: 10px; top: 9px; color: var(--fg-muted-grey);" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <circle cx="11" cy="11" r="8"></circle>
            <line x1="21" y1="21" x2="16.65" y2="16.65"></line>
          </svg>
        </div>

        <!-- Notifications Bell -->
        <button style="
          position: relative;
          background: none;
          border: 1px solid var(--fg-light-grey-green);
          border-radius: var(--radius-md);
          width: 38px;
          height: 38px;
          display: flex;
          align-items: center;
          justify-content: center;
          cursor: pointer;
          color: var(--fg-charcoal);
          background: var(--fg-pure-white);
        ">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"></path>
            <path d="M13.73 21a2 2 0 0 1-3.46 0"></path>
          </svg>
          <span style="
            position: absolute;
            top: 7px;
            right: 8px;
            width: 7px;
            height: 7px;
            border-radius: 50%;
            background: var(--fg-emerald-green);
            border: 2px solid white;
          "></span>
        </button>

        <!-- Primary CTA: Upload Statement -->
        <button onclick="window.fgOpenUploadModal()" class="fg-btn-primary" style="
          display: flex;
          align-items: center;
          gap: 8px;
          background: var(--fg-emerald-green);
          color: white;
          border: none;
          padding: 9px 16px;
          border-radius: var(--radius-md);
          font-size: 13px;
          font-weight: 600;
          cursor: pointer;
          box-shadow: 0 2px 6px rgba(29, 138, 96, 0.25);
          transition: background var(--transition-fast);
        " onmouseover="this.style.background='var(--fg-emerald-hover)'" onmouseout="this.style.background='var(--fg-emerald-green)'">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path>
            <polyline points="17 8 12 3 7 8"></polyline>
            <line x1="12" y1="3" x2="12" y2="15"></line>
          </svg>
          <span>Upload Statement</span>
        </button>
      </div>
    </header>
  `;
}
