import React from 'react';
import { formatCurrency, formatBalance, formatDate } from '../../utils/formatters.js';

export function TransactionDetailDrawer({ transaction, isOpen, onClose, onAskFinGenie }) {
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
        background: 'var(--fg-pure-white)', boxShadow: 'var(--shadow-drawer)', zIndex: 101,
        display: 'flex', flexDirection: 'column', padding: '24px', boxSizing: 'border-box'
      }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
          <div>
            <div style={{ fontSize: '11px', fontWeight: 700, color: 'var(--fg-muted-grey)' }}>RECORD AUDIT</div>
            <h3 style={{ margin: '4px 0 0 0', fontSize: '18px', fontWeight: 700 }}>Transaction Detail</h3>
          </div>
          <button onClick={onClose} style={{ background: 'none', border: 'none', cursor: 'pointer', fontSize: '16px' }}>✕</button>
        </div>

        <div style={{
          background: isCredit ? 'var(--fg-pale-mint)' : 'var(--fg-soft-red-light)',
          borderRadius: '12px', padding: '20px', textAlign: 'center', marginBottom: '20px'
        }}>
          <div style={{ fontSize: '12px', fontWeight: 600, color: isCredit ? 'var(--fg-emerald-green)' : 'var(--fg-soft-red)' }}>
            {isCredit ? 'CREDIT / INFLOW' : 'DEBIT / OUTFLOW'}
          </div>
          <div style={{ fontSize: '28px', fontWeight: 700, color: isCredit ? 'var(--fg-emerald-green)' : 'var(--fg-soft-red)', margin: '6px 0' }}>
            {isCredit ? '+' : '-'}{formatCurrency(transaction.amount, transaction.currency)}
          </div>
          <div style={{ fontSize: '12px', color: 'var(--fg-muted-grey)' }}>{formatDate(transaction.date)}</div>
        </div>

        <div style={{ marginBottom: '20px' }}>
          <label style={{ display: 'block', fontSize: '12px', fontWeight: 700, color: 'var(--fg-muted-grey)', marginBottom: '6px' }}>
            RAW NARRATION
          </label>
          <div style={{ background: 'var(--fg-warm-white)', padding: '12px', borderRadius: '8px', fontSize: '13px', wordBreak: 'break-all' }}>
            {transaction.description}
          </div>
        </div>

        <div className="fg-card" style={{ padding: '16px', marginBottom: '20px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '8px' }}>
            <span style={{ color: 'var(--fg-muted-grey)' }}>Source File</span>
            <strong>{transaction.source_file}</strong>
          </div>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '8px' }}>
            <span style={{ color: 'var(--fg-muted-grey)' }}>Source Row</span>
            <span>Row #{transaction.source_row}</span>
          </div>
          <div style={{ display: 'flex', justifyContent: 'space-between' }}>
            <span style={{ color: 'var(--fg-muted-grey)' }}>Closing Balance</span>
            <strong>{formatBalance(transaction.balance, transaction.currency)}</strong>
          </div>
        </div>

        <button 
          onClick={() => onAskFinGenie && onAskFinGenie(transaction)}
          style={{
            marginTop: 'auto', background: 'var(--fg-forest-green)', color: 'white',
            border: 'none', padding: '12px', borderRadius: '8px', fontWeight: 600, cursor: 'pointer'
          }}
        >
          Ask FinGenie About This Transaction
        </button>
      </aside>
    </>
  );
}
