import React from 'react';

export function Sidebar({ activeTab, onNavigate, onLogout, user }) {
  const tabs = [
    { id: 'dashboard', label: 'Financial Dashboard' },
    { id: 'transactions', label: 'Transactions' },
    { id: 'assistant', label: 'AI Assistant' },
    { id: 'settings', label: 'Settings' }
  ];

  return (
    <aside style={{
      width: '240px', height: '100vh', background: 'var(--fg-pure-white)',
      borderRight: '1px solid var(--fg-light-grey-green)', display: 'flex', flexDirection: 'column',
      position: 'sticky', top: 0, flexShrink: 0
    }}>
      <div style={{ padding: '24px 20px', borderBottom: '1px solid var(--fg-warm-white)' }}>
        <div style={{ fontSize: '18px', fontWeight: 700, color: 'var(--fg-forest-green)' }}>FinGenie</div>
        <div style={{ fontSize: '11px', color: 'var(--fg-muted-grey)' }}>INTELLIGENT FINANCE</div>
      </div>

      <nav style={{ flex: 1, padding: '20px 12px' }}>
        {tabs.map(t => (
          <button
            key={t.id}
            onClick={() => onNavigate(t.id)}
            style={{
              width: '100%', textAlign: 'left', padding: '10px 14px', borderRadius: '8px',
              border: 'none', cursor: 'pointer', marginBottom: '4px',
              background: activeTab === t.id ? 'var(--fg-pale-mint)' : 'transparent',
              color: activeTab === t.id ? 'var(--fg-emerald-green)' : 'var(--fg-charcoal)',
              fontWeight: activeTab === t.id ? 600 : 500
            }}
          >
            {t.label}
          </button>
        ))}
      </nav>

      <div style={{ padding: '16px', borderTop: '1px solid var(--fg-light-grey-green)', background: '#FAFBF9' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div>
            <div style={{ fontSize: '13px', fontWeight: 600 }}>{user?.email || 'Demo User'}</div>
            <div style={{ fontSize: '11px', color: 'var(--fg-muted-grey)' }}>Active Workspace</div>
          </div>
          <button onClick={onLogout} style={{ background: 'none', border: 'none', cursor: 'pointer', fontSize: '12px', color: 'var(--fg-soft-red)' }}>
            Logout
          </button>
        </div>
      </div>
    </aside>
  );
}
