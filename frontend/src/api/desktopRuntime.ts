import type { DesktopRuntime, InstallProgress } from "../types";

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

export async function openDiagnosticsFolder(): Promise<void> {
  if (!hasDesktopRuntimeBridge()) {
    return;
  }
  await window.__TAURI__!.core!.invoke!("open_diagnostics_folder");
}
