import type { AppUpdateProgress, InstallProgress } from "../types";

export type SetupBannerView = {
  tone: "progress" | "error" | "done";
  title: string;
  detail: string;
  /** null = indeterminate bar. */
  percent: number | null;
  canRetry: boolean;
};

/** What the first-run banner shows for a renderer install state; null hides it. */
export function setupBannerView(progress: InstallProgress | null): SetupBannerView | null {
  if (!progress) {
    return null;
  }
  if (progress.status === "downloading") {
    return {
      tone: "progress",
      title: "Đang chuẩn bị KusShoes Editor (chỉ lần đầu)",
      detail: progress.message,
      percent: progress.percent > 0 ? clampPercent(progress.percent) : null,
      canRetry: false,
    };
  }
  if (progress.status === "failed") {
    return {
      tone: "error",
      title: "Chưa cài xong bộ dựng hình 3D",
      detail: progress.message,
      percent: null,
      canRetry: true,
    };
  }
  if (progress.status === "installed" && progress.stage === "installed") {
    return {
      tone: "done",
      title: "KusShoes Editor đã sẵn sàng",
      detail: progress.message,
      percent: 100,
      canRetry: false,
    };
  }
  return null;
}

export function updatePercent(progress: AppUpdateProgress | null): number | null {
  if (!progress || progress.totalBytes <= 0) {
    return null;
  }
  return clampPercent((progress.downloadedBytes * 100) / progress.totalBytes);
}

function clampPercent(value: number): number {
  return Math.max(0, Math.min(100, Math.round(value)));
}
