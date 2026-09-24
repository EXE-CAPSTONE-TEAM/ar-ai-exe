import type {
  Design,
  DesignAsset,
  DesignAssetSource,
  DesignConfig,
  CloudProject,
  EditorReadiness,
  ExportPackage,
  Job,
  ModelAsset,
  ModelImportResponse,
  ReconstructionReadiness,
  ScanMetadata,
  ScanSession,
  User,
} from "../types";
import { clearAccessToken, storeAccessToken, storedAccessToken } from "./authStorage";
import { editorClient } from "./editorClient";
import { getActiveEditorSession } from "./editorLaunch";
import { apiUrl, getApiBaseUrl } from "./runtimeConfig";

const CSRF_COOKIE_NAME = "kusshoes_csrf_token";

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
    readonly code?: string,
  ) {
    super(message);
  }
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const response = await fetch(apiUrl(path), {
    ...options,
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      ...authHeader(),
      ...csrfHeader(options.method),
      ...options.headers,
    },
  });

  if (!response.ok) {
    throw new ApiError(await errorMessage(response), response.status);
  }

  return response.json() as Promise<T>;
}

async function errorMessage(response: Response): Promise<string> {
  try {
    const payload = await response.json();
    if (payload?.error?.message) {
      return String(payload.error.message);
    }
    if (typeof payload.message === "string") {
      return payload.message;
    }
    return typeof payload.detail === "string" ? payload.detail : JSON.stringify(payload.detail);
  } catch {
    return response.statusText;
  }
}

function authHeader(): Record<string, string> {
  const token = storedAccessToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}

function csrfHeader(method: string | undefined): Record<string, string> {
  const normalizedMethod = (method ?? "GET").toUpperCase();
  if (!["POST", "PUT", "PATCH", "DELETE"].includes(normalizedMethod)) {
    return {};
  }
  const csrfToken = document.cookie
    .split("; ")
    .find((value) => value.startsWith(`${CSRF_COOKIE_NAME}=`))
    ?.split("=")[1];
  return csrfToken ? { "X-CSRF-Token": decodeURIComponent(csrfToken) } : {};
}

// KusShoes editor content routes answer with a presigned storage URL instead of bytes
// (KusShoes spec §B, ADR-004). The local sidecar still serves bytes on its own routes.
const KUSSHOES_CONTENT_PATH = /^\/api\/v1\/editor\/(?:assets|exports)\/[0-9a-f-]{36}\/content(?:[?#]|$)/i;

type PresignedContent = {
  url: string;
  expiresIn: number;
  filename: string;
  contentType: string;
};

export type StoredFile = { blob: Blob; filename: string | null };

export function isPresignedContentPath(path: string): boolean {
  return KUSSHOES_CONTENT_PATH.test(path);
}

function presignedUrl(value: unknown): string {
  if (typeof value !== "string") {
    throw new ApiError("Storage URL is missing.", 502);
  }
  const url = new URL(value);
  if ((url.protocol !== "https:" && url.protocol !== "http:") || url.username || url.password) {
    throw new ApiError("Storage URL is invalid.", 502);
  }
  return url.toString();
}

/** Fetch a stored file from an API path, following a presigned URL when the API returns one. */
export async function fetchStoredFile(path: string, cache?: RequestCache): Promise<StoredFile> {
  const response = await fetch(apiUrl(path), {
    credentials: "include",
    headers: authHeader(),
    cache,
  });
  if (!response.ok) {
    throw new ApiError(await errorMessage(response), response.status);
  }
  if (!isPresignedContentPath(path)) {
    return { blob: await response.blob(), filename: null };
  }
  const content = (await response.json()) as PresignedContent;
  // Storage authenticates by the URL signature: never send cookies or the API bearer token.
  const file = await fetch(presignedUrl(content.url), { credentials: "omit", cache });
  if (!file.ok) {
    throw new ApiError(`Storage download failed (${file.status}).`, file.status);
  }
  return { blob: await file.blob(), filename: content.filename || null };
}

function downloadBlob(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  anchor.style.display = "none";
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}

async function uploadEditorDesignAsset(
  file: File,
  sourceType: DesignAssetSource,
): Promise<DesignAsset> {
  const allowedContentTypes = new Set(["image/png", "image/jpeg", "image/webp"]);
  if (!allowedContentTypes.has(file.type)) {
    throw new ApiError("KusStudio supports PNG, JPEG, or WebP design assets.", 400);
  }
  if (file.size < 1 || file.size > 5 * 1024 * 1024) {
    throw new ApiError("Design assets must be between 1 byte and 5 MiB.", 400);
  }

  const upload = await request<{
    upload_url: string;
    asset_id: string;
    expires_in: number;
  }>("/api/v1/editor/assets/upload-url", {
    method: "POST",
    body: JSON.stringify({
      asset_type: "sticker",
      filename: file.name,
      content_type: file.type,
    }),
  });
  const signedUrl = new URL(upload.upload_url);
  if (
    (signedUrl.protocol !== "https:" && signedUrl.protocol !== "http:") ||
    signedUrl.username ||
    signedUrl.password
  ) {
    throw new ApiError("KusShoes returned an invalid asset upload URL.", 502);
  }
  const uploaded = await fetch(signedUrl, {
    method: "PUT",
    credentials: "omit",
    headers: { "Content-Type": file.type },
    body: file,
  });
  if (!uploaded.ok) {
    throw new ApiError("Unable to upload the design asset.", uploaded.status);
  }

  const asset = await request<{
    id: string;
    original_filename: string | null;
    file_size_bytes: number | null;
    mime_type: string | null;
    created_at: string;
  }>("/api/v1/editor/assets/confirm", {
    method: "POST",
    body: JSON.stringify({ asset_id: upload.asset_id, file_size_bytes: file.size }),
  });
  return {
    id: asset.id,
    sourceType,
    fileName: asset.original_filename ?? file.name,
    contentType: asset.mime_type ?? file.type,
    sizeBytes: asset.file_size_bytes ?? file.size,
    checksum: "",
    downloadUrl: `/api/v1/editor/assets/${asset.id}/content`,
    createdAt: asset.created_at,
  };
}

const SOURCE_MODEL_MAX_BYTES = 500 * 1024 * 1024;

/**
 * Import thủ công model 3D gốc cho project KusShoes (tạm thời đứng thay luồng
 * scan mobile). KusShoes chỉ cho phép khi project chưa có model canonical.
 */
async function importEditorSourceModel(file: File): Promise<void> {
  if (!/\.glb$/i.test(file.name)) {
    throw new ApiError("KusShoes chỉ nhận file .glb làm model gốc của project.", 400);
  }
  if (file.size < 1 || file.size > SOURCE_MODEL_MAX_BYTES) {
    throw new ApiError("File GLB phải nằm trong khoảng 1 byte đến 500 MiB.", 400);
  }

  const upload = await request<{
    upload_url: string;
    asset_id: string;
  }>("/api/v1/editor/assets/upload-url", {
    method: "POST",
    body: JSON.stringify({
      asset_type: "source_model",
      filename: file.name,
      content_type: "model/gltf-binary",
    }),
  });
  const signedUrl = new URL(upload.upload_url);
  if (
    (signedUrl.protocol !== "https:" && signedUrl.protocol !== "http:") ||
    signedUrl.username ||
    signedUrl.password
  ) {
    throw new ApiError("KusShoes returned an invalid asset upload URL.", 502);
  }
  const uploaded = await fetch(signedUrl, {
    method: "PUT",
    credentials: "omit",
    headers: { "Content-Type": "model/gltf-binary" },
    body: file,
  });
  if (!uploaded.ok) {
    throw new ApiError("Không upload được model GLB lên KusShoes.", uploaded.status);
  }

  await request<unknown>("/api/v1/editor/assets/confirm", {
    method: "POST",
    body: JSON.stringify({ asset_id: upload.asset_id, file_size_bytes: file.size }),
  });
}

export const api = {
  get baseUrl(): string {
    return getApiBaseUrl();
  },

  hasToken(): boolean {
    return Boolean(storedAccessToken());
  },

  logout(): void {
    const wasEditorSession = Boolean(getActiveEditorSession());
    clearAccessToken();
    if (wasEditorSession) return;
    void fetch(apiUrl("/api/auth/logout"), {
      method: "POST",
      credentials: "include",
      headers: csrfHeader("POST"),
    });
  },

  async register(name: string, email: string, password: string): Promise<User> {
    const payload = await request<{ accessToken: string; user: User }>("/api/auth/register", {
      method: "POST",
      body: JSON.stringify({ name, email, password }),
    });
    storeAccessToken(payload.accessToken);
    return payload.user;
  },

  async login(email: string, password: string): Promise<User> {
    const payload = await request<{ accessToken: string; user: User }>("/api/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    });
    storeAccessToken(payload.accessToken);
    return payload.user;
  },

  async demoLogin(): Promise<User> {
    const payload = await request<{ accessToken: string; user: User }>("/api/auth/demo-login", {
      method: "POST",
    });
    storeAccessToken(payload.accessToken);
    return payload.user;
  },

  async me(): Promise<User> {
    return request<User>("/api/auth/me");
  },

  async listProjects(): Promise<CloudProject[]> {
    const payload = await request<{ items: CloudProject[] }>("/api/projects");
    return payload.items;
  },

  async getReconstructionReadiness(): Promise<ReconstructionReadiness> {
    return request<ReconstructionReadiness>("/api/system/reconstruction-readiness");
  },

  async getEditorReadiness(): Promise<EditorReadiness> {
    return request<EditorReadiness>("/api/system/editor-readiness");
  },

  async getScanSession(scanSessionId: string): Promise<ScanSession> {
    return request<ScanSession>(`/api/scan-sessions/${scanSessionId}`);
  },

  async getModelAsset(modelAssetId: string): Promise<ModelAsset> {
    return request<ModelAsset>(`/api/models/${modelAssetId}`);
  },

  async importModel(payload: ModelImportPayload): Promise<ModelImportResponse> {
    const form = new FormData();
    form.append("name", payload.name);
    form.append("format", payload.format);
    form.append("metadata", JSON.stringify(payload.metadata));
    if (payload.projectId) {
      form.append("projectId", payload.projectId);
    }
    if (payload.model) {
      form.append("model", payload.model);
    }
    if (payload.mtl) {
      form.append("mtl", payload.mtl);
    }
    if (payload.texture) {
      form.append("texture", payload.texture);
    }
    if (payload.package) {
      form.append("package", payload.package);
    }

    const response = await fetch(apiUrl("/api/models/import"), {
      method: "POST",
      credentials: "include",
      headers: { ...authHeader(), ...csrfHeader("POST") },
      body: form,
    });
    if (!response.ok) {
      throw new ApiError(await errorMessage(response), response.status);
    }
    return response.json() as Promise<ModelImportResponse>;
  },

  /** Import model gốc cho project cloud (KusShoes) — xem docs/integration-runbook.md. */
  async importProjectSourceModel(file: File): Promise<void> {
    if (!getActiveEditorSession()) {
      throw new ApiError("Chức năng này chỉ dùng khi KusStudio mở project từ KusShoes.", 400);
    }
    return importEditorSourceModel(file);
  },

  async uploadDesignAsset(file: File, sourceType: DesignAssetSource): Promise<DesignAsset> {
    if (getActiveEditorSession()) {
      return uploadEditorDesignAsset(file, sourceType);
    }
    const form = new FormData();
    form.append("file", file);
    form.append("sourceType", sourceType);

    const response = await fetch(apiUrl("/api/design-assets"), {
      method: "POST",
      credentials: "include",
      headers: { ...authHeader(), ...csrfHeader("POST") },
      body: form,
    });
    if (!response.ok) {
      throw new ApiError(await errorMessage(response), response.status);
    }
    return response.json() as Promise<DesignAsset>;
  },

  async fetchDesignAssetBlobUrl(assetId: string): Promise<string> {
    const path = getActiveEditorSession() ? `/api/v1/editor/assets/${assetId}/content` : `/api/design-assets/${assetId}/download`;
    const { blob } = await fetchStoredFile(path);
    return URL.createObjectURL(blob);
  },

  async fetchModelBlobUrl(modelAsset: ModelAsset): Promise<string> {
    const { blob } = await fetchStoredFile(modelAsset.canonicalGlbUrl ?? modelAsset.glbUrl);
    return URL.createObjectURL(blob);
  },

  async fetchDesignPreviewBlobUrl(design: Design): Promise<string | null> {
    if (!design.previewGlbUrl) {
      return null;
    }
    const separator = design.previewGlbUrl.includes("?") ? "&" : "?";
    const { blob } = await fetchStoredFile(`${design.previewGlbUrl}${separator}t=${Date.now()}`, "no-store");
    return URL.createObjectURL(blob);
  },

  async createDesign(modelAssetId: string, name: string, config: DesignConfig): Promise<Design> {
    return request<Design>("/api/designs", {
      method: "POST",
      body: JSON.stringify({ modelAssetId, name, config }),
    });
  },

  async getDesign(designId: string): Promise<Design> {
    return request<Design>(`/api/designs/${designId}`);
  },

  async updateDesign(designId: string, name: string, config: DesignConfig): Promise<Design> {
    return request<Design>(`/api/designs/${designId}`, {
      method: "PUT",
      body: JSON.stringify({ name, config }),
    });
  },

  async exportDesign(designId: string): Promise<ExportPackage> {
    if (getActiveEditorSession()) {
      return editorClient.exportDesign(designId);
    }
    return request<ExportPackage>(`/api/designs/${designId}/export`, {
      method: "POST",
    });
  },

  async bakeDesign(designId: string): Promise<Job> {
    if (getActiveEditorSession()) {
      return editorClient.bakeDesign(designId);
    }
    return request<Job>(`/api/designs/${designId}/bake`, {
      method: "POST",
    });
  },

  async getJob(jobId: string): Promise<Job> {
    if (getActiveEditorSession()) {
      return editorClient.getJob(jobId);
    }
    return request<Job>(`/api/jobs/${jobId}`);
  },

  async downloadExport(exportPackage: ExportPackage): Promise<void> {
    const exportPath = exportPackage.zipUrl ?? exportPackage.downloadUrl;
    if (getActiveEditorSession() || isPresignedContentPath(exportPath)) {
      // KusShoes exports (up to 2 GiB) are saved by the desktop sidecar, never buffered here.
      await editorClient.downloadExport(exportPackage);
      return;
    }
    const { blob, filename } = await fetchStoredFile(exportPath);
    downloadBlob(blob, filename ?? `${exportPackage.id}.zip`);
  },

  async downloadModelFile(urlPath: string, filename: string): Promise<void> {
    const file = await fetchStoredFile(urlPath);
    downloadBlob(file.blob, file.filename ?? filename);
  },
};

export type ModelImportPayload = {
  name: string;
  format: "glb" | "obj";
  metadata: ScanMetadata;
  projectId?: string | null;
  model?: File | null;
  mtl?: File | null;
  texture?: File | null;
  package?: File | null;
};

export function designStorageKey(modelAssetId: string): string {
  return `shoe-customizer-design-${modelAssetId}`;
}
