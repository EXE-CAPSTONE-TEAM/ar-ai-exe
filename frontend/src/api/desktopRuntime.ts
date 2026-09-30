import type { AppUpdateInfo, DesktopRuntime, InstallProgress } from "../types";

type TauriGlobal = {
  core?: {
    invoke?: <T>(command: string, args?: Record<string, unknown>) => Promise<T>;
  };
};

declare global {
  interface Window {
    __TAURI__?: TauriGlobal;
  }
}

const FALLBACK_RUNTIME: DesktopRuntime = {
  apiBaseUrl: "http://127.0.0.1:8000",
  backendStatus: "ready",
  blenderStatus: "missing",
  demoProjectStatus: "ready",
  diagnosticSummary: "Desktop runtime commands are not available in this browser context.",
  backendPort: 8000,
  storagePath: "",
  blenderPath: "",
  logsPath: "",
  appVersion: "dev",
  lastError: null,
  // No shell, no handshake: browser/web mode never gets sidecar credentials.
  sidecarToken: null,
};

export function hasDesktopRuntimeBridge(): boolean {
  return typeof window !== "undefined" && typeof window.__TAURI__?.core?.invoke === "function";
}

export async function getDesktopRuntime(): Promise<DesktopRuntime> {
  if (!hasDesktopRuntimeBridge()) {
    return FALLBACK_RUNTIME;
  }
  return window.__TAURI__!.core!.invoke!<DesktopRuntime>("get_desktop_runtime");
}

export async function restartDesktopBackend(): Promise<DesktopRuntime> {
  if (!hasDesktopRuntimeBridge()) {
    return FALLBACK_RUNTIME;
  }
  return window.__TAURI__!.core!.invoke!<DesktopRuntime>("restart_backend");
}

export async function installDesktopDependency(name: "blender"): Promise<InstallProgress> {
  if (!hasDesktopRuntimeBridge()) {
    return {
      name,
      status: "failed",
      message: "Desktop runtime commands are not available in this browser context.",
      percent: 0,
      path: null,
    };
  }
  return window.__TAURI__!.core!.invoke!<InstallProgress>("install_dependency", { name });
}

/** Latest state of the background preview-renderer install (null outside the desktop shell). */
export async function getInstallProgress(): Promise<InstallProgress | null> {
  if (!hasDesktopRuntimeBridge()) {
    return null;
  }
  return window.__TAURI__!.core!.invoke!<InstallProgress>("get_install_progress");
}

/** A newer desktop version found by the startup update check, if any. */
export async function getAppUpdate(): Promise<AppUpdateInfo | null> {
  if (!hasDesktopRuntimeBridge()) {
    return null;
  }
  return window.__TAURI__!.core!.invoke!<AppUpdateInfo | null>("get_app_update");
}

/** Downloads and installs the pending update; the app restarts itself when it succeeds. */
export async function installAppUpdate(): Promise<void> {
  if (!hasDesktopRuntimeBridge()) {
    return;
  }
  await window.__TAURI__!.core!.invoke!("install_app_update");
}

export async function openDiagnosticsFolder(): Promise<void> {
  if (!hasDesktopRuntimeBridge()) {
    return;
  }
  await window.__TAURI__!.core!.invoke!("open_diagnostics_folder");
}

export async function openInBrowser(url: string): Promise<void> {
  if (hasDesktopRuntimeBridge()) {
    try {
      await window.__TAURI__!.core!.invoke!("open_in_browser", { url });
      return;
    } catch {
      // Fallback to window.open if invoke fails
    }
  }
  window.open(url, "_blank", "noopener,noreferrer");
}
