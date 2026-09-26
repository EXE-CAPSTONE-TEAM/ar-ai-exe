import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { CropBox, ExportPackage } from "../types";
import { DEFAULT_CROP_BOX } from "../types";
import { storeEphemeralAccessToken } from "./authStorage";
import { api } from "./client";
import { EditorApiError, editorClient, isTerminalJobStatus } from "./editorClient";
import { clearEditorLaunchSession, setActiveEditorSessionForTesting } from "./editorLaunch";
import { messageFromError } from "../utils/editorMessages";

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

describe("editorClient (Ticket-06 & Ticket-09)", () => {
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

    it("prepareModel returns DESKTOP_REQUIRED without network calls", async () => {
      const fetchMock = vi.fn();
      vi.stubGlobal("fetch", fetchMock);

      await expect(editorClient.prepareModel("project-456", DEFAULT_CROP_BOX)).rejects.toSatisfy((err: unknown) => {
        return err instanceof EditorApiError && err.code === "DESKTOP_REQUIRED";
      });

      expect(fetchMock).not.toHaveBeenCalled();
    });

    it("api.prepareModel returns DESKTOP_REQUIRED without network calls", async () => {
      const fetchMock = vi.fn();
      vi.stubGlobal("fetch", fetchMock);

      await expect(api.prepareModel("project-456", DEFAULT_CROP_BOX)).rejects.toSatisfy((err: unknown) => {
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

  describe("Desktop mode prepareModel lifecycle", () => {
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
                  sidecarToken: "sidecar-token-prepare-xyz",
                };
              }
              return null;
            }),
          },
        },
      });
    }

    const testCropBox: CropBox = {
      center: { x: 0.1, y: -0.1, z: 0.05 },
      size: { x: 0.8, y: 0.9, z: 0.7 },
      rotation: { x: 10, y: 0, z: -5 },
      coordinateSpace: "normalized",
    };

    it("completes full create -> claim -> sidecar -> complete sequence with X-Claim-Token and cleanupReport", async () => {
      setupDesktopTauri();

      const prepareJobId = "job-prepare-123";
      const claimToken = "claim-token-prep-abc";
      const sidecarPayload = {
        job_id: prepareJobId,
        project_id: "project-456",
        crop_box: testCropBox,
        source_model: {
          asset_id: "asset-raw-1",
          download_url: "https://r2.test/raw.glb",
          file_size_bytes: 2048,
          mime_type: "model/gltf-binary",
        },
        outputs: [
          {
            format: "glb",
            file_path: `staging/project-456/${prepareJobId}/claim-1/prepared.glb`,
            upload_url: "https://r2.test/upload-prepared",
            content_type: "model/gltf-binary",
          },
        ],
      };

      const fetchMock = vi.fn().mockImplementation(async (url: string, init?: RequestInit) => {
        const urlStr = String(url);
        // Step 1: create prepare job on KusShoes BE
        if (urlStr.endsWith("/api/v1/editor/projects/project-456/prepare")) {
          expect(init?.headers).toMatchObject({
            Authorization: "Bearer editor-session-token",
          });
          const body = JSON.parse(String(init?.body));
          expect(body.cropBox).toEqual(testCropBox);
          expect(body.confirmResetDesign).toBe(false);

          return jsonResponse({
            id: prepareJobId,
            type: "prepare",
            status: "awaiting_client",
            progress: 0,
            errorMessage: null,
            projectId: "project-456",
            createdAt: "2026-09-24T00:00:00Z",
            updatedAt: "2026-09-24T00:00:00Z",
          });
        }
        // Step 2: claim job on KusShoes BE
        if (urlStr.endsWith(`/api/v1/editor/jobs/${prepareJobId}/claim`)) {
          expect(init?.headers).toMatchObject({
            Authorization: "Bearer editor-session-token",
          });
          return jsonResponse({
            claimId: "claim-uuid-prep-1",
            claimToken,
            leaseExpiresAt: "2026-09-24T01:00:00Z",
            payload: sidecarPayload,
          });
        }
        // Step 3: sidecar POST /prepare
        if (urlStr === "http://127.0.0.1:8000/prepare") {
          expect((init?.headers as Record<string, string>)["X-Service-Token"]).toBe("sidecar-token-prepare-xyz");
          expect(JSON.parse(String(init?.body))).toEqual(sidecarPayload);
          return jsonResponse({
            outputs: [
              {
                format: "glb",
                file_path: `staging/project-456/${prepareJobId}/claim-1/prepared.glb`,
                file_size_bytes: 8192,
              },
            ],
            cleanup_report: {
              editorReady: true,
              editorReadyScore: 98,
              meshObjectCount: 1,
            },
          });
        }
        // Step 4: complete on KusShoes BE
        if (urlStr.endsWith(`/api/v1/editor/jobs/${prepareJobId}/complete`)) {
          const headers = (init?.headers ?? {}) as Record<string, string>;
          expect(headers["X-Claim-Token"]).toBe(claimToken);
          expect(headers.Authorization).toBeUndefined();

          const body = JSON.parse(String(init?.body));
          expect(body.outputs).toEqual([
            {
              format: "glb",
              filePath: `staging/project-456/${prepareJobId}/claim-1/prepared.glb`,
              fileSizeBytes: 8192,
            },
          ]);
          expect(body.cleanupReport).toEqual({
            editorReady: true,
            editorReadyScore: 98,
            meshObjectCount: 1,
          });
          expect(body.watermarkApplied).toBe(false);

          return jsonResponse({
            id: prepareJobId,
            type: "prepare",
            status: "completed",
            progress: 100,
            errorMessage: null,
            projectId: "project-456",
            createdAt: "2026-09-24T00:00:00Z",
            updatedAt: "2026-09-24T00:01:00Z",
          });
        }
        throw new Error(`Unexpected fetch call: ${urlStr}`);
      });
      vi.stubGlobal("fetch", fetchMock);

      const job = await editorClient.prepareModel("project-456", testCropBox);
      expect(job.status).toBe("completed");
      expect(job.id).toBe(prepareJobId);
      expect(fetchMock).toHaveBeenCalledTimes(4);
    });

    it("sends confirmResetDesign: true when requested", async () => {
      setupDesktopTauri();

      const prepareJobId = "job-prepare-reset";
      const claimToken = "claim-token-reset-1";

      const fetchMock = vi.fn().mockImplementation(async (url: string, init?: RequestInit) => {
        const urlStr = String(url);
        if (urlStr.endsWith("/api/v1/editor/projects/project-456/prepare")) {
          const body = JSON.parse(String(init?.body));
          expect(body.confirmResetDesign).toBe(true);
          return jsonResponse({
            id: prepareJobId,
            type: "prepare",
            status: "awaiting_client",
          });
        }
        if (urlStr.endsWith(`/api/v1/editor/jobs/${prepareJobId}/claim`)) {
          return jsonResponse({
            claimId: "claim-uuid-reset",
            claimToken,
            payload: {},
          });
        }
        if (urlStr === "http://127.0.0.1:8000/prepare") {
          return jsonResponse({
            outputs: [{ format: "glb", filePath: "path/prepared.glb", fileSizeBytes: 1024 }],
          });
        }
        if (urlStr.endsWith(`/api/v1/editor/jobs/${prepareJobId}/complete`)) {
          return jsonResponse({
            id: prepareJobId,
            type: "prepare",
            status: "completed",
          });
        }
        throw new Error(`Unexpected fetch: ${urlStr}`);
      });
      vi.stubGlobal("fetch", fetchMock);

      const job = await editorClient.prepareModel("project-456", testCropBox, true);
      expect(job.status).toBe("completed");
    });

    it("propagates 409 EDITOR_DESIGN_RESET_REQUIRED when re-crop requires confirmation", async () => {
      setupDesktopTauri();

      const fetchMock = vi.fn().mockImplementation(async (url: string) => {
        const urlStr = String(url);
        if (urlStr.endsWith("/api/v1/editor/projects/project-456/prepare")) {
          return jsonResponse(
            {
              code: "EDITOR_DESIGN_RESET_REQUIRED",
              message: "Cắt lại sẽ xoá thiết kế hiện tại. Bạn có chắc?",
            },
            409,
          );
        }
        throw new Error(`Unexpected fetch: ${urlStr}`);
      });
      vi.stubGlobal("fetch", fetchMock);

      await expect(
        editorClient.prepareModel("project-456", testCropBox, false),
      ).rejects.toSatisfy((err: unknown) => {
        return (
          err instanceof EditorApiError &&
          err.status === 409 &&
          err.code === "EDITOR_DESIGN_RESET_REQUIRED"
        );
      });
    });

    it("calls /fail on sidecar network error without Authorization header", async () => {
      setupDesktopTauri();

      const prepareJobId = "job-prep-net-fail";
      const claimToken = "claim-token-net-fail";

      const fetchMock = vi.fn().mockImplementation(async (url: string, init?: RequestInit) => {
        const urlStr = String(url);
        if (urlStr.endsWith("/api/v1/editor/projects/project-456/prepare")) {
          return jsonResponse({ id: prepareJobId, status: "awaiting_client" });
        }
        if (urlStr.endsWith(`/api/v1/editor/jobs/${prepareJobId}/claim`)) {
          return jsonResponse({ claimToken, payload: {} });
        }
        if (urlStr === "http://127.0.0.1:8000/prepare") {
          throw new TypeError("Failed to fetch (sidecar crashed)");
        }
        if (urlStr.endsWith(`/api/v1/editor/jobs/${prepareJobId}/fail`)) {
          const headers = (init?.headers ?? {}) as Record<string, string>;
          expect(headers["X-Claim-Token"]).toBe(claimToken);
          expect(headers.Authorization).toBeUndefined();

          const body = JSON.parse(String(init?.body));
          expect(body.code).toBe("SIDECAR_UNAVAILABLE");
          expect(body.message).toContain("sidecar crashed");

          return jsonResponse({
            id: prepareJobId,
            type: "prepare",
            status: "failed",
            errorMessage: body.message,
          });
        }
        throw new Error(`Unexpected fetch: ${urlStr}`);
      });
      vi.stubGlobal("fetch", fetchMock);

      const failedJob = await editorClient.prepareModel("project-456", testCropBox);
      expect(failedJob.status).toBe("failed");
      expect(failedJob.id).toBe(prepareJobId);
    });

    it("calls /fail on sidecar 503 error", async () => {
      setupDesktopTauri();

      const prepareJobId = "job-prep-503";
      const claimToken = "claim-token-503";

      const fetchMock = vi.fn().mockImplementation(async (url: string, init?: RequestInit) => {
        const urlStr = String(url);
        if (urlStr.endsWith("/api/v1/editor/projects/project-456/prepare")) {
          return jsonResponse({ id: prepareJobId, status: "awaiting_client" });
        }
        if (urlStr.endsWith(`/api/v1/editor/jobs/${prepareJobId}/claim`)) {
          return jsonResponse({ claimToken, payload: {} });
        }
        if (urlStr === "http://127.0.0.1:8000/prepare") {
          return jsonResponse({ detail: "Prepare worker is at capacity." }, 503);
        }
        if (urlStr.endsWith(`/api/v1/editor/jobs/${prepareJobId}/fail`)) {
          const body = JSON.parse(String(init?.body));
          expect(body.code).toBe("WORKER_BUSY");
          return jsonResponse({
            id: prepareJobId,
            status: "failed",
            errorMessage: body.message,
          });
        }
        throw new Error(`Unexpected fetch: ${urlStr}`);
      });
      vi.stubGlobal("fetch", fetchMock);

      const failedJob = await editorClient.prepareModel("project-456", testCropBox);
      expect(failedJob.status).toBe("failed");
    });

    it("calls /fail when sidecar returns empty outputs", async () => {
      setupDesktopTauri();

      const prepareJobId = "job-prep-empty";
      const claimToken = "claim-token-empty";

      const fetchMock = vi.fn().mockImplementation(async (url: string, init?: RequestInit) => {
        const urlStr = String(url);
        if (urlStr.endsWith("/api/v1/editor/projects/project-456/prepare")) {
          return jsonResponse({ id: prepareJobId, status: "awaiting_client" });
        }
        if (urlStr.endsWith(`/api/v1/editor/jobs/${prepareJobId}/claim`)) {
          return jsonResponse({ claimToken, payload: {} });
        }
        if (urlStr === "http://127.0.0.1:8000/prepare") {
          return jsonResponse({ outputs: [] });
        }
        if (urlStr.endsWith(`/api/v1/editor/jobs/${prepareJobId}/fail`)) {
          const body = JSON.parse(String(init?.body));
          expect(body.code).toBe("SIDECAR_OUTPUT_MISSING");
          return jsonResponse({
            id: prepareJobId,
            status: "failed",
            errorMessage: body.message,
          });
        }
        throw new Error(`Unexpected fetch: ${urlStr}`);
      });
      vi.stubGlobal("fetch", fetchMock);

      const failedJob = await editorClient.prepareModel("project-456", testCropBox);
      expect(failedJob.status).toBe("failed");
    });

    it("notifies progress steps during prepare execution", async () => {
      setupDesktopTauri();

      const prepareJobId = "job-prep-prog";
      const claimToken = "claim-token-prog";

      const fetchMock = vi.fn().mockImplementation(async (url: string) => {
        const urlStr = String(url);
        if (urlStr.endsWith("/api/v1/editor/projects/project-456/prepare")) {
          return jsonResponse({ id: prepareJobId, status: "awaiting_client" });
        }
        if (urlStr.endsWith(`/api/v1/editor/jobs/${prepareJobId}/claim`)) {
          return jsonResponse({ claimToken, payload: {} });
        }
        if (urlStr === "http://127.0.0.1:8000/prepare") {
          return jsonResponse({
            outputs: [{ format: "glb", filePath: "path/prepared.glb", fileSizeBytes: 1024 }],
          });
        }
        if (urlStr.endsWith(`/api/v1/editor/jobs/${prepareJobId}/complete`)) {
          return jsonResponse({
            id: prepareJobId,
            status: "completed",
          });
        }
        throw new Error(`Unexpected fetch: ${urlStr}`);
      });
      vi.stubGlobal("fetch", fetchMock);

      const progressSteps: string[] = [];
      await editorClient.prepareModel("project-456", testCropBox, false, (step) => {
        progressSteps.push(step);
      });

      expect(progressSteps).toEqual(["downloading", "cropping", "uploading", "done"]);
    });

    it("maps PRD §3 error codes to Vietnamese messages via messageFromError", () => {
      const errReset = new EditorApiError("reset required", 409, "EDITOR_DESIGN_RESET_REQUIRED");
      expect(messageFromError(errReset)).toBe("Cắt lại sẽ xoá thiết kế hiện tại. Bạn có chắc?");

      const errNoRaw = new EditorApiError("no raw model", 409, "EDITOR_NO_RAW_MODEL");
      expect(messageFromError(errNoRaw)).toBe("Project không có model scan để chuẩn bị.");

      const errDesktop = new EditorApiError("desktop required", 400, "DESKTOP_REQUIRED");
      expect(messageFromError(errDesktop)).toBe("Tính năng này cần KusStudio Desktop (Windows).");
    });
  });
});
