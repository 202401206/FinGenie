import React from 'react';
import { formatCurrency, formatBalance, formatDate } from '../../utils/formatters.js';

export function TransactionDetailDrawer({ transaction, isOpen, onClose }) {
  if (!isOpen || !transaction) return null;

  const isCredit = transaction.type === 'credit';

  return (
    <>
      <div 
        onClick={onClose}
        style={{
          position: 'fixed', top: 0, left: 0, width: '100vw', height: '100vh',
          background: 'rgba(16, 37, 30, 0.35)', backdropFilter: 'blur(2px)', zIndex: 100
        }}
      />
      <aside style={{
        position: 'fixed', top: 0, right: 0, width: '420px', height: '100vh',
        background: '#ffffff', boxShadow: 'var(--shadow-drawer, -4px 0 24px rgba(0,0,0,0.12))', zIndex: 101,
        display: 'flex', flexDirection: 'column', padding: '24px', boxSizing: 'border-box'
      }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
          <div>
            <div style={{ fontSize: '11px', fontWeight: 700, color: '#66776d', letterSpacing: '0.6px' }}>RECORD AUDIT</div>
            <h3 style={{ margin: '4px 0 0 0', fontSize: '18px', fontWeight: 700, color: '#18352f' }}>Transaction Detail</h3>
          </div>
          <button 
            type="button"
            onClick={onClose} 
            style={{ background: 'none', border: 'none', cursor: 'pointer', fontSize: '18px', color: '#66776d' }}
          >
            ✕
          </button>
        </div>

        <div style={{
          background: isCredit ? '#e7f3eb' : '#fee2e2',
          borderRadius: '12px', padding: '20px', textAlign: 'center', marginBottom: '20px'
        }}>
          <div style={{ fontSize: '12px', fontWeight: 600, color: isCredit ? '#1d8a60' : '#dc2626' }}>
            {isCredit ? 'CREDIT / INFLOW' : 'DEBIT / OUTFLOW'}
          </div>
          <div style={{ fontSize: '28px', fontWeight: 700, color: isCredit ? '#1d8a60' : '#dc2626', margin: '6px 0' }}>
            {isCredit ? '+' : '-'}{formatCurrency(transaction.amount, transaction.currency)}
          </div>
          <div style={{ fontSize: '12px', color: '#66776d' }}>{formatDate(transaction.date)}</div>
        </div>

        <div style={{ marginBottom: '20px' }}>
          <label style={{ display: 'block', fontSize: '12px', fontWeight: 700, color: '#66776d', marginBottom: '6px' }}>
            RAW NARRATION
          </label>
          <div style={{ background: '#f4f7f5', padding: '12px', borderRadius: '8px', fontSize: '13px', wordBreak: 'break-all', color: '#18352f' }}>
            {String(transaction.description || '')}
          </div>
        </div>

        <div className="fg-card" style={{ padding: '16px', marginBottom: '20px', background: 'white', borderRadius: '8px', border: '1px solid #e5ebe7' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '8px', fontSize: '13px' }}>
            <span style={{ color: '#66776d' }}>Source File</span>
            <strong style={{ color: '#18352f' }}>{String(transaction.source_file || '')}</strong>
          </div>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '8px', fontSize: '13px' }}>
            <span style={{ color: '#66776d' }}>Source Row</span>
            <span style={{ color: '#18352f' }}>Row #{transaction.source_row}</span>
          </div>
          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '13px' }}>
            <span style={{ color: '#66776d' }}>Closing Balance</span>
            <strong style={{ color: '#18352f' }}>{formatBalance(transaction.balance, transaction.currency)}</strong>
          </div>
        </div>

        <div style={{ marginTop: 'auto', textAlign: 'center' }}>
          <button 
            type="button"
            disabled
            title="AI chat is scheduled for Sprint 2 per team specification"
            style={{
              width: '100%', background: '#e5ebe7', color: '#88998e',
              border: 'none', padding: '12px', borderRadius: '8px', fontWeight: 600, cursor: 'not-allowed',
              fontSize: '13px'
            }}
          >
            Ask FinGenie (Scheduled for Sprint 2)
          </button>
          <div style={{ fontSize: '11px', color: '#88998e', marginTop: '6px' }}>
            AI query analysis is deferred to Sprint 2 per project roadmap.
          </div>
        </div>
      </aside>
    </>
  );
}

export default TransactionDetailDrawer;
