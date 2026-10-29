import { useState } from "react";
import UploadPage from "./features/upload/UploadPage.jsx";
import SettingsPage from "./features/settings/SettingsPage.jsx";

export default function App() {
  const [currentPage, setCurrentPage] = useState("upload");

  return (
    <>
      <div className="dev-page-switcher">
        <button
          type="button"
          className={currentPage === "upload" ? "active" : ""}
          onClick={() => setCurrentPage("upload")}
        >
          Upload
        </button>

        <button
          type="button"
          className={currentPage === "settings" ? "active" : ""}
          onClick={() => setCurrentPage("settings")}
        >
          Settings
        </button>
      </div>

      {currentPage === "upload" ? <UploadPage /> : <SettingsPage />}
    </>
  );
}
