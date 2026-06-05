import { BadgeCheck, Box, CircleHelp, LogIn, LogOut } from "lucide-react";
import type { ReactNode } from "react";

import type { User } from "../../types";

type AppShellProps = {
  user: User | null;
  children: ReactNode;
  onLogout?: () => void;
};

export function AppShell({ user, children, onLogout }: AppShellProps) {
  return (
    <div className="app-shell">
      <a className="skip-link" href="#main-workspace">
        Skip to editor
      </a>
      <header className="topbar">
        <div className="brand-lockup">
          <div className="brand-mark">
            <Box size={18} aria-hidden="true" />
          </div>
          <div className="brand-copy">
            <h1>
              <span>Kus</span>Shoes
            </h1>
            <p>AI + 3D Sneaker Studio</p>
          </div>
        </div>
        <nav className="topbar-nav" aria-label="Primary">
          <a href="#main-workspace">Studio</a>
          <a href="#workflow-guide">Guide</a>
          <a href="#export-tools">Export</a>
        </nav>
        <div className="topbar-actions">
          {user ? (
            <a className="help-link topbar-cta" href="#workflow-guide">
              <CircleHelp size={16} aria-hidden="true" />
              <span>Open Kus Studio</span>
            </a>
          ) : null}
          <div className="auth-pill">
            {user ? <BadgeCheck size={16} aria-hidden="true" /> : <LogIn size={16} aria-hidden="true" />}
            <span>{user ? user.email : "Demo login pending"}</span>
          </div>
          {user && onLogout ? (
            <button type="button" className="topbar-logout" onClick={onLogout}>
              <LogOut size={16} aria-hidden="true" />
              Sign out
            </button>
          ) : null}
        </div>
      </header>
      {children}
    </div>
  );
}
