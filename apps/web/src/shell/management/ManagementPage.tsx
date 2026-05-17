import { Link } from "@tanstack/react-router";
import { SkillPackManager } from "./SkillPackManager";

export function ManagementPage() {
  return (
    <main className="management-page">
      <header className="management-topbar">
        <strong className="topbar__brand title-sm">DocAgent</strong>
        <Link className="command-chip" to="/">
          Authoring
        </Link>
      </header>
      <section className="management-page__body">
        <div className="management-page__header">
          <h1>Skill Pack Management</h1>
        </div>
        <SkillPackManager />
      </section>
    </main>
  );
}
