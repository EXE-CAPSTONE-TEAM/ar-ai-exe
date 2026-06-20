import type { Design, DesignConfig, EditorContext, ExportPackage, Job, User } from "../types";
import { apiUrl } from "./runtimeConfig";

const TOKEN_STORAGE_KEY = "shoe-customizer-token";
const CSRF_COOKIE_NAME = "kusshoes_csrf_token";

export class EditorApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
    readonly code: string,
  ) {
    super(message);
  }
}

export const editorClient = {
  async getMe(): Promise<User> {
    return request<User>("/api/auth/me");
  },

  async getEditorContext(projectId: string): Promise<EditorContext> {
    return request<EditorContext>(`/api/projects/${projectId}/editor-context`);
  },

  async saveDesign(projectId: string, designConfig: DesignConfig, name?: string): Promise<Design> {
    return request<Design>(`/api/projects/${projectId}/designs`, {
      method: "POST",
      body: JSON.stringify({ designConfig, name }),
    });
  },

  async bakeDesign(designId: string): Promise<Job> {
    return request<Job>(`/api/designs/${designId}/bake`, {
      method: "POST",
    });
  },

  async getJob(jobId: string): Promise<Job> {
    return request<Job>(`/api/jobs/${jobId}`);
  },

  async getDesign(designId: string): Promise<Design> {
    return request<Design>(`/api/designs/${designId}`);
  },

  async exportDesign(
    designId: string,
    options = {
      formats: ["glb", "obj"],
      includeTextures: true,
      includeProductionNotes: true,
    },
  ): Promise<ExportPackage> {
    return request<ExportPackage>(`/api/designs/${designId}/export`, {
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
    throw new EditorApiError(error.message, response.status, error.code);
  }
  return response.json() as Promise<T>;
}

async function readError(response: Response): Promise<{ code: string; message: string }> {
  try {
    const payload = await response.json();
    if (payload?.error) {
      return {
        code: String(payload.error.code ?? "API_ERROR"),
        message: String(payload.error.message ?? response.statusText),
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

function authHeader(): Record<string, string> {
  const token = localStorage.getItem(TOKEN_STORAGE_KEY);
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
