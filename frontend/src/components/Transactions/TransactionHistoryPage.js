/**
 * FinGenie Transaction History & High-Density Ledger Page Component
 * Complete with KPI summary cards, filter toolbar, Indian banking data table, and pagination
 */

import { formatINR, formatDate } from '../../utils/formatters.js';
import { TRANSACTION_CATEGORIES, PAYMENT_METHODS } from '../../services/transactionService.js';

export function renderTransactionHistoryPage({
  transactions = [],
  paginatedData = {},
  kpis = {},
  filters = {},
  sortState = { sortBy: 'date', sortOrder: 'desc' },
  selectedTransactionId = null,
  activeBank = 'HDFC Bank',
  activeDocument = 'HDFC_Statement_Oct2026.csv'
}) {
  const { items = [], totalItems = 0, totalPages = 1, currentPage = 1 } = paginatedData;

  const isFiltered = Boolean(
    filters.search || 
    (filters.type && filters.type !== 'all') || 
    (filters.category && filters.category !== 'all' && filters.category !== 'All Categories') ||
    (filters.paymentMethod && filters.paymentMethod !== 'all' && filters.paymentMethod !== 'All Methods') ||
    filters.minAmount ||
    filters.maxAmount
  );

  return `
    <div class="fg-transactions-view" style="padding: 28px 32px; box-sizing: border-box; max-width: 1400px; margin: 0 auto;">
      
      <!-- Top Title & Subheading -->
      <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 24px;">
        <div>
          <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 4px;">
            <h2 style="font-size: 24px; font-weight: 700; color: var(--fg-charcoal); margin: 0; letter-spacing: -0.4px;">
              Financial Transactions Ledger
            </h2>
            <span style="
              background: var(--fg-pale-mint);
              color: var(--fg-emerald-green);
              font-size: 11px;
              font-weight: 700;
              padding: 3px 8px;
              border-radius: var(--radius-pill);
            ">
              ${totalItems} RECORDS
            </span>
          </div>
          <p style="font-size: 13px; color: var(--fg-muted-grey); margin: 0;">
            Parsed from <strong style="color: var(--fg-charcoal);">${activeDocument}</strong> • Associated Institution: <strong style="color: var(--fg-charcoal);">${activeBank}</strong>
          </p>
        </div>

        <!-- Export & Action Buttons -->
        <div style="display: flex; gap: 10px;">
          <button onclick="window.fgExportCSV()" style="
            display: flex;
            align-items: center;
            gap: 6px;
            background: white;
            border: 1px solid var(--fg-light-grey-green);
            padding: 8px 14px;
            border-radius: var(--radius-md);
            font-size: 13px;
            font-weight: 600;
            color: var(--fg-charcoal);
            cursor: pointer;
            box-shadow: var(--shadow-subtle);
            transition: all var(--transition-fast);
          " onmouseover="this.style.background='var(--fg-warm-white)'" onmouseout="this.style.background='white'">
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path>
              <polyline points="7 10 12 15 17 10"></polyline>
              <line x1="12" y1="15" x2="12" y2="3"></line>
            </svg>
            <span>Export CSV</span>
          </button>
        </div>
      </div>

      <!-- KPI Metric Cards Grid (4 Summary Metrics) -->
      <div style="
        display: grid;
        grid-template-columns: repeat(4, 1fr);
        gap: 16px;
        margin-bottom: 24px;
      ">
        <!-- 1. Total Inflow / Credits -->
        <div class="fg-card" style="padding: 18px 20px;">
          <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
            <span style="font-size: 12px; font-weight: 600; text-transform: uppercase; color: var(--fg-muted-grey); letter-spacing: 0.5px;">TOTAL CREDITS</span>
            <span style="width: 24px; height: 24px; border-radius: 50%; background: var(--fg-pale-mint); display: flex; align-items: center; justify-content: center; color: var(--fg-emerald-green); font-size: 12px; font-weight: bold;">↓</span>
          </div>
          <div style="font-size: 24px; font-weight: 700; color: var(--fg-emerald-green); letter-spacing: -0.5px;">
            ${formatINR(kpis.totalCredits || 0)}
          </div>
          <div style="font-size: 11px; color: var(--fg-muted-grey); margin-top: 4px;">
            Salary & remittances recorded
          </div>
        </div>

        <!-- 2. Total Outflow / Debits -->
        <div class="fg-card" style="padding: 18px 20px;">
          <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
            <span style="font-size: 12px; font-weight: 600; text-transform: uppercase; color: var(--fg-muted-grey); letter-spacing: 0.5px;">TOTAL DEBITS</span>
            <span style="width: 24px; height: 24px; border-radius: 50%; background: var(--fg-soft-red-light); display: flex; align-items: center; justify-content: center; color: var(--fg-soft-red); font-size: 12px; font-weight: bold;">↑</span>
          </div>
          <div style="font-size: 24px; font-weight: 700; color: var(--fg-soft-red); letter-spacing: -0.5px;">
            ${formatINR(kpis.totalDebits || 0)}
          </div>
          <div style="font-size: 11px; color: var(--fg-muted-grey); margin-top: 4px;">
            Expenses & transfers out
          </div>
        </div>

        <!-- 3. Net Cash Flow -->
        <div class="fg-card" style="padding: 18px 20px;">
          <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
            <span style="font-size: 12px; font-weight: 600; text-transform: uppercase; color: var(--fg-muted-grey); letter-spacing: 0.5px;">NET CASH FLOW</span>
            <span style="font-size: 11px; font-weight: 600; color: var(--fg-muted-grey);">Current View</span>
          </div>
          <div style="font-size: 24px; font-weight: 700; color: ${kpis.netCashFlow >= 0 ? 'var(--fg-emerald-green)' : 'var(--fg-soft-red)'}; letter-spacing: -0.5px;">
            ${kpis.netCashFlow >= 0 ? '+' : ''}${formatINR(kpis.netCashFlow || 0)}
          </div>
          <div style="font-size: 11px; color: var(--fg-muted-grey); margin-top: 4px;">
            Net balance delta
          </div>
        </div>

        <!-- 4. Largest Outflow -->
        <div class="fg-card" style="padding: 18px 20px;">
          <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
            <span style="font-size: 12px; font-weight: 600; text-transform: uppercase; color: var(--fg-muted-grey); letter-spacing: 0.5px;">LARGEST EXPENSE</span>
            <span style="font-size: 11px; font-weight: 600; color: var(--fg-muted-grey);">Peak Debit</span>
          </div>
          <div style="font-size: 24px; font-weight: 700; color: var(--fg-charcoal); letter-spacing: -0.5px;">
            ${formatINR(kpis.largestExpense || 0)}
          </div>
          <div style="font-size: 11px; color: var(--fg-muted-grey); margin-top: 4px;">
            Single highest debit recorded
          </div>
        </div>
      </div>

      <!-- Filter & Search Toolbar Card -->
      <div class="fg-card" style="padding: 16px 20px; margin-bottom: 20px;">
        <div style="display: flex; flex-wrap: wrap; gap: 12px; align-items: center; justify-content: space-between;">
          <!-- Left: Search & Filter Controls -->
          <div style="display: flex; flex-wrap: wrap; gap: 10px; align-items: center; flex: 1;">
            <!-- Text Search Input -->
            <div style="position: relative; width: 240px;">
              <input 
                type="text" 
                id="tx-search-input"
                placeholder="Search description, UPI ID..." 
                value="${filters.search || ''}"
                oninput="window.fgApplyFilter('search', this.value)"
                style="
                  width: 100%; box-sizing: border-box; padding: 7px 10px 7px 30px; border: 1px solid var(--fg-light-grey-green); border-radius: var(--radius-sm); font-size: 13px; outline: none;
                "
              />
              <svg style="position: absolute; left: 8px; top: 8px; color: var(--fg-muted-grey);" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <circle cx="11" cy="11" r="8"></circle>
                <line x1="21" y1="21" x2="16.65" y2="16.65"></line>
              </svg>
            </div>

            <!-- Type Filter Tabs: All / Credit / Debit -->
            <div style="display: flex; background: var(--fg-warm-white); padding: 3px; border-radius: var(--radius-sm); border: 1px solid var(--fg-light-grey-green);">
              ${['all', 'credit', 'debit'].map(t => `
                <button onclick="window.fgApplyFilter('type', '${t}')" style="
                  border: none;
                  background: ${(filters.type || 'all') === t ? 'white' : 'transparent'};
                  color: ${(filters.type || 'all') === t ? 'var(--fg-forest-green)' : 'var(--fg-muted-grey)'};
                  font-weight: ${(filters.type || 'all') === t ? '600' : '500'};
                  font-size: 12px;
                  padding: 4px 10px;
                  border-radius: 4px;
                  cursor: pointer;
                  box-shadow: ${(filters.type || 'all') === t ? 'var(--shadow-subtle)' : 'none'};
                  text-transform: capitalize;
                ">
                  ${t}
                </button>
              `).join('')}
            </div>

            <!-- Category Filter Dropdown -->
            <select onchange="window.fgApplyFilter('category', this.value)" style="
              padding: 7px 10px; border: 1px solid var(--fg-light-grey-green); border-radius: var(--radius-sm); font-size: 13px; background: white; color: var(--fg-charcoal); outline: none; cursor: pointer;
            ">
              ${TRANSACTION_CATEGORIES.map(cat => `
                <option value="${cat}" ${(filters.category === cat) ? 'selected' : ''}>
                  ${cat}
                </option>
              `).join('')}
            </select>

            <!-- Payment Method Dropdown -->
            <select onchange="window.fgApplyFilter('paymentMethod', this.value)" style="
              padding: 7px 10px; border: 1px solid var(--fg-light-grey-green); border-radius: var(--radius-sm); font-size: 13px; background: white; color: var(--fg-charcoal); outline: none; cursor: pointer;
            ">
              ${PAYMENT_METHODS.map(pm => `
                <option value="${pm}" ${(filters.paymentMethod === pm) ? 'selected' : ''}>
                  ${pm}
                </option>
              `).join('')}
            </select>

            <!-- Reset Filters Pill -->
            ${isFiltered ? `
              <button onclick="window.fgResetFilters()" style="
                background: none; border: 1px dashed var(--fg-soft-red); color: var(--fg-soft-red); font-size: 12px; font-weight: 500; padding: 5px 10px; border-radius: var(--radius-sm); cursor: pointer; display: flex; align-items: center; gap: 4px;
              ">
                ✕ Reset Filters
              </button>
            ` : ''}
          </div>

          <!-- Right: Sort Dropdown & Indicator -->
          <div style="display: flex; align-items: center; gap: 8px;">
            <span style="font-size: 12px; color: var(--fg-muted-grey);">Sort:</span>
            <button onclick="window.fgToggleSort('${sortState.sortBy === 'date' ? 'amount' : 'date'}')" style="
              background: white; border: 1px solid var(--fg-light-grey-green); padding: 6px 10px; border-radius: var(--radius-sm); font-size: 12px; font-weight: 600; color: var(--fg-charcoal); cursor: pointer; display: flex; align-items: center; gap: 4px;
            ">
              <span>${sortState.sortBy === 'date' ? 'Date' : 'Amount'}</span>
              <span>${sortState.sortOrder === 'desc' ? '↓' : '↑'}</span>
            </button>
          </div>
        </div>
      </div>

      <!-- High Density Ledger Table Surface -->
      <div class="fg-card" style="overflow: hidden; margin-bottom: 20px;">
        <div style="overflow-x: auto;">
          <table style="width: 100%; border-collapse: collapse; text-align: left; font-size: 13px;">
            <thead>
              <tr style="background: #FAFBFA; border-bottom: 1px solid var(--fg-light-grey-green); color: var(--fg-muted-grey); font-weight: 600; font-size: 12px; text-transform: uppercase; letter-spacing: 0.5px;">
                <th style="padding: 12px 18px;">Date</th>
                <th style="padding: 12px 18px;">Transaction Details</th>
                <th style="padding: 12px 18px;">Category</th>
                <th style="padding: 12px 18px;">Channel</th>
                <th style="padding: 12px 18px; text-align: right;">Amount (INR)</th>
                <th style="padding: 12px 18px; text-align: right;">Balance (INR)</th>
                <th style="padding: 12px 18px; text-align: center;">Trace</th>
              </tr>
            </thead>
            <tbody>
              ${items.length === 0 ? `
                <tr>
                  <td colspan="7" style="padding: 48px; text-align: center; color: var(--fg-muted-grey);">
                    <div style="font-size: 28px; margin-bottom: 8px;">🔍</div>
                    <div style="font-weight: 600; font-size: 15px; color: var(--fg-charcoal); margin-bottom: 4px;">No matching transactions found</div>
                    <div style="font-size: 13px;">Try adjusting your keyword, category, or payment method filter.</div>
                    <button onclick="window.fgResetFilters()" style="margin-top: 14px; background: var(--fg-forest-green); color: white; border: none; padding: 7px 14px; border-radius: var(--radius-sm); font-size: 12px; font-weight: 600; cursor: pointer;">
                      Clear all filters
                    </button>
                  </td>
                </tr>
              ` : items.map((tx, idx) => {
                const isSelected = selectedTransactionId === tx.id;
                const isCredit = tx.type === 'credit';
                return `
                  <tr 
                    onclick="window.fgSelectTransaction('${tx.id}')"
                    style="
                      border-bottom: 1px solid var(--fg-light-grey-green);
                      background: ${isSelected ? 'var(--fg-pale-mint)' : (idx % 2 === 0 ? '#FFFFFF' : '#FCFDFC')};
                      cursor: pointer;
                      transition: background var(--transition-fast);
                    "
                    onmouseover="if (!${isSelected}) this.style.background='#F7F9F8';"
                    onmouseout="if (!${isSelected}) this.style.background='${idx % 2 === 0 ? '#FFFFFF' : '#FCFDFC'}';"
                  >
                    <!-- Date -->
                    <td style="padding: 14px 18px; white-space: nowrap; color: var(--fg-charcoal); font-weight: 500;">
                      ${formatDate(tx.date)}
                    </td>

                    <!-- Description / Narration -->
                    <td style="padding: 14px 18px; max-width: 320px;">
                      <div style="font-weight: 600; color: var(--fg-charcoal); white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">
                        ${tx.description}
                      </div>
                      <div style="font-size: 11px; color: var(--fg-muted-grey); margin-top: 2px;">
                        Row ${tx.source_row} • ${tx.source_file}
                      </div>
                    </td>

                    <!-- Category Badge -->
                    <td style="padding: 14px 18px; white-space: nowrap;">
                      <span style="
                        background: #F1F4F2;
                        border: 1px solid var(--fg-light-grey-green);
                        color: var(--fg-charcoal);
                        font-size: 11px;
                        font-weight: 600;
                        padding: 3px 8px;
                        border-radius: var(--radius-pill);
                        display: inline-flex;
                        align-items: center;
                        gap: 4px;
                      ">
                        ${tx.ai_inferred ? '<span style="color: var(--fg-emerald-green); font-size: 10px;">★</span>' : ''}
                        ${tx.category}
                      </span>
                    </td>

                    <!-- Payment Method Badge -->
                    <td style="padding: 14px 18px; white-space: nowrap;">
                      <span class="${tx.payment_method === 'UPI' ? 'badge-upi' : (tx.payment_method === 'NEFT' ? 'badge-neft' : '')}" style="
                        font-size: 11px;
                        font-weight: 600;
                        padding: 2px 7px;
                        border-radius: 4px;
                        border: 1px solid rgba(0,0,0,0.06);
                      ">
                        ${tx.payment_method}
                      </span>
                    </td>

                    <!-- Amount with Indian Rupee formatting & +/- -->
                    <td style="padding: 14px 18px; text-align: right; white-space: nowrap;">
                      <span style="
                        font-weight: 700;
                        font-size: 14px;
                        color: ${isCredit ? 'var(--fg-emerald-green)' : 'var(--fg-soft-red)'};
                      ">
                        ${isCredit ? '+' : '-'}${formatINR(tx.amount)}
                      </span>
                    </td>

                    <!-- Balance (INR) -->
                    <td style="padding: 14px 18px; text-align: right; white-space: nowrap; color: var(--fg-muted-grey); font-weight: 500;">
                      ${tx.balance ? formatINR(tx.balance) : '—'}
                    </td>

                    <!-- Trace Button -->
                    <td style="padding: 14px 18px; text-align: center; white-space: nowrap;">
                      <button title="Inspect Row Provenance" style="
                        background: none; border: none; color: var(--fg-muted-grey); cursor: pointer; padding: 4px;
                      ">
                        →
                      </button>
                    </td>
                  </tr>
                `;
              }).join('')}
            </tbody>
          </table>
        </div>

        <!-- Table Footer: Pagination & Item Count -->
        <div style="
          padding: 12px 18px;
          background: #FAFBFA;
          border-top: 1px solid var(--fg-light-grey-green);
          display: flex;
          justify-content: space-between;
          align-items: center;
          font-size: 12px;
          color: var(--fg-muted-grey);
        ">
          <div>
            Showing <strong style="color: var(--fg-charcoal);">${items.length}</strong> of <strong style="color: var(--fg-charcoal);">${totalItems}</strong> transactions
          </div>

          <!-- Pagination Buttons -->
          <div style="display: flex; align-items: center; gap: 8px;">
            <button 
              onclick="window.fgChangePage(${currentPage - 1})"
              ${currentPage <= 1 ? 'disabled style="opacity: 0.5; cursor: not-allowed;"' : 'style="cursor: pointer;"'}
              class="fg-btn-pagination"
              style="
                background: white; border: 1px solid var(--fg-light-grey-green); padding: 5px 10px; border-radius: var(--radius-sm); font-size: 12px; font-weight: 600; color: var(--fg-charcoal);
              "
            >
              Previous
            </button>

            <span style="font-weight: 600; color: var(--fg-charcoal); padding: 0 4px;">
              Page ${currentPage} of ${totalPages}
            </span>

            <button 
              onclick="window.fgChangePage(${currentPage + 1})"
              ${currentPage >= totalPages ? 'disabled style="opacity: 0.5; cursor: not-allowed;"' : 'style="cursor: pointer;"'}
              class="fg-btn-pagination"
              style="
                background: white; border: 1px solid var(--fg-light-grey-green); padding: 5px 10px; border-radius: var(--radius-sm); font-size: 12px; font-weight: 600; color: var(--fg-charcoal);
              "
            >
              Next
            </button>
          </div>
        </div>
      </div>
    </div>
  `;
}
