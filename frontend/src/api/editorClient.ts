import type { Design, DesignConfig, EditorContext, ExportPackage, Job, User } from "../types";
import { storedAccessToken } from "./authStorage";
import { getDesktopRuntime } from "./desktopRuntime";
import { getActiveEditorSession } from "./editorLaunch";
import { apiUrl } from "./runtimeConfig";

const CSRF_COOKIE_NAME = "kusshoes_csrf_token";

export type DesignConflictPayload = {
  currentRevision: number;
  currentDesignConfig: DesignConfig;
  currentUpdatedAt: string;
};

export type EditorJobClaimResponse = {
  job?: Job;
  claimId: string;
  claimToken: string;
  leaseExpiresAt?: string;
  payload: Record<string, unknown>;
};

export class EditorApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
    readonly code: string,
    readonly conflict?: DesignConflictPayload,
  ) {
    super(message);
  }
}

export function isTerminalJobStatus(status: string): boolean {
  return status === "completed" || status === "failed" || status === "cancelled";
}

function editorRoute(localPath: string, centralPath: string): string {
  return getActiveEditorSession() ? centralPath : localPath;
}


export const editorClient = {
  async getMe(): Promise<User> {
    return request<User>(editorRoute("/api/auth/me", "/api/v1/editor/me"));
  },

  async getEditorContext(projectId: string): Promise<EditorContext> {
    return request<EditorContext>(editorRoute(`/api/projects/${projectId}/editor-context`, `/api/v1/editor/projects/${projectId}/context`));
  },

  async saveDesign(
    projectId: string,
    designConfig: DesignConfig,
    name: string | undefined,
    baseRevision: number,
  ): Promise<Design> {
    return request<Design>(editorRoute(`/api/projects/${projectId}/designs`, `/api/v1/editor/projects/${projectId}/designs`), {
      method: "POST",
      body: JSON.stringify({ designConfig, name, baseRevision }),
    });
  },

  async bakeDesign(designId: string): Promise<Job> {
    const session = getActiveEditorSession();
    if (!session) {
      return request<Job>(`/api/designs/${designId}/bake`, {
        method: "POST",
      });
    }

    const runtime = await getDesktopRuntime();
    if (!runtime.sidecarToken) {
      throw new EditorApiError(
        "KusStudio Desktop (Windows) is required for this action.",
        400,
        "DESKTOP_REQUIRED",
      );
    }

    // 1. Create bake job on KusShoes BE
    const job = await request<Job>(`/api/v1/editor/designs/${designId}/bake`, {
      method: "POST",
    });

    // 2. Claim the job
    const claim = await request<EditorJobClaimResponse>(`/api/v1/editor/jobs/${job.id}/claim`, {
      method: "POST",
      body: JSON.stringify({ deviceLabel: "desktop" }),
    });

    const claimToken = claim.claimToken ?? (claim as unknown as { claim_token?: string }).claim_token;
    if (!claimToken) {
      throw new EditorApiError("Claim response did not contain a claim token.", 502, "CLAIM_FAILED");
    }

    const sidecarBaseUrl = runtime.apiBaseUrl.replace(/\/+$/, "");

    // 3. Post to sidecar /bake with header X-Service-Token: runtime.sidecarToken and claim payload
    let sidecarResponse: Response;
    try {
      sidecarResponse = await fetch(`${sidecarBaseUrl}/bake`, {
        method: "POST",
        credentials: "omit",
        headers: {
          "Content-Type": "application/json",
          "X-Service-Token": runtime.sidecarToken,
        },
        body: JSON.stringify(claim.payload),
      });
    } catch (networkError) {
      const code = "SIDECAR_UNAVAILABLE";
      const message = String(networkError instanceof Error ? networkError.message : "Sidecar connection failed").slice(0, 500);
      return failJob(job.id, claimToken, { code, message });
    }

    if (!sidecarResponse.ok) {
      const errPayload = await sidecarResponse.json().catch(() => null);
      const code = String(
        errPayload?.code ??
        errPayload?.error?.code ??
        (sidecarResponse.status === 503 ? "WORKER_BUSY" : "SIDECAR_BAKE_FAILED"),
      ).slice(0, 64);
      const message = String(
        errPayload?.message ??
        errPayload?.detail ??
        errPayload?.error?.message ??
        `Sidecar bake failed with status ${sidecarResponse.status}`,
      ).slice(0, 500);
      return failJob(job.id, claimToken, { code, message });
    }

    let sidecarData: Record<string, unknown>;
    try {
      sidecarData = (await sidecarResponse.json()) as Record<string, unknown>;
    } catch {
      return failJob(job.id, claimToken, {
        code: "SIDECAR_INVALID_RESPONSE",
        message: "Sidecar returned an invalid JSON response.",
      });
    }

    const rawExports = (sidecarData.exports ?? sidecarData.outputs) as Array<Record<string, unknown>> | undefined;
    if (!Array.isArray(rawExports) || rawExports.length === 0) {
      return failJob(job.id, claimToken, {
        code: "SIDECAR_OUTPUT_MISSING",
        message: "Sidecar completed without returning export outputs.",
      });
    }

    const outputs = rawExports.map((item) => ({
      format: String(item.format),
      filePath: String(item.filePath ?? item.file_path),
      fileSizeBytes: Number(item.fileSizeBytes ?? item.file_size_bytes),
    }));

    // 4. Complete the job with X-Claim-Token and watermarkApplied: false (no Authorization header)
    return completeJob(job.id, claimToken, outputs);
  },

  async getJob(jobId: string): Promise<Job> {
    return request<Job>(editorRoute(`/api/jobs/${jobId}`, `/api/v1/editor/jobs/${jobId}`));
  },

  async getDesign(designId: string): Promise<Design> {
    return request<Design>(editorRoute(`/api/designs/${designId}`, `/api/v1/editor/designs/${designId}`));
  },

  async exportDesign(
    designId: string,
    options = {
      formats: ["glb", "obj"],
      includeTextures: true,
      includeProductionNotes: true,
    },
  ): Promise<ExportPackage> {
    const session = getActiveEditorSession();
    if (!session) {
      return request<ExportPackage>(`/api/designs/${designId}/export`, {
        method: "POST",
        body: JSON.stringify(options),
      });
    }

    const runtime = await getDesktopRuntime();
    if (!runtime.sidecarToken) {
      throw new EditorApiError(
        "KusStudio Desktop (Windows) is required for this action.",
        400,
        "DESKTOP_REQUIRED",
      );
    }

    return request<ExportPackage>(`/api/v1/editor/designs/${designId}/export`, {
      method: "POST",
      body: JSON.stringify(options),
    });
  },

  async downloadExport(exportPackage: ExportPackage): Promise<{ path?: string }> {
    const session = getActiveEditorSession();
    const exportPath = exportPackage.zipUrl ?? exportPackage.downloadUrl;
    const isKusShoes = Boolean(session) || exportPath.includes("/editor/exports/");

    if (isKusShoes) {
      const runtime = await getDesktopRuntime();
      if (!runtime.sidecarToken) {
        throw new EditorApiError(
          "KusStudio Desktop (Windows) is required for this action.",
          400,
          "DESKTOP_REQUIRED",
        );
      }

      // Desktop: call KusShoes /content
      const response = await fetch(apiUrl(exportPath), {
        credentials: "include",
        headers: {
          ...authHeader(),
          ...csrfHeader("GET"),
        },
      });
      if (!response.ok) {
        const error = await readError(response);
        throw new EditorApiError(error.message, response.status, error.code);
      }
      const content = (await response.json()) as { url: string; filename: string };

      // POST {runtime.apiBaseUrl}/downloads {url, filename} with X-Service-Token
      const sidecarBaseUrl = runtime.apiBaseUrl.replace(/\/+$/, "");
      const downloadResponse = await fetch(`${sidecarBaseUrl}/downloads`, {
        method: "POST",
        credentials: "omit",
        headers: {
          "Content-Type": "application/json",
          "X-Service-Token": runtime.sidecarToken,
        },
        body: JSON.stringify({
          url: content.url,
          filename: content.filename || `${exportPackage.id}.zip`,
        }),
      });

      if (!downloadResponse.ok) {
        throw new EditorApiError(
          `Desktop download failed (${downloadResponse.status}).`,
          downloadResponse.status,
          "DOWNLOAD_FAILED",
        );
      }
      return (await downloadResponse.json().catch(() => ({}))) as { path?: string };
    }

    return {};
  },
};

async function completeJob(
  jobId: string,
  claimToken: string,
  outputs: Array<{ format: string; filePath: string; fileSizeBytes: number }>,
): Promise<Job> {
  const response = await fetch(apiUrl(`/api/v1/editor/jobs/${jobId}/complete`), {
    method: "POST",
    credentials: "omit",
    headers: {
      "Content-Type": "application/json",
      "X-Claim-Token": claimToken,
      ...csrfHeader("POST"),
    },
    body: JSON.stringify({
      outputs,
      watermarkApplied: false,
    }),
  });

  if (!response.ok) {
    const error = await readError(response);
    throw new EditorApiError(error.message, response.status, error.code, error.conflict);
  }
  return response.json() as Promise<Job>;
}

async function failJob(
  jobId: string,
  claimToken: string,
  errorPayload: { code: string; message: string },
): Promise<Job> {
  const response = await fetch(apiUrl(`/api/v1/editor/jobs/${jobId}/fail`), {
    method: "POST",
    credentials: "omit",
    headers: {
      "Content-Type": "application/json",
      "X-Claim-Token": claimToken,
      ...csrfHeader("POST"),
    },
    body: JSON.stringify({
      code: errorPayload.code,
      message: errorPayload.message,
    }),
  });

  if (!response.ok) {
    const error = await readError(response);
    throw new EditorApiError(error.message, response.status, error.code, error.conflict);
  }
  return response.json() as Promise<Job>;
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
    const error = await readError(response);
    throw new EditorApiError(error.message, response.status, error.code, error.conflict);
  }
  return response.json() as Promise<T>;
}

async function readError(response: Response): Promise<{
  code: string;
  message: string;
  conflict?: DesignConflictPayload;
}> {
  try {
    const payload = await response.json();
    if (payload?.error) {
      return {
        code: String(payload.error.code ?? "API_ERROR"),
        message: String(payload.error.message ?? response.statusText),
      };
    }
    if (typeof payload.message === "string") {
      return {
        code: String(payload.code ?? "API_ERROR"),
        message: payload.message,
        conflict: readConflictPayload(payload),
      };
    }
    if (typeof payload.detail === "string") {
      return { code: "API_ERROR", message: payload.detail };
    }
  } catch {
    // Fall through to statusText.
  }
  return { code: "API_ERROR", message: response.statusText };
}

function readConflictPayload(payload: Record<string, unknown>): DesignConflictPayload | undefined {
  if (payload.code !== "DESIGN_REVISION_CONFLICT") {
    return undefined;
  }
  const currentRevision = payload.current_revision;
  const currentDesignConfig = payload.current_design_config;
  const currentUpdatedAt = payload.current_updated_at;
  if (
    typeof currentRevision !== "number" ||
    typeof currentUpdatedAt !== "string" ||
    typeof currentDesignConfig !== "object" ||
    currentDesignConfig === null
  ) {
    return undefined;
  }
  return {
    currentRevision,
    currentDesignConfig: currentDesignConfig as DesignConfig,
    currentUpdatedAt,
  };
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
  if (typeof document === "undefined") {
    return {};
  }
  const csrfToken = document.cookie
    .split("; ")
    .find((value) => value.startsWith(`${CSRF_COOKIE_NAME}=`))
    ?.split("=")[1];
  return csrfToken ? { "X-CSRF-Token": decodeURIComponent(csrfToken) } : {};
}
