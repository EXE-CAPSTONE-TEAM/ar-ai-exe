import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { ExportPackage } from "../types";
import { storeEphemeralAccessToken } from "./authStorage";
import { api } from "./client";
import { EditorApiError, editorClient, isTerminalJobStatus } from "./editorClient";
import { clearEditorLaunchSession, setActiveEditorSessionForTesting } from "./editorLaunch";

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

describe("editorClient (Ticket-06)", () => {
  beforeEach(() => {
    const store = new Map<string, string>();
    vi.stubGlobal("localStorage", {
      getItem: (key: string) => store.get(key) ?? null,
      setItem: (key: string, value: string) => store.set(key, value),
      removeItem: (key: string) => store.delete(key),
    });
    vi.stubGlobal("window", {});
    storeEphemeralAccessToken("editor-session-token");
    setActiveEditorSessionForTesting({
      expiresIn: 3600,
      userId: "user-123",
      projectId: "project-456",
      scopes: ["editor:read", "editor:write"],
    });
  });

  afterEach(() => {
    clearEditorLaunchSession();
    vi.unstubAllGlobals();
  });

  describe("Web mode (no sidecarToken)", () => {
    it("bakeDesign returns DESKTOP_REQUIRED without network calls", async () => {
      const fetchMock = vi.fn();
      vi.stubGlobal("fetch", fetchMock);

      await expect(editorClient.bakeDesign("design-001")).rejects.toSatisfy((err: unknown) => {
        return err instanceof EditorApiError && err.code === "DESKTOP_REQUIRED";
      });

      expect(fetchMock).not.toHaveBeenCalled();
    });

    it("exportDesign returns DESKTOP_REQUIRED without network calls", async () => {
      const fetchMock = vi.fn();
      vi.stubGlobal("fetch", fetchMock);

      await expect(editorClient.exportDesign("design-001")).rejects.toSatisfy((err: unknown) => {
        return err instanceof EditorApiError && err.code === "DESKTOP_REQUIRED";
      });

      expect(fetchMock).not.toHaveBeenCalled();
    });

    it("downloadExport returns DESKTOP_REQUIRED without network calls", async () => {
      const fetchMock = vi.fn();
      vi.stubGlobal("fetch", fetchMock);

      const pkg: ExportPackage = {
        id: "exp-001",
        designId: "design-001",
        status: "ready",
        downloadUrl: "/api/v1/editor/exports/exp-001/content",
        files: ["glb"],
        createdAt: "2026-09-24T00:00:00Z",
      };

      await expect(editorClient.downloadExport(pkg)).rejects.toSatisfy((err: unknown) => {
        return err instanceof EditorApiError && err.code === "DESKTOP_REQUIRED";
      });

      expect(fetchMock).not.toHaveBeenCalled();
    });

    it("api.downloadExport returns DESKTOP_REQUIRED without network calls", async () => {
      const fetchMock = vi.fn();
      vi.stubGlobal("fetch", fetchMock);

      const pkg: ExportPackage = {
        id: "exp-001",
        designId: "design-001",
        status: "ready",
        downloadUrl: "/api/v1/editor/exports/exp-001/content",
        files: ["glb"],
        createdAt: "2026-09-24T00:00:00Z",
      };

      await expect(api.downloadExport(pkg)).rejects.toSatisfy((err: any) => {
        return err.code === "DESKTOP_REQUIRED";
      });

      expect(fetchMock).not.toHaveBeenCalled();
    });
  });

  describe("Desktop mode bakeDesign lifecycle", () => {
    function setupDesktopTauri() {
      vi.stubGlobal("window", {
        __TAURI__: {
          core: {
            invoke: vi.fn().mockImplementation(async (command: string) => {
              if (command === "get_desktop_runtime") {
                return {
                  apiBaseUrl: "http://127.0.0.1:8000",
                  backendStatus: "ready",
                  blenderStatus: "installed",
                  demoProjectStatus: "ready",
                  diagnosticSummary: "",
                  backendPort: 8000,
                  storagePath: "",
                  blenderPath: "",
                  logsPath: "",
                  appVersion: "1.0.0",
                  sidecarToken: "sidecar-token-xyz",
                };
              }
              return null;
            }),
          },
        },
      });
    }

    it("completes full create -> claim -> sidecar -> complete sequence with X-Claim-Token and no Authorization header on complete", async () => {
      setupDesktopTauri();

      const bakeJobId = "job-bake-123";
      const claimToken = "claim-token-secret-999";
      const sidecarPayload = {
        job_id: bakeJobId,
        project_id: "project-456",
        formats: ["glb"],
        source_model: {
          asset_id: "asset-1",
          download_url: "https://r2.test/model.glb",
          file_size_bytes: 1024,
          mime_type: "model/gltf-binary",
        },
        outputs: [
          {
            format: "glb",
            file_path: `exports/project-456/${bakeJobId}/final_shoe.glb`,
            upload_url: "https://r2.test/upload",
            content_type: "model/gltf-binary",
          },
        ],
        design_config: {},
      };

      const fetchMock = vi.fn().mockImplementation(async (url: string, init?: RequestInit) => {
        const urlStr = String(url);
        // Step 1: create bake job on KusShoes BE
        if (urlStr.endsWith("/api/v1/editor/designs/design-001/bake")) {
          expect(init?.headers).toMatchObject({
            Authorization: "Bearer editor-session-token",
          });
          return jsonResponse({
            id: bakeJobId,
            type: "bake",
            status: "awaiting_client",
            progress: 0,
            errorMessage: null,
            designId: "design-001",
            projectId: "project-456",
            createdAt: "2026-09-24T00:00:00Z",
            updatedAt: "2026-09-24T00:00:00Z",
          });
        }
        // Step 2: claim job on KusShoes BE
        if (urlStr.endsWith(`/api/v1/editor/jobs/${bakeJobId}/claim`)) {
          expect(init?.headers).toMatchObject({
            Authorization: "Bearer editor-session-token",
          });
          return jsonResponse({
            claimId: "claim-uuid-1",
            claimToken,
            leaseExpiresAt: "2026-09-24T01:00:00Z",
            payload: sidecarPayload,
          });
        }
        // Step 3: sidecar POST /bake
        if (urlStr === "http://127.0.0.1:8000/bake") {
          expect((init?.headers as Record<string, string>)["X-Service-Token"]).toBe("sidecar-token-xyz");
          expect(JSON.parse(String(init?.body))).toEqual(sidecarPayload);
          return jsonResponse({
            exports: [
              {
                format: "glb",
                file_path: `exports/project-456/${bakeJobId}/final_shoe.glb`,
                file_size_bytes: 4096,
              },
            ],
          });
        }
        // Step 4: complete on KusShoes BE
        if (urlStr.endsWith(`/api/v1/editor/jobs/${bakeJobId}/complete`)) {
          const headers = (init?.headers ?? {}) as Record<string, string>;
          // complete must send X-Claim-Token and must NOT send Authorization
          expect(headers["X-Claim-Token"]).toBe(claimToken);
          expect(headers.Authorization).toBeUndefined();

          const body = JSON.parse(String(init?.body));
          expect(body).toEqual({
            outputs: [
              {
                format: "glb",
                filePath: `exports/project-456/${bakeJobId}/final_shoe.glb`,
                fileSizeBytes: 4096,
              },
            ],
            watermarkApplied: false,
          });

          return jsonResponse({
            id: bakeJobId,
            type: "bake",
            status: "completed",
            progress: 100,
            errorMessage: null,
            designId: "design-001",
            projectId: "project-456",
            createdAt: "2026-09-24T00:00:00Z",
            updatedAt: "2026-09-24T00:01:00Z",
          });
        }
        throw new Error(`Unexpected fetch call: ${urlStr}`);
      });
      vi.stubGlobal("fetch", fetchMock);

      const job = await editorClient.bakeDesign("design-001");
      expect(job.status).toBe("completed");
      expect(job.id).toBe(bakeJobId);
      expect(fetchMock).toHaveBeenCalledTimes(4);
    });

    it("calls /fail with code and message on sidecar HTTP error, without Authorization header", async () => {
      setupDesktopTauri();

      const bakeJobId = "job-bake-fail-503";
      const claimToken = "claim-token-secret-fail";

      const fetchMock = vi.fn().mockImplementation(async (url: string, init?: RequestInit) => {
        const urlStr = String(url);
        if (urlStr.endsWith("/api/v1/editor/designs/design-001/bake")) {
          return jsonResponse({
            id: bakeJobId,
            status: "awaiting_client",
          });
        }
        if (urlStr.endsWith(`/api/v1/editor/jobs/${bakeJobId}/claim`)) {
          return jsonResponse({
            claimId: "claim-uuid-2",
            claimToken,
            payload: { dummy: 1 },
          });
        }
        if (urlStr === "http://127.0.0.1:8000/bake") {
          return jsonResponse({ detail: "Bake worker is at capacity." }, 503);
        }
        if (urlStr.endsWith(`/api/v1/editor/jobs/${bakeJobId}/fail`)) {
          const headers = (init?.headers ?? {}) as Record<string, string>;
          expect(headers["X-Claim-Token"]).toBe(claimToken);
          expect(headers.Authorization).toBeUndefined();

          const body = JSON.parse(String(init?.body));
          expect(body.code).toBe("WORKER_BUSY");
          expect(body.message).toContain("Bake worker is at capacity.");

          return jsonResponse({
            id: bakeJobId,
            type: "bake",
            status: "failed",
            errorMessage: body.message,
            progress: 50,
          });
        }
        throw new Error(`Unexpected fetch call: ${urlStr}`);
      });
      vi.stubGlobal("fetch", fetchMock);

      const failedJob = await editorClient.bakeDesign("design-001");
      expect(failedJob.status).toBe("failed");
      expect(failedJob.id).toBe(bakeJobId);
      expect(fetchMock).toHaveBeenCalledTimes(4);
    });

    it("calls /fail on sidecar network exception without Authorization header", async () => {
      setupDesktopTauri();

      const bakeJobId = "job-bake-fail-net";
      const claimToken = "claim-token-secret-net";

      const fetchMock = vi.fn().mockImplementation(async (url: string, init?: RequestInit) => {
        const urlStr = String(url);
        if (urlStr.endsWith("/api/v1/editor/designs/design-001/bake")) {
          return jsonResponse({
            id: bakeJobId,
            status: "awaiting_client",
          });
        }
        if (urlStr.endsWith(`/api/v1/editor/jobs/${bakeJobId}/claim`)) {
          return jsonResponse({
            claimId: "claim-uuid-3",
            claimToken,
            payload: { dummy: 1 },
          });
        }
        if (urlStr === "http://127.0.0.1:8000/bake") {
          throw new Error("Sidecar process terminated unexpectedly");
        }
        if (urlStr.endsWith(`/api/v1/editor/jobs/${bakeJobId}/fail`)) {
          const headers = (init?.headers ?? {}) as Record<string, string>;
          expect(headers["X-Claim-Token"]).toBe(claimToken);
          expect(headers.Authorization).toBeUndefined();

          const body = JSON.parse(String(init?.body));
          expect(body.code).toBe("SIDECAR_UNAVAILABLE");
          expect(body.message).toContain("Sidecar process terminated unexpectedly");

          return jsonResponse({
            id: bakeJobId,
            type: "bake",
            status: "failed",
            errorMessage: body.message,
            progress: 50,
          });
        }
        throw new Error(`Unexpected fetch call: ${urlStr}`);
      });
      vi.stubGlobal("fetch", fetchMock);

      const failedJob = await editorClient.bakeDesign("design-001");
      expect(failedJob.status).toBe("failed");
      expect(failedJob.errorMessage).toContain("Sidecar process terminated unexpectedly");
    });

    it("calls /fail when sidecar returns empty exports", async () => {
      setupDesktopTauri();

      const bakeJobId = "job-bake-fail-empty";
      const claimToken = "claim-token-secret-empty";

      const fetchMock = vi.fn().mockImplementation(async (url: string, init?: RequestInit) => {
        const urlStr = String(url);
        if (urlStr.endsWith("/api/v1/editor/designs/design-001/bake")) {
          return jsonResponse({
            id: bakeJobId,
            status: "awaiting_client",
          });
        }
        if (urlStr.endsWith(`/api/v1/editor/jobs/${bakeJobId}/claim`)) {
          return jsonResponse({
            claimId: "claim-uuid-4",
            claimToken,
            payload: { dummy: 1 },
          });
        }
        if (urlStr === "http://127.0.0.1:8000/bake") {
          return jsonResponse({ exports: [] });
        }
        if (urlStr.endsWith(`/api/v1/editor/jobs/${bakeJobId}/fail`)) {
          const body = JSON.parse(String(init?.body));
          expect(body.code).toBe("SIDECAR_OUTPUT_MISSING");
          return jsonResponse({
            id: bakeJobId,
            status: "failed",
          });
        }
        throw new Error(`Unexpected fetch call: ${urlStr}`);
      });
      vi.stubGlobal("fetch", fetchMock);

      const failedJob = await editorClient.bakeDesign("design-001");
      expect(failedJob.status).toBe("failed");
    });
  });

  describe("Desktop exports via sidecar /downloads", () => {
    function setupDesktopTauri() {
      vi.stubGlobal("window", {
        __TAURI__: {
          core: {
            invoke: vi.fn().mockImplementation(async (command: string) => {
              if (command === "get_desktop_runtime") {
                return {
                  apiBaseUrl: "http://127.0.0.1:8000",
                  backendStatus: "ready",
                  blenderStatus: "installed",
                  demoProjectStatus: "ready",
                  diagnosticSummary: "",
                  backendPort: 8000,
                  storagePath: "",
                  blenderPath: "",
                  logsPath: "",
                  appVersion: "1.0.0",
                  sidecarToken: "sidecar-token-xyz",
                };
              }
              return null;
            }),
          },
        },
      });
    }

    it("downloadExport calls KusShoes /content then POST /downloads with X-Service-Token", async () => {
      setupDesktopTauri();

      const exportPkg: ExportPackage = {
        id: "exp-888",
        designId: "design-001",
        status: "ready",
        downloadUrl: "/api/v1/editor/exports/exp-888/content",
        files: ["zip"],
        createdAt: "2026-09-24T00:00:00Z",
      };

      const fetchMock = vi.fn().mockImplementation(async (url: string, init?: RequestInit) => {
        const urlStr = String(url);
        if (urlStr.endsWith("/api/v1/editor/exports/exp-888/content")) {
          expect(init?.headers).toMatchObject({
            Authorization: "Bearer editor-session-token",
          });
          return jsonResponse({
            url: "https://r2.storage.test/exports/kusshoes-shoe.zip?signature=secret",
            expiresIn: 900,
            filename: "kusshoes-shoe.zip",
            contentType: "application/zip",
          });
        }
        if (urlStr === "http://127.0.0.1:8000/downloads") {
          expect((init?.headers as Record<string, string>)["X-Service-Token"]).toBe("sidecar-token-xyz");
          const body = JSON.parse(String(init?.body));
          expect(body).toEqual({
            url: "https://r2.storage.test/exports/kusshoes-shoe.zip?signature=secret",
            filename: "kusshoes-shoe.zip",
          });
          return jsonResponse({
            path: "C:\\Users\\User\\Downloads\\kusshoes-shoe.zip",
            file_size_bytes: 8192,
          });
        }
        throw new Error(`Unexpected fetch call: ${urlStr}`);
      });
      vi.stubGlobal("fetch", fetchMock);

      await editorClient.downloadExport(exportPkg);

      expect(fetchMock).toHaveBeenCalledTimes(2);
      const [contentCall, downloadCall] = fetchMock.mock.calls;
      expect(contentCall[0]).toContain("/api/v1/editor/exports/exp-888/content");
      expect(downloadCall[0]).toBe("http://127.0.0.1:8000/downloads");
    });

    it("api.downloadExport calls KusShoes /content then POST /downloads with X-Service-Token", async () => {
      setupDesktopTauri();

      const exportPkg: ExportPackage = {
        id: "exp-999",
        designId: "design-001",
        status: "ready",
        downloadUrl: "/api/v1/editor/exports/exp-999/content",
        files: ["glb"],
        createdAt: "2026-09-24T00:00:00Z",
      };

      const fetchMock = vi.fn().mockImplementation(async (url: string, init?: RequestInit) => {
        const urlStr = String(url);
        if (urlStr.endsWith("/api/v1/editor/exports/exp-999/content")) {
          expect(init?.headers).toMatchObject({
            Authorization: "Bearer editor-session-token",
          });
          return jsonResponse({
            url: "https://r2.storage.test/exports/shoe.glb?signature=secret",
            expiresIn: 900,
            filename: "shoe.glb",
            contentType: "model/gltf-binary",
          });
        }
        if (urlStr === "http://127.0.0.1:8000/downloads") {
          expect((init?.headers as Record<string, string>)["X-Service-Token"]).toBe("sidecar-token-xyz");
          const body = JSON.parse(String(init?.body));
          expect(body).toEqual({
            url: "https://r2.storage.test/exports/shoe.glb?signature=secret",
            filename: "shoe.glb",
          });
          return jsonResponse({
            path: "C:\\Users\\User\\Downloads\\shoe.glb",
            file_size_bytes: 4096,
          });
        }
        throw new Error(`Unexpected fetch call: ${urlStr}`);
      });
      vi.stubGlobal("fetch", fetchMock);

      await api.downloadExport(exportPkg);

      expect(fetchMock).toHaveBeenCalledTimes(2);
    });
  });

  describe("isTerminalJobStatus", () => {
    it("treats cancelled, completed, and failed as terminal", () => {
      expect(isTerminalJobStatus("completed")).toBe(true);
      expect(isTerminalJobStatus("failed")).toBe(true);
      expect(isTerminalJobStatus("cancelled")).toBe(true);
    });

    it("treats in-progress states as non-terminal", () => {
      expect(isTerminalJobStatus("queued")).toBe(false);
      expect(isTerminalJobStatus("processing")).toBe(false);
      expect(isTerminalJobStatus("awaiting_client")).toBe(false);
      expect(isTerminalJobStatus("claimed")).toBe(false);
      expect(isTerminalJobStatus("unknown")).toBe(false);
    });
  });

  describe("Local mode fallback", () => {
    it("calls local routes when no KusShoes session is active", async () => {
      clearEditorLaunchSession();

      const fetchMock = vi.fn().mockImplementation(async (url: string) => {
        const urlStr = String(url);
        if (urlStr.endsWith("/api/designs/design-001/bake")) {
          return jsonResponse({
            id: "local-job-1",
            status: "queued",
          });
        }
        if (urlStr.endsWith("/api/designs/design-001/export")) {
          return jsonResponse({
            id: "local-exp-1",
            status: "ready",
          });
        }
        throw new Error(`Unexpected fetch: ${urlStr}`);
      });
      vi.stubGlobal("fetch", fetchMock);

      const job = await editorClient.bakeDesign("design-001");
      expect(job.id).toBe("local-job-1");

      const exp = await editorClient.exportDesign("design-001");
      expect(exp.id).toBe("local-exp-1");
    });
  });
});
