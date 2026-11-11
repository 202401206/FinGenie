import Sidebar from "./Sidebar.jsx";
import "./AppLayout.css";

export const PAGE_INFO = {
  home: {
    title: "Home",
    subtitle: "Your financial workspace",
  },
  dashboard: {
    title: "Financial Dashboard",
    subtitle: "Understand your financial performance",
  },
  transactions: {
    title: "Transactions",
    subtitle: "View and manage your transactions",
  },
  assistant: {
    title: "AI Assistant",
    subtitle: "Get insights into your finances",
  },
  "chat-history": {
    title: "Chat History",
    subtitle: "View your previous conversations",
  },
  settings: {
    title: "Settings",
    subtitle: "Account and application preferences",
  },
};

export default function AppLayout({ activePage, onNavigate, children }) {
  const pageInfo = PAGE_INFO[activePage] || PAGE_INFO.home;

  return (
    <div className="fg-app-layout">
      <Sidebar activePage={activePage} onNavigate={onNavigate} />

      <div className="fg-main-area">
        <header className="fg-topbar">
          <div className="fg-topbar-page-info">
            <h1>{pageInfo.title}</h1>
            <p>{pageInfo.subtitle}</p>
          </div>
        </header>

        <main className="fg-page-content">{children}</main>
      </div>
    </div>
  );
}
