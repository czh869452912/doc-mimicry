import { LayoutDashboard, PanelsTopLeft } from "lucide-react";
import { useState } from "react";
import { ManagementPage } from "./pages/ManagementPage";
import { WorkbenchPage } from "./pages/WorkbenchPage";

type Page = "management" | "workbench";

export function App() {
  const [page, setPage] = useState<Page>("workbench");

  return (
    <main className="app-shell">
      <nav className="topbar">
        <strong>DocAgent Workbench</strong>
        <button className={page === "workbench" ? "active" : ""} onClick={() => setPage("workbench")}>
          <PanelsTopLeft size={16} /> Workbench
        </button>
        <button className={page === "management" ? "active" : ""} onClick={() => setPage("management")}>
          <LayoutDashboard size={16} /> Management
        </button>
      </nav>
      {page === "management" ? <ManagementPage /> : <WorkbenchPage />}
    </main>
  );
}
