import React from 'react';

export function TopNav({ title = 'Transactions', documentName = 'All Records' }) {
  return (
    <header style={{
      height: '70px', background: 'var(--fg-pure-white)', borderBottom: '1px solid var(--fg-light-grey-green)',
      display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '0 32px',
      position: 'sticky', top: 0, zIndex: 30
    }}>
      <div>
        <div style={{ fontSize: '12px', color: 'var(--fg-muted-grey)' }}>FinGenie / {title}</div>
        <h1 style={{ margin: 0, fontSize: '20px', fontWeight: 700 }}>{title}</h1>
      </div>
      <div style={{
        background: '#F0F5F2', border: '1px solid var(--fg-light-grey-green)',
        padding: '6px 12px', borderRadius: '9999px', fontSize: '12px', fontWeight: 500
      }}>
        <span>Active Document: <strong>{documentName}</strong></span>
      </div>
    </header>
  );
}
