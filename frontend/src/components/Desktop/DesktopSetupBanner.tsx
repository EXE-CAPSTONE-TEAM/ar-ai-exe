import { useEffect, useRef, useState } from "react";
import { listen } from "@tauri-apps/api/event";
import { AlertTriangle, CheckCircle2, Download, Loader2, RefreshCw } from "lucide-react";

import {
  getAppUpdate,
  getInstallProgress,
  hasDesktopRuntimeBridge,
  installAppUpdate,
  installDesktopDependency,
} from "../../api/desktopRuntime";
import type { AppUpdateInfo, AppUpdateProgress, InstallProgress } from "../../types";
import { setupBannerView, updatePercent } from "../../utils/desktopSetup";

/** How long the "ready" confirmation stays after a first-run install finishes. */
const DONE_BANNER_MS = 4000;

type DesktopSetupBannerProps = {
  /** Called once the preview renderer finished installing in this session. */
  onRendererInstalled?: () => void;
};

/**
 * First-run and update notices for the desktop shell. The renderer install and the update
 * check both start in the Rust shell at launch; this only mirrors their events.
 */
export function DesktopSetupBanner({ onRendererInstalled }: DesktopSetupBannerProps) {
  const [install, setInstall] = useState<InstallProgress | null>(null);
  const [update, setUpdate] = useState<AppUpdateInfo | null>(null);
  const [updateProgress, setUpdateProgress] = useState<AppUpdateProgress | null>(null);
  const [updateState, setUpdateState] = useState<"idle" | "installing" | "failed">("idle");
  const [updateError, setUpdateError] = useState<string | null>(null);
  const [showDone, setShowDone] = useState(false);
  const installedCallback = useRef(onRendererInstalled);
  installedCallback.current = onRendererInstalled;

  useEffect(() => {
    if (!hasDesktopRuntimeBridge()) {
      return;
    }
    let active = true;
    const unlisteners: Array<Promise<() => void>> = [
      listen<InstallProgress>("dependency-install-progress", (event) => {
        setInstall(event.payload);
        if (event.payload.status === "installed") {
          setShowDone(true);
          installedCallback.current?.();
        }
      }),
      listen<AppUpdateInfo>("app-update-available", (event) => setUpdate(event.payload)),
      listen<AppUpdateProgress>("app-update-progress", (event) => setUpdateProgress(event.payload)),
    ];
    // Events emitted before this window subscribed are recovered from the shell's state.
    void getInstallProgress()
      .then((progress) => active && progress && setInstall((current) => current ?? progress))
      .catch(() => undefined);
    void getAppUpdate()
      .then((info) => active && info && setUpdate((current) => current ?? info))
      .catch(() => undefined);
    return () => {
      active = false;
      unlisteners.forEach((unlisten) => void unlisten.then((stop) => stop()));
    };
  }, []);

  useEffect(() => {
    if (!showDone) {
      return;
    }
    const timer = window.setTimeout(() => setShowDone(false), DONE_BANNER_MS);
    return () => window.clearTimeout(timer);
  }, [showDone]);

  const view = setupBannerView(install);
  const visibleSetup = view && (view.tone !== "done" || showDone) ? view : null;

  async function retryInstall() {
    try {
      setInstall(await installDesktopDependency("blender"));
    } catch (error) {
      setInstall({
        name: "blender",
        status: "failed",
        stage: "failed",
        message: error instanceof Error ? error.message : String(error),
        percent: 0,
      });
    }
  }

  async function startUpdate() {
    setUpdateState("installing");
    setUpdateError(null);
    try {
      await installAppUpdate();
    } catch (error) {
      setUpdateState("failed");
      setUpdateError(error instanceof Error ? error.message : String(error));
    }
  }

  if (!visibleSetup && !update) {
    return null;
  }

  const updateBarPercent = updatePercent(updateProgress);

  return (
    <div className="desktop-setup-stack">
      {visibleSetup ? (
        <section
          className={`desktop-setup-banner ${visibleSetup.tone}`}
          role={visibleSetup.tone === "error" ? "alert" : "status"}
          aria-live="polite"
        >
          <span className="desktop-setup-icon" aria-hidden="true">
            {visibleSetup.tone === "progress" ? (
              <Loader2 size={18} className="spin" />
            ) : visibleSetup.tone === "error" ? (
              <AlertTriangle size={18} />
            ) : (
              <CheckCircle2 size={18} />
            )}
          </span>
          <div className="desktop-setup-body">
            <strong>{visibleSetup.title}</strong>
            <p>{visibleSetup.detail}</p>
            {visibleSetup.tone === "progress" ? (
              <>
                <ProgressBar percent={visibleSetup.percent} label="Tiến trình cài đặt" />
                <p className="desktop-setup-hint">
                  Bạn vẫn có thể dùng app trong lúc chờ; xem trước và xuất 3D sẽ bật khi cài xong.
                </p>
              </>
            ) : null}
          </div>
          {visibleSetup.canRetry ? (
            <button type="button" className="desktop-setup-action" onClick={() => void retryInstall()}>
              <RefreshCw size={14} aria-hidden="true" />
              Thử lại
            </button>
          ) : null}
        </section>
      ) : null}

      {update ? (
        <section className="desktop-setup-banner update" role="status" aria-live="polite">
          <span className="desktop-setup-icon" aria-hidden="true">
            <Download size={18} />
          </span>
          <div className="desktop-setup-body">
            <strong>Có phiên bản mới {update.version}</strong>
            <p>
              {updateState === "installing"
                ? "Đang tải bản cập nhật; app sẽ tự khởi động lại khi xong."
                : updateState === "failed"
                  ? updateError ?? "Cập nhật thất bại."
                  : `Bạn đang dùng ${update.currentVersion}.`}
            </p>
            {updateState === "installing" ? (
              <ProgressBar percent={updateBarPercent} label="Tiến trình cập nhật" />
            ) : null}
          </div>
          {updateState !== "installing" ? (
            <button type="button" className="desktop-setup-action" onClick={() => void startUpdate()}>
              <Download size={14} aria-hidden="true" />
              {updateState === "failed" ? "Thử lại" : "Cập nhật ngay"}
            </button>
          ) : null}
        </section>
      ) : null}
    </div>
  );
}

function ProgressBar({ percent, label }: { percent: number | null; label: string }) {
  return (
    <div
      className={`desktop-setup-progress ${percent === null ? "indeterminate" : ""}`}
      role="progressbar"
      aria-label={label}
      aria-valuemin={0}
      aria-valuemax={100}
      aria-valuenow={percent ?? undefined}
    >
      <span style={percent === null ? undefined : { width: `${percent}%` }} />
      {percent !== null ? <em>{percent}%</em> : null}
    </div>
  );
}
