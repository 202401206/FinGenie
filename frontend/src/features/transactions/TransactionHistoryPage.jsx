import React, { useState, useMemo } from 'react';
import { formatCurrency, formatBalance, formatDate } from '../../utils/formatters.js';

export function TransactionHistoryPage({ 
  transactions = [], 
  documentMetadata = {}, 
  analysisKpis = null,
  onSelectTransaction 
}) {
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedType, setSelectedType] = useState('all');
  const [page, setPage] = useState(1);
  const pageSize = 10;

  const filteredTransactions = useMemo(() => {
    return transactions.filter(tx => {
      if (searchTerm) {
        const q = searchTerm.toLowerCase();
        const matchesDesc = (tx.description || '').toLowerCase().includes(q);
        const matchesCat = (tx.category || '').toLowerCase().includes(q);
        const matchesChan = (tx.payment_method || '').toLowerCase().includes(q);
        if (!matchesDesc && !matchesCat && !matchesChan) return false;
      }
      if (selectedType !== 'all' && tx.type !== selectedType) return false;
      return true;
    });
  }, [transactions, searchTerm, selectedType]);

  const totalPages = Math.max(1, Math.ceil(filteredTransactions.length / pageSize));
  const paginatedItems = useMemo(() => {
    const start = (page - 1) * pageSize;
    return filteredTransactions.slice(start, start + pageSize);
  }, [filteredTransactions, page, pageSize]);

  return (
    <div className="fg-transactions-view" style={{ padding: '28px 32px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '24px' }}>
        <div>
          <h2 style={{ fontSize: '24px', fontWeight: 700, margin: 0 }}>Financial Transactions Ledger</h2>
          <p style={{ fontSize: '13px', color: 'var(--fg-muted-grey)', margin: '4px 0 0 0' }}>
            Document: <strong>{documentMetadata.filename || documentMetadata.file_name || 'Uploaded Records'}</strong>
          </p>
        </div>
      </div>

      {analysisKpis && (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '16px', marginBottom: '24px' }}>
          <div className="fg-card" style={{ padding: '16px' }}>
            <span style={{ fontSize: '12px', color: 'var(--fg-muted-grey)' }}>TOTAL INFLOWS</span>
            <div style={{ fontSize: '24px', fontWeight: 700, color: 'var(--fg-emerald-green)' }}>
              {formatCurrency(analysisKpis.total_inflow, documentMetadata.currency)}
            </div>
          </div>
          <div className="fg-card" style={{ padding: '16px' }}>
            <span style={{ fontSize: '12px', color: 'var(--fg-muted-grey)' }}>TOTAL OUTFLOWS</span>
            <div style={{ fontSize: '24px', fontWeight: 700, color: 'var(--fg-soft-red)' }}>
              {formatCurrency(analysisKpis.total_outflow, documentMetadata.currency)}
            </div>
          </div>
          <div className="fg-card" style={{ padding: '16px' }}>
            <span style={{ fontSize: '12px', color: 'var(--fg-muted-grey)' }}>CLOSING BALANCE</span>
            <div style={{ fontSize: '24px', fontWeight: 700 }}>
              {formatBalance(analysisKpis.closing_balance, documentMetadata.currency)}
            </div>
          </div>
        </div>
      )}

      <div className="fg-card" style={{ padding: '16px', marginBottom: '20px', display: 'flex', gap: '12px' }}>
        <input
          type="text"
          value={searchTerm}
          onChange={(e) => { setSearchTerm(e.target.value); setPage(1); }}
          placeholder="Search description, category..."
          style={{ padding: '8px 12px', borderRadius: '6px', border: '1px solid var(--fg-light-grey-green)', width: '260px' }}
        />
        <select 
          value={selectedType} 
          onChange={(e) => { setSelectedType(e.target.value); setPage(1); }}
          style={{ padding: '8px 12px', borderRadius: '6px', border: '1px solid var(--fg-light-grey-green)' }}
        >
          <option value="all">All Types</option>
          <option value="credit">Credits</option>
          <option value="debit">Debits</option>
        </select>
      </div>

      <div className="fg-card" style={{ overflow: 'hidden' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '13px' }}>
          <thead>
            <tr style={{ background: '#FAFBFA', borderBottom: '1px solid var(--fg-light-grey-green)' }}>
              <th style={{ padding: '12px 16px' }}>Date</th>
              <th style={{ padding: '12px 16px' }}>Description</th>
              <th style={{ padding: '12px 16px' }}>Category</th>
              <th style={{ padding: '12px 16px' }}>Channel</th>
              <th style={{ padding: '12px 16px', textAlign: 'right' }}>Debit</th>
              <th style={{ padding: '12px 16px', textAlign: 'right' }}>Credit</th>
              <th style={{ padding: '12px 16px', textAlign: 'right' }}>Balance</th>
            </tr>
          </thead>
          <tbody>
            {paginatedItems.map((tx) => (
              <tr 
                key={tx.id} 
                onClick={() => onSelectTransaction && onSelectTransaction(tx)}
                style={{ borderBottom: '1px solid var(--fg-light-grey-green)', cursor: 'pointer' }}
              >
                <td style={{ padding: '12px 16px', whiteSpace: 'nowrap' }}>{formatDate(tx.date)}</td>
                <td style={{ padding: '12px 16px' }}>
                  <div style={{ fontWeight: 600 }}>{tx.description}</div>
                  <div style={{ fontSize: '11px', color: 'var(--fg-muted-grey)' }}>Row #{tx.source_row} • {tx.source_file}</div>
                </td>
                <td style={{ padding: '12px 16px' }}>{tx.category}</td>
                <td style={{ padding: '12px 16px' }}>{tx.payment_method}</td>
                <td style={{ padding: '12px 16px', textAlign: 'right', color: 'var(--fg-soft-red)' }}>
                  {tx.debit !== null && tx.debit > 0 ? formatCurrency(tx.debit, tx.currency) : '—'}
                </td>
                <td style={{ padding: '12px 16px', textAlign: 'right', color: 'var(--fg-emerald-green)' }}>
                  {tx.credit !== null && tx.credit > 0 ? formatCurrency(tx.credit, tx.currency) : '—'}
                </td>
                <td style={{ padding: '12px 16px', textAlign: 'right' }}>
                  {formatBalance(tx.balance, tx.currency)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>

        <div style={{ padding: '12px 16px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <span>Showing {paginatedItems.length} of {filteredTransactions.length} records</span>
          <div>
            <button disabled={page <= 1} onClick={() => setPage(p => p - 1)}>Previous</button>
            <span style={{ margin: '0 8px' }}>Page {page} of {totalPages}</span>
            <button disabled={page >= totalPages} onClick={() => setPage(p => p + 1)}>Next</button>
          </div>
        </div>
      </div>
    </div>
  );
}
