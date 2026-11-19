import React, { useState, useMemo } from 'react';
import { formatCurrency, formatBalance, formatDate, formatCurrencyLabel } from '../../utils/formatters.js';

export function TransactionHistoryPage({ 
  transactions = [], 
  total = 0,
  offset = 0,
  limit = 50,
  loading = false,
  error = null,
  documentMetadata = {}, 
  analysisKpis = null,
  onPageChange,
  onRetry,
  onSelectTransaction,
  onNavigateUpload
}) {
  const [pageSearchTerm, setPageSearchTerm] = useState('');
  const [selectedType, setSelectedType] = useState('all');

  const filename = documentMetadata?.original_filename || documentMetadata?.filename || null;
  const currency = documentMetadata?.currency || null;

  // Filter ONLY within the currently loaded backend page
  const filteredPageTransactions = useMemo(() => {
    return transactions.filter(tx => {
      if (pageSearchTerm) {
        const q = pageSearchTerm.toLowerCase();
        const matchesDesc = (tx.description || '').toLowerCase().includes(q);
        if (!matchesDesc) return false;
      }
      if (selectedType !== 'all' && tx.type !== selectedType) return false;
      return true;
    });
  }, [transactions, pageSearchTerm, selectedType]);

  const currentPage = Math.floor(offset / limit) + 1;
  const totalPages = Math.max(1, Math.ceil(total / limit));
  const canGoPrevious = offset > 0 && !loading;
  const canGoNext = offset + limit < total && !loading;

  // ── Determine which state to render (mutually exclusive) ───────────────────
  // loading → spinner
  // error   → error panel (with optional Retry); never show rows alongside it
  // success → table (empty-success is valid when transactions.length === 0 and !error)

  return (
    <div className="fg-transactions-view" style={{ padding: '28px 32px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '24px' }}>
        <div>
          <h2 style={{ fontSize: '24px', fontWeight: 700, margin: 0 }}>Financial Transactions Ledger</h2>
          <div style={{ display: 'flex', gap: '16px', alignItems: 'center', marginTop: '6px', fontSize: '13px', color: 'var(--fg-muted-grey, #66776d)' }}>
            {filename && (
              <>
                <span>Document: <strong style={{ color: '#18352f' }}>{filename}</strong></span>
                <span>•</span>
              </>
            )}
            <span>Currency: <strong>{formatCurrencyLabel(currency)}</strong></span>
            {documentMetadata?.status && (
              <>
                <span>•</span>
                <span style={{ 
                  textTransform: 'uppercase', 
                  fontSize: '11px', 
                  fontWeight: 700,
                  padding: '2px 8px',
                  borderRadius: '12px',
                  background: documentMetadata.status === 'parsed' ? '#e7f3eb' : '#fee2e2',
                  color: documentMetadata.status === 'parsed' ? '#1d8a60' : '#dc2626'
                }}>
                  {documentMetadata.status}
                </span>
              </>
            )}
          </div>
        </div>

        {onNavigateUpload && (
          <button
            type="button"
            onClick={onNavigateUpload}
            style={{
              background: '#f4f7f5',
              border: '1px solid #d1dbd4',
              borderRadius: '8px',
              padding: '8px 14px',
              fontSize: '13px',
              fontWeight: 600,
              cursor: 'pointer',
              color: '#18352f'
            }}
          >
            ← Upload Another Statement
          </button>
        )}
      </div>

      {/* KPI Cards: ONLY shown in demo mode (passed explicitly), never computed from a partial page */}
      {analysisKpis && (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '16px', marginBottom: '24px' }}>
          <div className="fg-card" style={{ padding: '16px', background: 'white', borderRadius: '12px', border: '1px solid #e5ebe7' }}>
            <span style={{ fontSize: '12px', color: '#66776d', fontWeight: 600 }}>TOTAL INFLOWS (DEMO)</span>
            <div style={{ fontSize: '24px', fontWeight: 700, color: '#1d8a60', marginTop: '4px' }}>
              {formatCurrency(analysisKpis.total_inflow, currency)}
            </div>
          </div>
          <div className="fg-card" style={{ padding: '16px', background: 'white', borderRadius: '12px', border: '1px solid #e5ebe7' }}>
            <span style={{ fontSize: '12px', color: '#66776d', fontWeight: 600 }}>TOTAL OUTFLOWS (DEMO)</span>
            <div style={{ fontSize: '24px', fontWeight: 700, color: '#dc2626', marginTop: '4px' }}>
              {formatCurrency(analysisKpis.total_outflow, currency)}
            </div>
          </div>
          <div className="fg-card" style={{ padding: '16px', background: 'white', borderRadius: '12px', border: '1px solid #e5ebe7' }}>
            <span style={{ fontSize: '12px', color: '#66776d', fontWeight: 600 }}>CLOSING BALANCE (DEMO)</span>
            <div style={{ fontSize: '24px', fontWeight: 700, color: '#18352f', marginTop: '4px' }}>
              {formatBalance(analysisKpis.closing_balance, currency)}
            </div>
          </div>
        </div>
      )}

      {/* ── Loading state ── */}
      {loading && (
        <div className="fg-card" style={{ padding: '64px', textAlign: 'center', color: '#66776d', background: 'white', borderRadius: '12px', border: '1px solid #e5ebe7' }}>
          <div style={{ fontSize: '28px', marginBottom: '12px' }}>⏳</div>
          <div style={{ fontWeight: 600 }}>Loading transactions from workspace…</div>
        </div>
      )}

      {/* ── Error / not-ready state (mutually exclusive with the table) ── */}
      {!loading && error && (
        <div style={{ background: '#fef2f2', border: '1px solid #fca5a5', borderRadius: '10px', padding: '24px', marginBottom: '20px' }} role="alert">
          <div style={{ display: 'flex', alignItems: 'flex-start', gap: '12px' }}>
            <span style={{ fontSize: '22px', lineHeight: 1 }}>⚠️</span>
            <div style={{ flex: 1 }}>
              <div style={{ fontWeight: 700, color: '#b91c1c', marginBottom: '6px', fontSize: '15px' }}>
                Unable to load transactions
              </div>
              <div style={{ color: '#7f1d1d', fontSize: '13px', lineHeight: 1.6 }}>{error}</div>
              {onRetry && (
                <button
                  type="button"
                  onClick={onRetry}
                  style={{
                    marginTop: '14px',
                    background: '#18352f',
                    color: 'white',
                    border: 'none',
                    padding: '9px 18px',
                    borderRadius: '7px',
                    fontWeight: 600,
                    fontSize: '13px',
                    cursor: 'pointer',
                  }}
                >
                  Retry
                </button>
              )}
            </div>
          </div>
        </div>
      )}

      {/* ── Successful state: search bar + table (shown only when not loading and no error) ── */}
      {!loading && !error && (
        <>
          {/* Search within loaded page */}
          <div className="fg-card" style={{ padding: '14px 18px', marginBottom: '20px', display: 'flex', gap: '16px', alignItems: 'center', background: 'white', borderRadius: '10px', border: '1px solid #e5ebe7' }}>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
              <input
                type="text"
                value={pageSearchTerm}
                onChange={(e) => setPageSearchTerm(e.target.value)}
                placeholder="Search within this page..."
                style={{ padding: '8px 12px', borderRadius: '6px', border: '1px solid #d1dbd4', width: '280px', fontSize: '13px' }}
              />
              <span style={{ fontSize: '11px', color: '#88998e' }}>(Filters only the currently loaded page of records)</span>
            </div>
            <select 
              value={selectedType} 
              onChange={(e) => setSelectedType(e.target.value)}
              style={{ padding: '8px 12px', borderRadius: '6px', border: '1px solid #d1dbd4', fontSize: '13px', background: 'white' }}
            >
              <option value="all">All Movements</option>
              <option value="credit">Credits only</option>
              <option value="debit">Debits only</option>
            </select>
          </div>

          {/* Transactions Table */}
          <div className="fg-card" style={{ overflow: 'hidden', background: 'white', borderRadius: '12px', border: '1px solid #e5ebe7' }}>
            {filteredPageTransactions.length === 0 ? (
              <div style={{ padding: '48px', textAlign: 'center', color: '#66776d' }}>
                <p style={{ margin: '0 0 8px 0', fontSize: '16px', fontWeight: 600 }}>No transactions to display.</p>
                <p style={{ fontSize: '13px', margin: 0 }}>
                  {transactions.length === 0
                    ? 'This workspace has no transaction rows in this page.'
                    : 'No transactions match your page search.'}
                </p>
              </div>
            ) : (
              <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '13px' }}>
                <thead>
                  <tr style={{ background: '#fafbfa', borderBottom: '1px solid #e5ebe7' }}>
                    <th style={{ padding: '12px 16px', fontWeight: 600, color: '#52685c' }}>Date</th>
                    <th style={{ padding: '12px 16px', fontWeight: 600, color: '#52685c' }}>Description</th>
                    <th style={{ padding: '12px 16px', textAlign: 'right', fontWeight: 600, color: '#52685c' }}>Debit</th>
                    <th style={{ padding: '12px 16px', textAlign: 'right', fontWeight: 600, color: '#52685c' }}>Credit</th>
                    <th style={{ padding: '12px 16px', textAlign: 'right', fontWeight: 600, color: '#52685c' }}>Balance</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredPageTransactions.map((tx) => (
                    <tr 
                      key={tx.id} 
                      onClick={() => onSelectTransaction && onSelectTransaction(tx)}
                      style={{ borderBottom: '1px solid #edf1ee', cursor: 'pointer' }}
                    >
                      <td style={{ padding: '12px 16px', whiteSpace: 'nowrap', color: '#18352f' }}>{formatDate(tx.date)}</td>
                      <td style={{ padding: '12px 16px' }}>
                        <div style={{ fontWeight: 600, color: '#18352f' }}>{tx.description}</div>
                        <div style={{ fontSize: '11px', color: '#66776d' }}>Row #{tx.source_row} • {tx.source_file}</div>
                      </td>
                      <td style={{ padding: '12px 16px', textAlign: 'right', color: '#dc2626', fontWeight: 500 }}>
                        {tx.debit !== null && tx.debit > 0 ? formatCurrency(tx.debit, tx.currency) : '—'}
                      </td>
                      <td style={{ padding: '12px 16px', textAlign: 'right', color: '#1d8a60', fontWeight: 500 }}>
                        {tx.credit !== null && tx.credit > 0 ? formatCurrency(tx.credit, tx.currency) : '—'}
                      </td>
                      <td style={{ padding: '12px 16px', textAlign: 'right', color: '#18352f', fontWeight: 600 }}>
                        {formatBalance(tx.balance, tx.currency)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}

            {/* Backend Pagination Bar */}
            <div style={{ padding: '14px 18px', display: 'flex', justifyContent: 'space-between', alignItems: 'center', background: '#fafbfa', borderTop: '1px solid #e5ebe7', fontSize: '13px' }}>
              <span style={{ color: '#66776d' }}>
                Showing {transactions.length} record{transactions.length === 1 ? '' : 's'} (total: {total})
              </span>
              <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                <button 
                  type="button"
                  disabled={!canGoPrevious} 
                  onClick={() => onPageChange && onPageChange(Math.max(0, offset - limit))}
                  style={{
                    padding: '6px 12px',
                    borderRadius: '6px',
                    border: '1px solid #d1dbd4',
                    background: canGoPrevious ? 'white' : '#f4f7f5',
                    cursor: canGoPrevious ? 'pointer' : 'not-allowed',
                    color: canGoPrevious ? '#18352f' : '#999'
                  }}
                >
                  ← Previous
                </button>
                <span style={{ color: '#18352f', fontWeight: 500 }}>
                  Page {currentPage} of {totalPages}
                </span>
                <button 
                  type="button"
                  disabled={!canGoNext} 
                  onClick={() => onPageChange && onPageChange(offset + limit)}
                  style={{
                    padding: '6px 12px',
                    borderRadius: '6px',
                    border: '1px solid #d1dbd4',
                    background: canGoNext ? 'white' : '#f4f7f5',
                    cursor: canGoNext ? 'pointer' : 'not-allowed',
                    color: canGoNext ? '#18352f' : '#999'
                  }}
                >
                  Next →
                </button>
              </div>
            </div>
          </div>
        </>
      )}
    </div>
  );
}

export default TransactionHistoryPage;
