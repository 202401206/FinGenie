import "./Sidebar.css";

const NAV_ITEMS = [
  { id: "home", label: "Home", icon: "home" },
  {
    id: "dashboard",
    label: "Financial Dashboard",
    icon: "dashboard",
  },
  {
    id: "transactions",
    label: "Transactions",
    icon: "transactions",
  },
  {
    id: "assistant",
    label: "AI Assistant",
    icon: "assistant",
  },
  {
    id: "chat-history",
    label: "Chat History",
    icon: "history",
  },
  { id: "settings", label: "Settings", icon: "settings" },
];

function NavIcon({ name }) {
  const common = {
    width: 20,
    height: 20,
    viewBox: "0 0 24 24",
    fill: "none",
    stroke: "currentColor",
    strokeWidth: 1.8,
    strokeLinecap: "round",
    strokeLinejoin: "round",
    "aria-hidden": true,
  };

  switch (name) {
    case "home":
      return (
        <svg {...common}>
          <path d="m3 10 9-7 9 7" />
          <path d="M5 9v11h14V9" />
          <path d="M9 20v-7h6v7" />
        </svg>
      );

    case "dashboard":
      return (
        <svg {...common}>
          <rect x="3" y="3" width="7" height="7" rx="1.5" />
          <rect x="14" y="3" width="7" height="7" rx="1.5" />
          <rect x="3" y="14" width="7" height="7" rx="1.5" />
          <rect x="14" y="14" width="7" height="7" rx="1.5" />
        </svg>
      );

    case "transactions":
      return (
        <svg {...common}>
          <path d="M7 7h13l-3-3" />
          <path d="m20 7-3 3" />
          <path d="M17 17H4l3 3" />
          <path d="m4 17 3-3" />
        </svg>
      );

    case "assistant":
      return (
        <svg {...common}>
          <path d="m12 3 1.8 5.2L19 10l-5.2 1.8L12 17l-1.8-5.2L5 10l5.2-1.8L12 3Z" />
          <path d="m19 15 .9 2.1L22 18l-2.1.9L19 21l-.9-2.1L16 18l2.1-.9L19 15Z" />
          <path d="m5 16 .7 1.3L7 18l-1.3.7L5 20l-.7-1.3L3 18l1.3-.7L5 16Z" />
        </svg>
      );

    case "history":
      return (
        <svg {...common}>
          <path d="M3 12a9 9 0 1 0 2.6-6.4L3 8" />
          <path d="M3 3v5h5" />
          <path d="M12 7v5l3 2" />
        </svg>
      );

    case "settings":
      return (
        <svg {...common}>
          <circle cx="12" cy="12" r="3" />
          <path d="m19.4 15 .1.1 1.4 1.1-1.4 2.4-1.7-.7a8 8 0 0 1-1.7 1l-.3 1.8h-2.8l-.3-1.8a8 8 0 0 1-1.7-1l-1.7.7-1.4-2.4 1.4-1.1a7 7 0 0 1 0-2l-1.4-1.1 1.4-2.4 1.7.7a8 8 0 0 1 1.7-1l.3-1.8h2.8l.3 1.8a8 8 0 0 1 1.7 1l1.7-.7 1.4 2.4-1.4 1.1a7 7 0 0 1 0 2Z" />
        </svg>
      );

    default:
      return null;
  }
}

export default function Sidebar({ activePage, onNavigate }) {
  return (
    <aside className="fg-sidebar">
      <div className="fg-sidebar-brand">
        <div className="fg-sidebar-logo">F</div>
        <span>FinGenie</span>
      </div>

      <nav className="fg-sidebar-nav" aria-label="Main navigation">
        {NAV_ITEMS.map((item) => {
          const isActive = activePage === item.id;

          return (
            <button
              key={item.id}
              type="button"
              className={`fg-nav-item ${isActive ? "active" : ""}`}
              onClick={() => onNavigate(item.id)}
              aria-current={isActive ? "page" : undefined}
            >
              <NavIcon name={item.icon} />
              <span>{item.label}</span>
            </button>
          );
        })}
      </nav>

      <div className="fg-sidebar-footer">
        <div className="fg-account-avatar">F</div>

        <div className="fg-account-details">
          <strong>FinGenie Account</strong>
          <span>Financial workspace</span>
        </div>
      </div>
    </aside>
  );
}
