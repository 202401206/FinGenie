import React, { useState } from 'react';
import { formatCurrency, formatBalance, formatDate } from '../../../utils/formatters.js';

/**
 * Bank Transaction Explorer
 * Renders server-paginated bank transactions with source-row provenance.
 * Strictly used for bank statements only.
 */
export function TransactionExplorer({
  transactions = [],
  total = 0,
  offset = 0,
  limit = 50,
  loading = false,
  error = null,
  currency = 'INR',
  highlightSourceRow = null,
  onPageChange = null,
  onRetry = null
}) {
  const [selectedTx, setSelectedTx] = useState(null);

  const currentPage = Math.floor(offset / limit) + 1;
  const totalPages = Math.max(1, Math.ceil(total / limit));
  const canGoPrevious = offset > 0 && !loading;
  const canGoNext = offset + limit < total && !loading;

  const handlePrev = () => {
    if (canGoPrevious && onPageChange) {
      onPageChange(Math.max(0, offset - limit));
    }
  };

  const handleNext = () => {
    if (canGoNext && onPageChange) {
      onPageChange(offset + limit);
    }
  };

  return (
    <section className="fg-transaction-explorer" aria-label="Statement Transactions Ledger">
      <div className="fg-explorer-header">
        <div>
          <h3 className="fg-explorer-title">Statement Transactions Ledger</h3>
          <p className="fg-explorer-subtitle">
            Showing transactions {total > 0 ? offset + 1 : 0} to {Math.min(offset + limit, total)} of {total} verified records
          </p>
        </div>

        {/* Pagination Controls */}
        <div className="fg-pagination-controls" role="navigation" aria-label="Transaction pagination">
          <button
            type="button"
            className="fg-pagination-btn"
            onClick={handlePrev}
            disabled={!canGoPrevious}
            aria-label="Previous page"
          >
            ← Previous
          </button>

          <span className="fg-pagination-indicator" aria-current="page">
            Page {currentPage} of {totalPages}
          </span>

          <button
            type="button"
            className="fg-pagination-btn"
            onClick={handleNext}
            disabled={!canGoNext}
            aria-label="Next page"
          >
            Next →
          </button>
        </div>
      </div>

      {/* Loading indicator */}
      {loading && (
        <div className="fg-explorer-loading" role="status" aria-live="polite">
          <div className="fg-loading-spinner" aria-hidden="true" />
          <span>Loading transaction records...</span>
        </div>
      )}

      {/* Error state */}
      {error && !loading && (
        <div className="fg-explorer-error" role="alert">
          <p>⚠️ {error}</p>
          {onRetry && (
            <button type="button" className="fg-state-btn primary" onClick={onRetry}>
              Retry Loading Transactions
            </button>
          )}
        </div>
      )}

      {/* Transactions Table */}
      {!loading && !error && (
        <div className="fg-table-wrapper" tabIndex={0} role="region" aria-label="Scrollable transaction records">
          <table className="fg-transactions-table">
            <thead>
              <tr>
                <th scope="col" style={{ width: '80px' }}>Row</th>
                <th scope="col" style={{ width: '120px' }}>Date</th>
                <th scope="col">Description</th>
                <th scope="col" style={{ width: '130px', textAlign: 'right' }}>Debit</th>
                <th scope="col" style={{ width: '130px', textAlign: 'right' }}>Credit</th>
                <th scope="col" style={{ width: '140px', textAlign: 'right' }}>Balance</th>
              </tr>
            </thead>
            <tbody>
              {transactions.length === 0 ? (
                <tr>
                  <td colSpan={6} className="fg-table-empty">
                    No transactions recorded on this page.
                  </td>
                </tr>
              ) : (
                transactions.map((tx) => {
                  const isHighlighted = highlightSourceRow !== null && tx.source_row === Number(highlightSourceRow);
                  const isDebit = tx.debit !== null && tx.debit !== undefined && Number(tx.debit) > 0;
                  const isCredit = tx.credit !== null && tx.credit !== undefined && Number(tx.credit) > 0;

                  return (
                    <tr
                      key={tx.id || `row-${tx.source_row}`}
                      className={`fg-table-row ${isHighlighted ? 'highlighted' : ''} ${selectedTx?.id === tx.id ? 'selected' : ''}`}
                      onClick={() => setSelectedTx(selectedTx?.id === tx.id ? null : tx)}
                      tabIndex={0}
                      role="button"
                      aria-pressed={selectedTx?.id === tx.id}
                      onKeyDown={(e) => {
                        if (e.key === 'Enter' || e.key === ' ') {
                          setSelectedTx(selectedTx?.id === tx.id ? null : tx);
                        }
                      }}
                    >
                      <td className="fg-cell-row">
                        <span className="fg-row-tag" title={`Statement original source row ${tx.source_row}`}>
                          #{tx.source_row}
                        </span>
                      </td>
                      <td className="fg-cell-date">{formatDate(tx.date)}</td>
                      <td className="fg-cell-desc" title={tx.description}>
                        {tx.description || '—'}
                      </td>
                      <td className="fg-cell-debit">
                        {isDebit ? formatCurrency(tx.debit, currency) : '—'}
                      </td>
                      <td className="fg-cell-credit">
                        {isCredit ? formatCurrency(tx.credit, currency) : '—'}
                      </td>
                      <td className="fg-cell-balance">
                        {formatBalance(tx.balance, currency)}
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      )}

      {/* Selected Transaction Detail Drawer */}
      {selectedTx && (
        <aside className="fg-tx-detail-drawer" aria-label="Transaction Audit Detail">
          <div className="fg-drawer-header">
            <h4>Transaction Audit Provenance</h4>
            <button
              type="button"
              className="fg-drawer-close-btn"
              onClick={() => setSelectedTx(null)}
              aria-label="Close detail drawer"
            >
              ✕
            </button>
          </div>
          <div className="fg-drawer-grid">
            <div className="fg-drawer-item">
              <span className="fg-drawer-label">Original Statement Row</span>
              <span className="fg-drawer-value">Row #{selectedTx.source_row}</span>
            </div>
            <div className="fg-drawer-item">
              <span className="fg-drawer-label">Record Date</span>
              <span className="fg-drawer-value">{formatDate(selectedTx.date)}</span>
            </div>
            <div className="fg-drawer-item full">
              <span className="fg-drawer-label">Raw Description</span>
              <span className="fg-drawer-value mono">{selectedTx.description || '—'}</span>
            </div>
            <div className="fg-drawer-item">
              <span className="fg-drawer-label">Debit Amount</span>
              <span className="fg-drawer-value">{selectedTx.debit ? formatCurrency(selectedTx.debit, currency) : '—'}</span>
            </div>
            <div className="fg-drawer-item">
              <span className="fg-drawer-label">Credit Amount</span>
              <span className="fg-drawer-value">{selectedTx.credit ? formatCurrency(selectedTx.credit, currency) : '—'}</span>
            </div>
            <div className="fg-drawer-item">
              <span className="fg-drawer-label">Resulting Balance</span>
              <span className="fg-drawer-value">{formatBalance(selectedTx.balance, currency)}</span>
            </div>
          </div>
        </aside>
      )}
    </section>
  );
}

export default TransactionExplorer;
