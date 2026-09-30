import type { AppUpdateProgress, InstallProgress } from "../types";

export type SetupBannerView = {
  tone: "progress" | "error" | "done";
  title: string;
  detail: string;
  /** null = indeterminate bar. */
  percent: number | null;
  canRetry: boolean;
  /** Raw shell message, shown only behind a "technical details" toggle. */
  technicalDetail: string | null;
};

/** What the first-run banner shows for a renderer install state; null hides it. */
export function setupBannerView(progress: InstallProgress | null): SetupBannerView | null {
  if (!progress) {
    return null;
  }
  if (progress.status === "downloading") {
    return {
      tone: "progress",
      title: "Đang chuẩn bị xưởng vẽ 3D (chỉ lần đầu)",
      detail: progress.message,
      percent: progress.percent > 0 ? clampPercent(progress.percent) : null,
      canRetry: false,
      technicalDetail: null,
    };
  }
  if (progress.status === "failed") {
    return {
      tone: "error",
      title: "Chưa tải xong bộ dựng hình 3D",
      detail: "Kiểm tra kết nối mạng rồi bấm Thử lại. Nếu vẫn lỗi, gửi chi tiết kỹ thuật cho đội KusShoes.",
      percent: null,
      canRetry: true,
      technicalDetail: progress.message || null,
    };
  }
  if (progress.status === "installed" && progress.stage === "installed") {
    return {
      tone: "done",
      title: "Xưởng vẽ 3D đã sẵn sàng",
      detail: "Bạn có thể xem preview và xuất file 3D.",
      percent: 100,
      canRetry: false,
      technicalDetail: null,
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
