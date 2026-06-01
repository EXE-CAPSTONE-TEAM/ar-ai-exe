import type {
  Design,
  DesignAsset,
  DesignAssetSource,
  DesignConfig,
  ExportPackage,
  ModelAsset,
  ModelImportResponse,
  ReconstructionReadiness,
  ScanMetadata,
  ScanSession,
  User,
} from "../types";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000";
const TOKEN_STORAGE_KEY = "shoe-customizer-token";

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
  ) {
    super(message);
  }
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...authHeader(),
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
    return typeof payload.detail === "string" ? payload.detail : JSON.stringify(payload.detail);
  } catch {
    return response.statusText;
  }
}

function authHeader(): Record<string, string> {
  const token = localStorage.getItem(TOKEN_STORAGE_KEY);
  return token ? { Authorization: `Bearer ${token}` } : {};
}

function storeToken(accessToken: string): void {
  localStorage.setItem(TOKEN_STORAGE_KEY, accessToken);
}

export const api = {
  baseUrl: API_BASE_URL,

  hasToken(): boolean {
    return Boolean(localStorage.getItem(TOKEN_STORAGE_KEY));
  },

  logout(): void {
    localStorage.removeItem(TOKEN_STORAGE_KEY);
  },

  async register(name: string, email: string, password: string): Promise<User> {
    const payload = await request<{ accessToken: string; user: User }>("/api/auth/register", {
      method: "POST",
      body: JSON.stringify({ name, email, password }),
    });
    storeToken(payload.accessToken);
    return payload.user;
  },

  async login(email: string, password: string): Promise<User> {
    const payload = await request<{ accessToken: string; user: User }>("/api/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    });
    storeToken(payload.accessToken);
    return payload.user;
  },

  async demoLogin(): Promise<User> {
    const payload = await request<{ accessToken: string; user: User }>("/api/auth/demo-login", {
      method: "POST",
    });
    storeToken(payload.accessToken);
    return payload.user;
  },

  async me(): Promise<User> {
    return request<User>("/api/auth/me");
  },

  async getReconstructionReadiness(): Promise<ReconstructionReadiness> {
    return request<ReconstructionReadiness>("/api/system/reconstruction-readiness");
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

    const response = await fetch(`${API_BASE_URL}/api/models/import`, {
      method: "POST",
      headers: authHeader(),
      body: form,
    });
    if (!response.ok) {
      throw new ApiError(await errorMessage(response), response.status);
    }
    return response.json() as Promise<ModelImportResponse>;
  },

  async uploadDesignAsset(file: File, sourceType: DesignAssetSource): Promise<DesignAsset> {
    const form = new FormData();
    form.append("file", file);
    form.append("sourceType", sourceType);

    const response = await fetch(`${API_BASE_URL}/api/design-assets`, {
      method: "POST",
      headers: authHeader(),
      body: form,
    });
    if (!response.ok) {
      throw new ApiError(await errorMessage(response), response.status);
    }
    return response.json() as Promise<DesignAsset>;
  },

  async fetchDesignAssetBlobUrl(assetId: string): Promise<string> {
    const response = await fetch(`${API_BASE_URL}/api/design-assets/${assetId}/download`, {
      headers: authHeader(),
    });
    if (!response.ok) {
      throw new ApiError(await errorMessage(response), response.status);
    }
    return URL.createObjectURL(await response.blob());
  },

  async fetchModelBlobUrl(modelAsset: ModelAsset): Promise<string> {
    const response = await fetch(`${API_BASE_URL}${modelAsset.glbUrl}`, {
      headers: authHeader(),
    });
    if (!response.ok) {
      throw new ApiError(await errorMessage(response), response.status);
    }
    return URL.createObjectURL(await response.blob());
  },

  async fetchDesignPreviewBlobUrl(design: Design): Promise<string | null> {
    if (!design.previewGlbUrl) {
      return null;
    }
    const response = await fetch(`${API_BASE_URL}${design.previewGlbUrl}`, {
      headers: authHeader(),
      cache: "no-store",
    });
    if (!response.ok) {
      throw new ApiError(await errorMessage(response), response.status);
    }
    return URL.createObjectURL(await response.blob());
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
    return request<ExportPackage>(`/api/designs/${designId}/export`, {
      method: "POST",
    });
  },

  async downloadExport(exportPackage: ExportPackage): Promise<void> {
    const response = await fetch(`${API_BASE_URL}${exportPackage.downloadUrl}`, {
      headers: authHeader(),
    });
    if (!response.ok) {
      throw new ApiError(await errorMessage(response), response.status);
    }

    const url = URL.createObjectURL(await response.blob());
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = `${exportPackage.id}.zip`;
    anchor.click();
    URL.revokeObjectURL(url);
  },

  async downloadModelFile(urlPath: string, filename: string): Promise<void> {
    const response = await fetch(`${API_BASE_URL}${urlPath}`, {
      headers: authHeader(),
    });
    if (!response.ok) {
      throw new ApiError(await errorMessage(response), response.status);
    }

    const url = URL.createObjectURL(await response.blob());
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = filename;
    anchor.click();
    URL.revokeObjectURL(url);
  },
};

export type ModelImportPayload = {
  name: string;
  format: "glb" | "obj";
  metadata: ScanMetadata;
  model?: File | null;
  mtl?: File | null;
  texture?: File | null;
  package?: File | null;
};

export function designStorageKey(modelAssetId: string): string {
  return `shoe-customizer-design-${modelAssetId}`;
}
