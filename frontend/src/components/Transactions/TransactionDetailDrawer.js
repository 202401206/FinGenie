/**
 * FinGenie Transaction Detail Drawer Component
 * Right-side slide-out drawer providing 100% data provenance and AI verification
 */

import { formatINR, formatDate } from '../../utils/formatters.js';

export function renderTransactionDetailDrawer({ transaction = null, isOpen = false, onClose, onAskFinGenie }) {
  if (!isOpen || !transaction) return '';

  const isCredit = transaction.type === 'credit';

  return `
    <!-- Drawer Backdrop -->
    <div onclick="window.fgCloseTransactionDrawer()" style="
      position: fixed;
      top: 0;
      left: 0;
      width: 100vw;
      height: 100vh;
      background: rgba(16, 37, 30, 0.35);
      backdrop-filter: blur(2px);
      z-index: 100;
      animation: fgFadeIn 150ms ease-out;
    "></div>

    <!-- Right Drawer Surface -->
    <aside style="
      position: fixed;
      top: 0;
      right: 0;
      width: 440px;
      height: 100vh;
      background: var(--fg-pure-white);
      box-shadow: var(--shadow-drawer);
      z-index: 101;
      display: flex;
      flex-direction: column;
      animation: fgSlideIn 200ms cubic-bezier(0.16, 1, 0.3, 1);
      overflow-y: auto;
    ">
      <!-- Drawer Header -->
      <div style="padding: 24px; border-bottom: 1px solid var(--fg-light-grey-green); display: flex; justify-content: space-between; align-items: center;">
        <div>
          <div style="font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.8px; color: var(--fg-muted-grey);">
            RECORD INSPECTOR
          </div>
          <h3 style="margin: 4px 0 0 0; font-size: 18px; font-weight: 700; color: var(--fg-charcoal);">
            Transaction Detail
          </h3>
        </div>

        <button onclick="window.fgCloseTransactionDrawer()" style="
          background: none;
          border: 1px solid var(--fg-light-grey-green);
          border-radius: var(--radius-sm);
          width: 32px;
          height: 32px;
          display: flex;
          align-items: center;
          justify-content: center;
          cursor: pointer;
          color: var(--fg-muted-grey);
        ">
          ✕
        </button>
      </div>

      <!-- Drawer Content -->
      <div style="padding: 24px; flex: 1; display: flex; flex-direction: column; gap: 24px;">
        
        <!-- Big Value Card -->
        <div style="
          background: ${isCredit ? 'var(--fg-pale-mint)' : 'var(--fg-soft-red-light)'};
          border: 1px solid ${isCredit ? 'rgba(29, 138, 96, 0.25)' : 'rgba(201, 76, 76, 0.25)'};
          border-radius: var(--radius-card);
          padding: 20px;
          text-align: center;
        ">
          <div style="font-size: 12px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px; color: ${isCredit ? 'var(--fg-emerald-green)' : 'var(--fg-soft-red)'};">
            ${isCredit ? 'CREDIT / INFLOW' : 'DEBIT / OUTFLOW'}
          </div>
          <div style="font-size: 32px; font-weight: 700; color: ${isCredit ? 'var(--fg-emerald-green)' : 'var(--fg-soft-red)'}; margin: 6px 0;">
            ${isCredit ? '+' : '-'}${formatINR(transaction.amount)}
          </div>
          <div style="font-size: 12px; color: var(--fg-muted-grey);">
            Processed on ${formatDate(transaction.date)}
          </div>
        </div>

        <!-- Full Bank Narration Section -->
        <div>
          <label style="display: block; font-size: 12px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.5px; color: var(--fg-muted-grey); margin-bottom: 6px;">
            RAW STATEMENT NARRATION
          </label>
          <div style="
            background: var(--fg-warm-white);
            border: 1px solid var(--fg-light-grey-green);
            border-radius: var(--radius-md);
            padding: 12px 14px;
            font-size: 13px;
            font-family: monospace;
            color: var(--fg-charcoal);
            word-break: break-all;
            line-height: 1.5;
          ">
            ${transaction.description}
          </div>
        </div>

        <!-- Data Provenance & File Traceability per Prompt Standards -->
        <div class="fg-card" style="padding: 16px;">
          <div style="display: flex; align-items: center; gap: 6px; font-size: 12px; font-weight: 700; color: var(--fg-forest-green); margin-bottom: 12px;">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
              <polyline points="14 2 14 8 20 8"></polyline>
              <line x1="16" y1="13" x2="8" y2="13"></line>
              <line x1="16" y1="17" x2="8" y2="17"></line>
              <polyline points="10 9 9 9 8 9"></polyline>
            </svg>
            <span>AUDIT TRAIL & SOURCE PROVENANCE</span>
          </div>

          <div style="display: flex; flex-direction: column; gap: 10px; font-size: 13px;">
            <div style="display: flex; justify-content: space-between; border-bottom: 1px solid var(--fg-warm-white); padding-bottom: 6px;">
              <span style="color: var(--fg-muted-grey);">Source File</span>
              <strong style="color: var(--fg-charcoal);">${transaction.source_file}</strong>
            </div>
            <div style="display: flex; justify-content: space-between; border-bottom: 1px solid var(--fg-warm-white); padding-bottom: 6px;">
              <span style="color: var(--fg-muted-grey);">Excel/CSV Row</span>
              <span style="background: #E2E8F0; padding: 2px 6px; border-radius: 4px; font-family: monospace; font-size: 12px;">
                #row-${transaction.source_row}
              </span>
            </div>
            <div style="display: flex; justify-content: space-between; border-bottom: 1px solid var(--fg-warm-white); padding-bottom: 6px;">
              <span style="color: var(--fg-muted-grey);">Post-Transaction Balance</span>
              <strong style="color: var(--fg-charcoal);">${transaction.balance ? formatINR(transaction.balance) : 'N/A'}</strong>
            </div>
            <div style="display: flex; justify-content: space-between;">
              <span style="color: var(--fg-muted-grey);">Channel</span>
              <strong style="color: var(--fg-charcoal);">${transaction.payment_method}</strong>
            </div>
          </div>
        </div>

        <!-- AI Categorization vs Ground Truth -->
        <div style="
          border: 1px dashed ${transaction.ai_inferred ? 'var(--fg-emerald-green)' : 'var(--fg-light-grey-green)'};
          background: ${transaction.ai_inferred ? '#F4FBF7' : 'white'};
          border-radius: var(--radius-md);
          padding: 14px;
          font-size: 12px;
          line-height: 1.5;
        ">
          <div style="display: flex; align-items: center; gap: 6px; font-weight: 700; color: var(--fg-charcoal); margin-bottom: 4px;">
            ${transaction.ai_inferred ? '★ AI Inferred Category' : '✔ Bank-Classified Record'}
          </div>
          <div style="color: var(--fg-muted-grey);">
            ${transaction.ai_inferred ? 
              `Classified as <strong>${transaction.category}</strong> using narration pattern matching. You can override or ask FinGenie for supporting context.` :
              `Category <strong>${transaction.category}</strong> was directly recorded in the institution's statement.`}
          </div>
        </div>

        <!-- Primary Action: Ask FinGenie -->
        <button 
          onclick="window.fgAskAssistantAboutTx('${transaction.id}')"
          style="
            background: var(--fg-forest-green);
            color: white;
            border: none;
            padding: 13px;
            border-radius: var(--radius-md);
            font-size: 14px;
            font-weight: 600;
            cursor: pointer;
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 8px;
            box-shadow: 0 2px 8px rgba(16, 37, 30, 0.2);
            transition: background var(--transition-fast);
            margin-top: auto;
          "
          onmouseover="this.style.background='var(--fg-emerald-green)'"
          onmouseout="this.style.background='var(--fg-forest-green)'"
        >
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M21 11.5a8.38 8.38 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.38 8.38 0 0 1-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.38 8.38 0 0 1 3.8-.9h.5a8.48 8.48 0 0 1 8 8v.5z"></path>
          </svg>
          <span>Ask FinGenie About This Transaction</span>
        </button>

      </div>
    </aside>
  `;
}
