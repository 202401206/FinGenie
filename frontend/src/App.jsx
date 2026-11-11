import { useState } from "react";

import UploadPage from "./features/upload/UploadPage.jsx";
import SettingsPage from "./features/settings/SettingsPage.jsx";

import AppLayout from "./components/layout/AppLayout.jsx";

function PlaceholderPage({ title, description }) {
  return (
    <section className="fg-placeholder-page">
      <span className="fg-step-label">COMING SOON</span>
      <h2>{title}</h2>
      <p>{description}</p>
      <p className="fg-placeholder-note">
        This section will be connected when its development is completed.
      </p>
    </section>
  );
}

export default function App() {
  const [activePage, setActivePage] = useState("home");

  function renderPage() {
    switch (activePage) {
      case "home":
        return <UploadPage />;

      case "settings":
        return <SettingsPage />;

      case "dashboard":
        return (
          <PlaceholderPage
            title="Financial Dashboard"
            description="Your financial summaries, charts and insights will appear here."
          />
        );

      case "transactions":
        return (
          <PlaceholderPage
            title="Transactions"
            description="Your uploaded bank transactions will be displayed here."
          />
        );

      case "assistant":
        return (
          <PlaceholderPage
            title="AI Assistant"
            description="Ask questions and get insights about your finances here."
          />
        );

      case "chat-history":
        return (
          <PlaceholderPage
            title="Chat History"
            description="Your previous AI conversations will appear here."
          />
        );

      default:
        return <UploadPage />;
    }
  }

  return (
    <AppLayout activePage={activePage} onNavigate={setActivePage}>
      {renderPage()}
    </AppLayout>
  );
}
