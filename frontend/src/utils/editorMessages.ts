import { ApiError } from "../api/client";
import { EditorApiError } from "../api/editorClient";

export type NoticeTone = "neutral" | "loading" | "success" | "warning" | "error";

export type EditorNotice = {
  tone: NoticeTone;
  title: string;
  detail: string;
};

export function editorRouteStateLabel(state: string): string {
  const labels: Record<string, string> = {
    idle: "Editor chưa mở dự án",
    AUTH_CHECKING: "Đang kiểm tra đăng nhập",
    UNAUTHENTICATED: "Cần đăng nhập để mở editor",
    PROJECT_LOADING: "Đang mở dự án",
    PROJECT_NOT_FOUND: "Không tìm thấy dự án",
    MODEL_PROCESSING: "Mẫu 3D đang được chuẩn bị",
    EDITOR_READY: "Editor đã sẵn sàng",
  };
  return labels[state] ?? "Editor đang xử lý";
}

export function friendlyInlineMessage(message: string): string {
  const notice = noticeFromStatus(message, false);
  return notice.detail;
}

export function noticeFromStatus(message: string, isBusy: boolean): EditorNotice {
  const rawMessage = message.trim();
  const normalizedMessage = cleanTechnicalMessage(rawMessage);
  const loweredRaw = rawMessage.toLowerCase();
  const lowered = normalizedMessage.toLowerCase();

  if (
    isBusy ||
    rawMessage === "SAVING_DRAFT" ||
    rawMessage === "BAKING" ||
    rawMessage === "EXPORTING" ||
    lowered.includes("loading") ||
    lowered.includes("importing") ||
    lowered.includes("signing in") ||
    lowered.includes("creating account") ||
    lowered.includes("creating export") ||
    lowered.includes("creating zip") ||
    lowered.includes("downloading")
  ) {
    if (rawMessage === "BAKING") {
      return {
        tone: "loading",
        title: "Đang áp hình lên giày",
        detail: "Ứng dụng đang tạo bản xem trước 3D mới. Bước này có thể mất một lúc.",
      };
    }
    if (rawMessage === "SAVING_DRAFT") {
      return {
        tone: "loading",
        title: "Đang lưu bản nháp",
        detail: "Ứng dụng đang lưu thiết kế trước khi áp hình lên giày.",
      };
    }
    if (rawMessage === "EXPORTING" || lowered.includes("export") || lowered.includes("zip")) {
      return {
        tone: "loading",
        title: "Đang chuẩn bị file xuất",
        detail: "Ứng dụng đang đóng gói file thiết kế để tải xuống.",
      };
    }
    if (lowered.includes("import")) {
      return {
        tone: "loading",
        title: "Đang nhập mẫu 3D",
        detail: "Ứng dụng đang kiểm tra và đưa mẫu giày vào editor.",
      };
    }
    if (lowered.includes("project")) {
      return {
        tone: "loading",
        title: "Đang mở dự án",
        detail: "Ứng dụng đang tải mẫu giày và bản thiết kế gần nhất.",
      };
    }
    return {
      tone: "loading",
      title: "Ứng dụng đang xử lý",
      detail: normalizedMessage || "Vui lòng chờ trong giây lát.",
    };
  }

  if (rawMessage === "PREVIEW_READY") {
    return {
      tone: "success",
      title: "Đã áp hình lên giày",
      detail: "Bản xem trước 3D đã được cập nhật.",
    };
  }
  if (rawMessage === "EDITOR_READY" || lowered === "ready") {
    return {
      tone: "neutral",
      title: "Editor đã sẵn sàng",
      detail: "Bạn có thể thêm sticker, chữ, lưu bản nháp hoặc xuất file.",
    };
  }
  if (rawMessage === "EXPORT_READY" || lowered.includes("download started") || lowered.includes("zip package ready")) {
    return {
      tone: "success",
      title: "File xuất đã sẵn sàng",
      detail: "Ứng dụng đã chuẩn bị file tải xuống cho thiết kế này.",
    };
  }
  if (
    lowered.includes("model loaded") ||
    lowered.includes("signed in") ||
    lowered.includes("demo session") ||
    lowered.includes("layer applied") ||
    lowered.includes("layer kept")
  ) {
    return {
      tone: "success",
      title: "Thao tác đã hoàn tất",
      detail: successMessage(normalizedMessage),
    };
  }
  if (
    loweredRaw.startsWith("model_processing") ||
    lowered.includes("still processing") ||
    lowered.includes("waiting for model") ||
    lowered.includes("outside the shoe surface") ||
    lowered.includes("select a sticker") ||
    lowered.includes("select a layer") ||
    lowered.includes("no shoe mesh") ||
    lowered.includes("not ready")
  ) {
    return {
      tone: "warning",
      title: "Cần thêm một bước trước khi tiếp tục",
      detail: warningMessage(normalizedMessage),
    };
  }
  if (
    loweredRaw.startsWith("forbidden") ||
    lowered.includes("permission") ||
    lowered.includes("unauthorized") ||
    lowered.includes("session expired") ||
    lowered.includes("not found") ||
    lowered.includes("unavailable") ||
    lowered.includes("failed") ||
    lowered.includes("timed out") ||
    lowered.includes("could not") ||
    lowered.includes("couldn't") ||
    lowered.includes("ứng dụng chưa") ||
    lowered.includes("không còn hợp lệ") ||
    lowered.includes("gặp lỗi") ||
    lowered.includes("không thể") ||
    lowered.includes("chưa thể") ||
    lowered.includes("lỗi")
  ) {
    return {
      tone: "error",
      title: "Ứng dụng chưa hoàn tất thao tác",
      detail: errorMessageForUser(rawMessage),
    };
  }

  return {
    tone: "neutral",
    title: "Trạng thái editor",
    detail: normalizedMessage || "Bạn có thể tiếp tục chỉnh sửa thiết kế.",
  };
}

export function messageFromError(error: unknown): string {
  if (error instanceof EditorApiError) {
    return messageFromApiError(error.message, error.status);
  }
  if (error instanceof ApiError) {
    return messageFromApiError(error.message, error.status);
  }
  if (error instanceof Error) {
    return errorMessageForUser(error.message);
  }
  return "Ứng dụng gặp lỗi ngoài dự kiến. Vui lòng thử lại.";
}

function cleanTechnicalMessage(message: string): string {
  const withoutStatus = message.replace(/^\d{3}\s*:\s*/, "").trim();
  return withoutStatus.replace(/^[A-Z][A-Z0-9_]*\s*:\s*/, "").trim();
}

function successMessage(message: string): string {
  const lowered = message.toLowerCase();
  if (lowered.includes("layer applied") || lowered.includes("layer kept")) {
    return "Sticker hoặc chữ đã được đặt lên bề mặt giày.";
  }
  if (lowered.includes("model loaded")) {
    return "Mẫu giày đã được tải vào editor.";
  }
  if (lowered.includes("signed in") || lowered.includes("demo session")) {
    return "Phiên làm việc đã sẵn sàng.";
  }
  return message || "Thao tác đã hoàn tất.";
}

function warningMessage(message: string): string {
  const lowered = message.toLowerCase();
  if (lowered.includes("outside the shoe surface")) {
    return "Sticker hoặc chữ đang nằm ngoài bề mặt giày. Vui lòng đưa layer lại gần mẫu giày rồi thử lại.";
  }
  if (lowered.includes("select a sticker") || lowered.includes("select a layer")) {
    return "Vui lòng chọn một sticker hoặc text layer trước khi áp lên bề mặt giày.";
  }
  if (lowered.includes("no shoe mesh")) {
    return "Ứng dụng chưa tìm thấy bề mặt giày phù hợp trong mẫu 3D này.";
  }
  if (lowered.includes("waiting for model") || lowered.includes("processing") || lowered.includes("not ready")) {
    return "Mẫu 3D vẫn đang được chuẩn bị. Vui lòng thử lại sau ít phút.";
  }
  return message || "Vui lòng kiểm tra lại dữ liệu trước khi tiếp tục.";
}

function errorMessageForUser(message: string): string {
  const lowered = message.toLowerCase();
  if (lowered.includes("permission") || lowered.includes("forbidden")) {
    return "Ứng dụng chưa thể thực hiện thao tác này vì tài khoản hiện tại chưa có quyền phù hợp.";
  }
  if (lowered.includes("unauthorized") || lowered.includes("session expired")) {
    return "Phiên đăng nhập không còn hợp lệ. Vui lòng đăng nhập lại để tiếp tục.";
  }
  if (lowered.includes("job queue") || lowered.includes("processing is temporarily unavailable") || lowered.includes("unavailable")) {
    return "Ứng dụng chưa khởi động được bộ xử lý preview. Bản nháp vẫn được giữ lại, vui lòng thử lại sau ít phút.";
  }
  if (lowered.includes("preview") || lowered.includes("bake") || lowered.includes("failed")) {
    return "Ứng dụng chưa áp được hình lên giày. Bản nháp đã được lưu, vui lòng kiểm tra vị trí sticker/text rồi thử lại.";
  }
  if (lowered.includes("not found")) {
    return "Ứng dụng chưa tìm thấy dữ liệu cần mở. Vui lòng kiểm tra lại dự án hoặc mẫu giày.";
  }
  if (lowered.includes("timed out")) {
    return "Ứng dụng xử lý lâu hơn dự kiến. Bản nháp đã được giữ lại, vui lòng thử lại.";
  }
  return "Ứng dụng gặp lỗi khi xử lý thao tác này. Bản nháp hiện tại vẫn được giữ lại nếu đã lưu.";
}

function messageFromApiError(message: string, statusCode: number): string {
  if (statusCode === 401) {
    return "Phiên đăng nhập không còn hợp lệ. Vui lòng đăng nhập lại để tiếp tục.";
  }
  if (statusCode === 403) {
    return "Ứng dụng chưa thể thực hiện thao tác này vì tài khoản hiện tại chưa có quyền phù hợp.";
  }
  if (statusCode === 404) {
    return "Ứng dụng chưa tìm thấy dữ liệu cần mở. Vui lòng kiểm tra lại dự án hoặc mẫu giày.";
  }
  if (statusCode === 503) {
    return "Ứng dụng chưa khởi động được bộ xử lý preview. Bản nháp vẫn được giữ lại, vui lòng thử lại sau ít phút.";
  }
  return errorMessageForUser(message);
}
