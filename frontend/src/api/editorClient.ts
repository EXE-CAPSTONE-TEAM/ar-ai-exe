import type { Design, DesignConfig, EditorContext, ExportPackage, Job, User } from "../types";
import { storedAccessToken } from "./authStorage";
import { getActiveEditorSession } from "./editorLaunch";
import { apiUrl } from "./runtimeConfig";

const CSRF_COOKIE_NAME = "kusshoes_csrf_token";

export type DesignConflictPayload = {
  currentRevision: number;
  currentDesignConfig: DesignConfig;
  currentUpdatedAt: string;
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
    return request<Job>(editorRoute(`/api/designs/${designId}/bake`, `/api/v1/editor/designs/${designId}/bake`), {
      method: "POST",
    });
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
    return request<ExportPackage>(editorRoute(`/api/designs/${designId}/export`, `/api/v1/editor/designs/${designId}/export`), {
      method: "POST",
      body: JSON.stringify(options),
    });
  },
};

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
  const csrfToken = document.cookie
    .split("; ")
    .find((value) => value.startsWith(`${CSRF_COOKIE_NAME}=`))
    ?.split("=")[1];
  return csrfToken ? { "X-CSRF-Token": decodeURIComponent(csrfToken) } : {};
}
