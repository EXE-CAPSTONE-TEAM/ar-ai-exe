import "@fontsource/anton/400.css";
import "@fontsource/be-vietnam-pro/400.css";
import "@fontsource/be-vietnam-pro/500.css";
import "@fontsource/be-vietnam-pro/600.css";
import "@fontsource/be-vietnam-pro/700.css";
import "@fontsource/be-vietnam-pro/800.css";
import "@fontsource/space-mono/400.css";
import "@fontsource/space-mono/700.css";
import "./DesktopLauncher.css";

import {
  AlertTriangle,
  Box,
  Cloud,
  Copy,
  HardDrive,
  Link2,
  Loader2,
  LogIn,
  LogOut,
  RefreshCw,
  Smartphone,
  Upload,
  UserPlus,
  X,
} from "lucide-react";
import { useState } from "react";
import type { FormEvent, ReactNode } from "react";

import logoUrl from "../../assets/desktop/kusshoes-logo.png";
import shoeUrl from "../../assets/desktop/kusshoes-mid.jpg";
import paintLeftUrl from "../../assets/desktop/paint-left.png";
import paintRightUrl from "../../assets/desktop/paint-right.png";
import type { CloudProject, User } from "../../types";

export type DesktopApiMode = "local" | "cloud";

/** Customer-facing health of whatever backs the current mode. */
export type DesktopEngineState = "ready" | "starting" | "failed";

export type DesktopAuthForm = {
  mode: "login" | "register";
  name: string;
  email: string;
  password: string;
  isBusy: boolean;
  statusMessage: string | null;
  onModeChange: (mode: "login" | "register") => void;
  onNameChange: (value: string) => void;
  onEmailChange: (value: string) => void;
  onPasswordChange: (value: string) => void;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
};

type DesktopLauncherProps = {
  mode: DesktopApiMode;
  onModeChange: (mode: DesktopApiMode) => void;
  user: User | null;
  onLogout: () => void;
  engineState: DesktopEngineState;
  engineError: string | null;
  onRetryEngine: () => void;
  /** Resolves true once the diagnostics summary is on the clipboard. */
  onCopyDiagnostics: () => Promise<boolean>;
  /** First-run renderer install and app-update notices. */
  setupBanner: ReactNode;
  projects: CloudProject[];
  isProjectsLoading: boolean;
  projectsError: string | null;
  onRefreshProjects: () => void;
  onOpenProject: (projectId: string) => void;
  linkValue: string;
  linkError: string | null;
  onLinkChange: (value: string) => void;
  onLinkSubmit: (event: FormEvent<HTMLFormElement>) => void;
  isImportOpen: boolean;
  onToggleImport: () => void;
  importPanel: ReactNode;
  auth: DesktopAuthForm;
};

export function DesktopLauncher(props: DesktopLauncherProps) {
  const { mode, user, engineState } = props;
  const [isLinkOpen, setIsLinkOpen] = useState(false);
  const needsSignIn = mode === "cloud" && engineState === "ready" && !user;
  const canUseEngine = engineState === "ready";

  return (
    <div className="kd-launcher">
      <img className="kd-paint kd-paint-left" src={paintLeftUrl} alt="" aria-hidden="true" draggable={false} />
      <img className="kd-paint kd-paint-right" src={paintRightUrl} alt="" aria-hidden="true" draggable={false} />

      <header className="kd-topbar">
        <div className="kd-brand">
          <img src={logoUrl} alt="KusShoes" />
          <span>Studio</span>
        </div>
        <div className="kd-topbar-actions">
          <EnginePill mode={mode} state={engineState} />
          {user ? (
            <div className="kd-account">
              <span className="kd-avatar" aria-hidden="true">
                {(user.name || user.email).trim().charAt(0).toUpperCase()}
              </span>
              <span className="kd-account-name">{user.name || user.email}</span>
              <button type="button" className="kd-icon-button" aria-label="Đăng xuất" onClick={props.onLogout}>
                <LogOut size={18} aria-hidden="true" />
              </button>
            </div>
          ) : null}
        </div>
      </header>

      <main className="kd-main" id="main-workspace">
        {props.setupBanner}

        {engineState === "failed" ? (
          <EngineProblem
            mode={mode}
            message={props.engineError}
            onRetry={props.onRetryEngine}
            onCopyDiagnostics={props.onCopyDiagnostics}
          />
        ) : null}

        <section className="kd-hero">
          <div className="kd-hero-copy">
            <span className="kd-eyebrow">Digitize &amp; Design System</span>
            <h1>
              Custom đôi giày
              <br />
              theo cách <em>của bạn.</em>
            </h1>
            <p>
              Mở project quét từ điện thoại hoặc import model 3D. Dán sticker, viết chữ, xem preview rồi xuất
              file — ngay trên máy bạn.
            </p>
            <div className="kd-hero-actions">
              {mode === "local" ? (
                <button
                  type="button"
                  className="kd-button kd-button-primary"
                  disabled={!canUseEngine}
                  aria-expanded={props.isImportOpen}
                  onClick={props.onToggleImport}
                >
                  <Upload size={18} aria-hidden="true" />
                  Import model 3D
                  <span className="kd-chip-dark">GLB · OBJ</span>
                </button>
              ) : null}
              <button
                type="button"
                className={`kd-button ${mode === "local" ? "kd-button-secondary" : "kd-button-primary"}`}
                aria-expanded={isLinkOpen}
                onClick={() => setIsLinkOpen((current) => !current)}
              >
                <Link2 size={18} aria-hidden="true" />
                Dán link project
              </button>
            </div>
          </div>
          <img className="kd-hero-shoe" src={shoeUrl} alt="Giày KusShoes mid-top đen trắng cam" />
        </section>

        {isLinkOpen ? (
          <form className="kd-card kd-link-form" onSubmit={props.onLinkSubmit}>
            <label>
              Link hoặc mã project
              <input
                value={props.linkValue}
                onChange={(event) => props.onLinkChange(event.target.value)}
                placeholder="Dán link editor hoặc mã proj_…"
                autoFocus
              />
            </label>
            <button type="submit" className="kd-button kd-button-dark" disabled={!canUseEngine}>
              Mở project
            </button>
            <button
              type="button"
              className="kd-icon-button"
              aria-label="Đóng"
              onClick={() => setIsLinkOpen(false)}
            >
              <X size={18} aria-hidden="true" />
            </button>
            {props.linkError ? <p className="kd-form-error">{props.linkError}</p> : null}
          </form>
        ) : null}

        {mode === "local" && props.isImportOpen ? (
          <section className="kd-card kd-import-card">
            <div className="kd-card-header">
              <h2>Import model 3D</h2>
              <button type="button" className="kd-icon-button" aria-label="Đóng import" onClick={props.onToggleImport}>
                <X size={18} aria-hidden="true" />
              </button>
            </div>
            {props.importPanel}
          </section>
        ) : null}

        {needsSignIn ? (
          <SignInCard auth={props.auth} onUseLocal={() => props.onModeChange("local")} />
        ) : (
          <ProjectsSection {...props} canOpen={canUseEngine} />
        )}
      </main>
    </div>
  );
}

function EnginePill({ mode, state }: { mode: DesktopApiMode; state: DesktopEngineState }) {
  const label =
    state === "ready"
      ? mode === "local"
        ? "Máy sẵn sàng · offline"
        : "Đã kết nối cloud"
      : state === "starting"
        ? "Đang khởi động…"
        : mode === "local"
          ? "Xưởng vẽ chưa chạy"
          : "Chưa kết nối cloud";
  return (
    <span className={`kd-pill kd-pill-${state}`} role="status">
      {state === "starting" ? <Loader2 size={14} className="spin" aria-hidden="true" /> : <span className="kd-dot" />}
      {label}
    </span>
  );
}

function EngineProblem({
  mode,
  message,
  onRetry,
  onCopyDiagnostics,
}: {
  mode: DesktopApiMode;
  message: string | null;
  onRetry: () => void;
  onCopyDiagnostics: () => Promise<boolean>;
}) {
  const [copyState, setCopyState] = useState<"idle" | "copied" | "failed">("idle");

  async function copyDiagnostics() {
    setCopyState((await onCopyDiagnostics()) ? "copied" : "failed");
  }

  return (
    <section className="kd-card kd-problem" role="alert">
      <span className="kd-problem-icon" aria-hidden="true">
        <AlertTriangle size={20} />
      </span>
      <div className="kd-problem-body">
        <strong>{mode === "local" ? "Chưa khởi động được xưởng vẽ trên máy" : "Chưa kết nối được cloud"}</strong>
        <p>
          {mode === "local"
            ? "Bấm Thử lại. Nếu vẫn lỗi, sao chép thông tin lỗi và gửi cho đội KusShoes."
            : "Kiểm tra kết nối mạng, hoặc chuyển sang chế độ Trên máy để làm việc offline."}
        </p>
        {message ? (
          <details>
            <summary>Chi tiết kỹ thuật</summary>
            <code>{message}</code>
          </details>
        ) : null}
      </div>
      <div className="kd-problem-actions">
        {mode === "local" ? (
          <button type="button" className="kd-button kd-button-primary kd-button-sm" onClick={onRetry}>
            <RefreshCw size={16} aria-hidden="true" />
            Thử lại
          </button>
        ) : null}
        <button type="button" className="kd-button kd-button-secondary kd-button-sm" onClick={() => void copyDiagnostics()}>
          <Copy size={16} aria-hidden="true" />
          {copyState === "copied" ? "Đã sao chép" : copyState === "failed" ? "Chưa sao chép được" : "Sao chép thông tin lỗi"}
        </button>
      </div>
    </section>
  );
}

function ModeSwitch({ mode, onChange }: { mode: DesktopApiMode; onChange: (mode: DesktopApiMode) => void }) {
  return (
    <div className="kd-mode-switch" role="tablist" aria-label="Nơi lưu project">
      <button type="button" role="tab" aria-selected={mode === "local"} onClick={() => onChange("local")}>
        <HardDrive size={16} aria-hidden="true" />
        <span>
          Trên máy
          <small>Không cần mạng</small>
        </span>
      </button>
      <button type="button" role="tab" aria-selected={mode === "cloud"} onClick={() => onChange("cloud")}>
        <Cloud size={16} aria-hidden="true" />
        <span>
          Cloud
          <small>Đồng bộ với điện thoại</small>
        </span>
      </button>
    </div>
  );
}

function ProjectsSection({
  mode,
  onModeChange,
  engineState,
  projects,
  isProjectsLoading,
  projectsError,
  onRefreshProjects,
  onOpenProject,
  canOpen,
}: DesktopLauncherProps & { canOpen: boolean }) {
  return (
    <section className="kd-projects" aria-labelledby="kd-projects-title">
      <div className="kd-projects-header">
        <div className="kd-projects-title">
          <h2 id="kd-projects-title">Project của bạn</h2>
          <span className="kd-count">{projects.length}</span>
        </div>
        <div className="kd-projects-tools">
          <ModeSwitch mode={mode} onChange={onModeChange} />
          <button
            type="button"
            className="kd-icon-button kd-icon-button-bordered"
            aria-label="Làm mới danh sách"
            disabled={!canOpen}
            onClick={onRefreshProjects}
          >
            <RefreshCw size={18} className={isProjectsLoading ? "spin" : ""} aria-hidden="true" />
          </button>
        </div>
      </div>

      {projectsError ? <p className="kd-form-error">{projectsError}</p> : null}

      <div className="kd-project-grid">
        <div className="kd-scan-card">
          <span className="kd-scan-icon" aria-hidden="true">
            <Smartphone size={22} />
          </span>
          <h3>Quét giày bằng điện thoại</h3>
          <ol>
            <li>Mở app KusShoes</li>
            <li>Quay quanh đôi giày</li>
            <li>Bấm “Mở trên Desktop”</li>
          </ol>
          <p>{mode === "cloud" ? "Project mới sẽ tự hiện ở đây." : "Chuyển sang Cloud để thấy project quét từ điện thoại."}</p>
        </div>

        {engineState === "starting" && projects.length === 0 ? (
          <div className="kd-project-empty">
            <Loader2 size={20} className="spin" aria-hidden="true" />
            Đang khởi động xưởng vẽ…
          </div>
        ) : null}

        {engineState === "ready" && !isProjectsLoading && projects.length === 0 ? (
          <div className="kd-project-empty">
            {mode === "local" ? "Chưa có project trên máy. Import một model 3D để bắt đầu." : "Chưa có project nào trên cloud."}
          </div>
        ) : null}

        {projects.map((project) => (
          <ProjectCard key={project.id} project={project} canOpen={canOpen} onOpen={onOpenProject} />
        ))}
      </div>
    </section>
  );
}

const PROJECT_STATUS: Record<CloudProject["status"], { label: string; tone: string }> = {
  ready: { label: "Sẵn sàng", tone: "ready" },
  processing: { label: "Đang xử lý", tone: "working" },
  draft: { label: "Chưa có model", tone: "neutral" },
  failed: { label: "Lỗi xử lý", tone: "failed" },
  archived: { label: "Đã lưu trữ", tone: "neutral" },
};

function ProjectCard({
  project,
  canOpen,
  onOpen,
}: {
  project: CloudProject;
  canOpen: boolean;
  onOpen: (projectId: string) => void;
}) {
  const [thumbnailFailed, setThumbnailFailed] = useState(false);
  const status = PROJECT_STATUS[project.status] ?? { label: project.status, tone: "neutral" };
  const isReady = project.status === "ready";
  const thumbnail = project.thumbnailUrl && !thumbnailFailed ? project.thumbnailUrl : null;

  return (
    <article className="kd-project-card">
      <div className={`kd-project-thumb ${thumbnail ? "" : "placeholder"} ${status.tone}`}>
        {thumbnail ? (
          <img src={thumbnail} alt="" onError={() => setThumbnailFailed(true)} />
        ) : project.status === "draft" ? (
          <Box size={40} strokeWidth={1.6} aria-hidden="true" />
        ) : (
          <img src={shoeUrl} alt="" />
        )}
        {project.status === "processing" ? (
          <div className="kd-thumb-progress">
            <span>Đang dựng 3D…</span>
            <div className="kd-progress indeterminate">
              <span />
            </div>
          </div>
        ) : null}
      </div>
      <div className="kd-project-body">
        <h3 title={project.name}>{project.name}</h3>
        <span className="kd-project-date">Cập nhật {formatDate(project.updatedAt)}</span>
        <div className="kd-project-footer">
          <span className={`kd-status kd-status-${status.tone}`}>{status.label}</span>
          <button
            type="button"
            className="kd-button kd-button-dark kd-button-sm"
            disabled={!isReady || !canOpen}
            aria-label={`Mở ${project.name}`}
            onClick={() => onOpen(project.id)}
          >
            {isReady ? "Mở" : "Chờ"}
          </button>
        </div>
      </div>
    </article>
  );
}

function SignInCard({ auth, onUseLocal }: { auth: DesktopAuthForm; onUseLocal: () => void }) {
  return (
    <section className="kd-signin">
      <form className="kd-card kd-signin-card" onSubmit={auth.onSubmit}>
        <div className="kd-signin-brand">
          <img src={logoUrl} alt="KusShoes" />
          <span>KusStudio · Desktop</span>
        </div>
        <div className="kd-auth-tabs" role="tablist" aria-label="Đăng nhập hoặc đăng ký">
          <button
            type="button"
            role="tab"
            aria-selected={auth.mode === "login"}
            onClick={() => auth.onModeChange("login")}
          >
            <LogIn size={16} aria-hidden="true" />
            Đăng nhập
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={auth.mode === "register"}
            onClick={() => auth.onModeChange("register")}
          >
            <UserPlus size={16} aria-hidden="true" />
            Đăng ký
          </button>
        </div>
        {auth.mode === "register" ? (
          <label>
            Tên của bạn
            <input value={auth.name} onChange={(event) => auth.onNameChange(event.target.value)} required minLength={1} />
          </label>
        ) : null}
        <label>
          Email
          <input
            type="email"
            autoComplete="email"
            placeholder="ban@email.com"
            value={auth.email}
            onChange={(event) => auth.onEmailChange(event.target.value)}
            required
          />
        </label>
        <label>
          Mật khẩu
          <input
            type="password"
            autoComplete={auth.mode === "login" ? "current-password" : "new-password"}
            value={auth.password}
            onChange={(event) => auth.onPasswordChange(event.target.value)}
            required
            minLength={auth.mode === "register" ? 8 : 1}
          />
        </label>
        <button type="submit" className="kd-button kd-button-primary kd-button-block" disabled={auth.isBusy}>
          {auth.isBusy ? <Loader2 size={18} className="spin" aria-hidden="true" /> : <LogIn size={18} aria-hidden="true" />}
          {auth.mode === "login" ? "Vào studio" : "Tạo tài khoản"}
        </button>
        {auth.statusMessage ? <p className="kd-form-error" role="status">{auth.statusMessage}</p> : null}
        <p className="kd-signin-hint">
          Dùng chung tài khoản với app điện thoại và web KusShoes.{" "}
          <button type="button" className="kd-text-button" onClick={onUseLocal}>
            Làm việc offline trên máy
          </button>
        </p>
      </form>
    </section>
  );
}

function formatDate(value: string): string {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "—" : date.toLocaleDateString("vi-VN");
}
