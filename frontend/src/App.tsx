import {
  AlertTriangle,
  CheckCircle2,
  Cloud,
  Cpu,
  Download,
  HardDrive,
  FolderOpen,
  ImagePlus,
  Info,
  Loader2,
  LogIn,
  Monitor,
  RefreshCw,
  Save,
  Search,
  Settings,
  UserPlus,
  Wrench,
  X,
} from "lucide-react";
import { FormEvent, useEffect, useMemo, useRef, useState } from "react";
import { onOpenUrl } from "@tauri-apps/plugin-deep-link";
import { listen } from "@tauri-apps/api/event";

import { api, designStorageKey } from "./api/client";
import {
  getDesktopRuntime,
  installDesktopDependency,
  openDiagnosticsFolder,
  restartDesktopBackend,
} from "./api/desktopRuntime";
import type { ModelImportPayload } from "./api/client";
import { editorClient } from "./api/editorClient";
import { setApiBaseUrl } from "./api/runtimeConfig";
import { EditorPanels } from "./components/Editor/EditorPanels";
import { AppShell } from "./components/Layout/AppShell";
import { MetadataPanel } from "./components/MetadataPanel/MetadataPanel";
import { ModelImportPanel } from "./components/ModelImport/ModelImportPanel";
import { ModelViewer } from "./components/ModelViewer/ModelViewer";
import { useEditorContext } from "./hooks/useEditorContext";
import type {
  Design,
  CloudProject,
  DesignAssetSource,
  DesignConfig,
  DesktopRuntime,
  EditorContext,
  EditorPermissions,
  EditorReadiness,
  ExportPackage,
  InstallProgress,
  Job,
  ModelAsset,
  ScanSession,
  TextLayer,
  User,
} from "./types";
import {
  editorRouteStateLabel,
  friendlyInlineMessage,
  messageFromError,
  noticeFromStatus,
} from "./utils/editorMessages";

const MARKETING_LOGIN_URL = import.meta.env.VITE_MARKETING_LOGIN_URL ?? "https://kusshoes.vn/login";
const DESKTOP_DEMO_PROJECT_ID = import.meta.env.VITE_DESKTOP_DEMO_PROJECT_ID ?? "proj_desktop_demo";
const DESKTOP_CLOUD_API_BASE_URL = (import.meta.env.VITE_DESKTOP_CLOUD_API_BASE_URL || import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000").replace(/\/+$/, "");
const DEFAULT_EDITOR_PERMISSIONS: EditorPermissions = { canEdit: true, canBake: true, canExport: true };
type DesktopApiMode = "local" | "cloud";

export function App() {
  const isDesktopShell = useMemo(() => isDesktopShellLocation(), []);
  const editorProjectId = useMemo(() => editorProjectIdFromLocation(isDesktopShell), [isDesktopShell]);
  const isProjectEditor = Boolean(editorProjectId);
  const [desktopRuntime, setDesktopRuntime] = useState<DesktopRuntime | null>(null);
  const [desktopRuntimeError, setDesktopRuntimeError] = useState<string | null>(null);
  const [isDesktopRuntimeLoading, setIsDesktopRuntimeLoading] = useState(isDesktopShell);
  const [desktopApiMode, setDesktopApiMode] = useState<DesktopApiMode>(() => {
    const stored = localStorage.getItem("kusshoes-desktop-api-mode");
    return stored === "cloud" ? "cloud" : "local";
  });
  const [desktopCloudReady, setDesktopCloudReady] = useState(false);
  const [cloudProjects, setCloudProjects] = useState<CloudProject[]>([]);
  const [isCloudProjectsLoading, setIsCloudProjectsLoading] = useState(false);
  const cloudProjectsLoadingRef = useRef(false);
  const [editorReadiness, setEditorReadiness] = useState<EditorReadiness | null>(null);
  const [installProgress, setInstallProgress] = useState<InstallProgress | null>(null);
  const desktopRuntimeReady =
    !isDesktopShell ||
    (desktopApiMode === "cloud" ? desktopCloudReady : desktopRuntime?.backendStatus === "ready");
  const editorContext = useEditorContext(desktopRuntimeReady ? editorProjectId : null);
  const [user, setUser] = useState<User | null>(null);
  const [scanId, setScanId] = useState(() => new URLSearchParams(window.location.search).get("scanId") ?? "");
  const [scanSession, setScanSession] = useState<ScanSession | null>(null);
  const [modelAsset, setModelAsset] = useState<ModelAsset | null>(null);
  const [modelUrl, setModelUrl] = useState<string | null>(null);
  const [previewModelUrl, setPreviewModelUrl] = useState<string | null>(null);
  const [bakedLayerIds, setBakedLayerIds] = useState<string[]>([]);
  const [savedConfigFingerprint, setSavedConfigFingerprint] = useState<string | null>(null);
  const [design, setDesign] = useState<Design | null>(null);
  const [previewErrorMessage, setPreviewErrorMessage] = useState<string | null>(null);
  const [designName, setDesignName] = useState("Untitled shoe design");
  const [config, setConfig] = useState<DesignConfig | null>(null);
  const [exportPackage, setExportPackage] = useState<ExportPackage | null>(null);
  const [statusMessage, setStatusMessage] = useState("Ready");
  const [isSaving, setIsSaving] = useState(false);
  const [isBakingPreview, setIsBakingPreview] = useState(false);
  const [isExporting, setIsExporting] = useState(false);
  const [exportMessage, setExportMessage] = useState<string | null>(null);
  const [isImporting, setIsImporting] = useState(false);
  const [authMode, setAuthMode] = useState<"login" | "register">("login");
  const [authName, setAuthName] = useState("");
  const [authEmail, setAuthEmail] = useState("");
  const [authPassword, setAuthPassword] = useState("");
  const [isAuthBusy, setIsAuthBusy] = useState(false);
  const [activeLayerId, setActiveLayerId] = useState<string | null>(null);
  const [meshBounds, setMeshBounds] = useState<{ center: [number, number, number]; size: [number, number, number] } | null>(null);
  const [gizmoMode, setGizmoMode] = useState<"translate" | "rotate" | "scale">("translate");
  const [surfaceApplyRequest, setSurfaceApplyRequest] = useState(0);
  const [editorPermissions, setEditorPermissions] = useState<EditorPermissions>(DEFAULT_EDITOR_PERMISSIONS);
  const [desktopProjectInput, setDesktopProjectInput] = useState("");
  const [desktopLaunchError, setDesktopLaunchError] = useState<string | null>(null);
  const [isDesktopDemoOpening, setIsDesktopDemoOpening] = useState(false);
  const [isDesktopImportOpen, setIsDesktopImportOpen] = useState(false);
  const [isDesktopDetailsOpen, setIsDesktopDetailsOpen] = useState(false);
  const assetPreviewUrlsRef = useRef<Set<string>>(new Set());

  // Handle Tauri Custom Protocol Deep Link and Single Instance
  useEffect(() => {
    if (!isDesktopShell) return;

    const handleDeepLinkUrl = (urlStr: string) => {
      console.log("Caught deep link URL:", urlStr);
      try {
        // Expected format: kusshoes-editor://editor/proj_123?token=abc
        const url = new URL(urlStr.replace("kusshoes-editor://", "http://localhost/"));
        const pathParts = url.pathname.split("/");
        const projectId = pathParts[2] || pathParts[1];
        const token = url.searchParams.get("token");

        if (token) {
          localStorage.setItem("shoe-customizer-token", token);
        }
        localStorage.setItem("kusshoes-desktop-api-mode", "cloud");

        if (projectId) {
          // Force page reload to apply new token and projectId
          window.location.href = `/?desktop=1&projectId=${projectId}`;
        }
      } catch (err) {
        console.error("Failed to parse deep link URL:", err);
      }
    };

    // 1. Listen for active running deep link events from other single instances
    let unsubscribeSingleInstance: (() => void) | undefined;
    listen<string[]>("single-instance-deep-link", (event) => {
      const args = event.payload;
      console.log("Single instance args received:", args);
      const deepLinkArg = args.find((arg) => arg.startsWith("kusshoes-editor://"));
      if (deepLinkArg) {
        handleDeepLinkUrl(deepLinkArg);
      }
    }).then((unsub) => {
      unsubscribeSingleInstance = unsub;
    }).catch((err) => {
      console.error("Failed to listen to single-instance-deep-link:", err);
    });

    // 2. Listen to startup deep links using the plugin
    let unsubscribeDeepLink: (() => void) | undefined;
    onOpenUrl((urls) => {
      console.log("Tauri deep link URLs received:", urls);
      if (urls.length > 0) {
        handleDeepLinkUrl(urls[0]);
      }
    }).then((unsub) => {
      unsubscribeDeepLink = unsub;
    }).catch((err) => {
      console.error("Failed to listen to tauri-plugin-deep-link onOpenUrl:", err);
    });

    return () => {
      if (unsubscribeSingleInstance) unsubscribeSingleInstance();
      if (unsubscribeDeepLink) unsubscribeDeepLink();
    };
  }, [isDesktopShell]);

  useEffect(() => {
    if (!isDesktopShell) {
      return;
    }
    if (desktopApiMode === "cloud") {
      setDesktopRuntime(null);
      setEditorReadiness(null);
      if (!DESKTOP_CLOUD_API_BASE_URL) {
        setDesktopCloudReady(false);
        setDesktopRuntimeError("VITE_DESKTOP_CLOUD_API_BASE_URL is not configured.");
        return;
      }
      setApiBaseUrl(DESKTOP_CLOUD_API_BASE_URL);
      setDesktopRuntimeError(null);
      setDesktopCloudReady(true);
      setIsDesktopRuntimeLoading(false);
      return;
    }
    setDesktopCloudReady(false);
    void refreshDesktopRuntime();
  }, [desktopApiMode, isDesktopShell]);

  useEffect(() => {
    if (!isDesktopShell || desktopApiMode !== "cloud" || !desktopCloudReady || user || !api.hasToken()) {
      return;
    }
    api.me().then(setUser).catch(() => api.logout());
  }, [desktopApiMode, desktopCloudReady, isDesktopShell, user]);

  useEffect(() => {
    if (!isDesktopShell || desktopApiMode !== "cloud" || !desktopCloudReady || !user || isProjectEditor) {
      return;
    }
    void loadCloudProjects();
    const timer = window.setInterval(() => void loadCloudProjects(), 5000);
    return () => window.clearInterval(timer);
  }, [desktopApiMode, desktopCloudReady, isDesktopShell, isProjectEditor, user]);

  useEffect(() => {
    if (isProjectEditor || isDesktopShell) {
      return;
    }
    if (!api.hasToken()) {
      setStatusMessage("Sign in to open scan designs.");
      return;
    }
    api
      .me()
      .then(setUser)
      .catch(() => {
        api.logout();
        setStatusMessage("Session expired. Sign in again.");
    });
  }, [isDesktopShell, isProjectEditor]);

  useEffect(() => {
    if (!isProjectEditor) {
      return;
    }
    if (editorContext.user) {
      setUser(editorContext.user);
    }
  }, [editorContext.user, isProjectEditor]);

  useEffect(() => {
    if (!isProjectEditor || editorContext.state !== "UNAUTHENTICATED") {
      return;
    }
    window.location.assign(loginRedirectUrl());
  }, [editorContext.state, isProjectEditor]);

  useEffect(() => {
    if (!isProjectEditor || !editorContext.context) {
      return;
    }
    void loadProjectEditorContext(editorContext.context);
  }, [editorContext.context, isProjectEditor]);

  useEffect(() => {
    if (user && scanId.trim()) {
      void loadScan();
    }
  }, [user]);

  useEffect(() => {
    if (!scanSession || modelAsset || scanSession.status === "completed" || scanSession.status === "failed") {
      return;
    }

    const timer = window.setInterval(() => {
      void loadScan();
    }, 2500);
    return () => window.clearInterval(timer);
  }, [scanSession, modelAsset, scanId]);

  useEffect(() => {
    return () => {
      if (modelUrl) {
        URL.revokeObjectURL(modelUrl);
      }
    };
  }, [modelUrl]);

  useEffect(() => {
    return () => {
      if (previewModelUrl) {
        URL.revokeObjectURL(previewModelUrl);
      }
    };
  }, [previewModelUrl]);

  useEffect(() => {
    return () => {
      clearAssetPreviewUrls();
    };
  }, []);

  const canLoad = useMemo(() => scanId.trim().length > 0 && Boolean(user), [scanId, user]);
  const activeModelUrl = previewModelUrl ?? modelUrl;
  const hiddenLayerIds = previewModelUrl ? bakedLayerIds : [];
  const canUsePreviewRenderer =
    !isDesktopShell ||
    editorReadiness?.previewRenderer.available === true ||
    desktopRuntime?.blenderStatus === "installed";
  const isEditorBusy =
    isSaving ||
    isBakingPreview ||
    isExporting ||
    isImporting ||
    isDesktopRuntimeLoading ||
    editorContext.state === "AUTH_CHECKING" ||
    editorContext.state === "PROJECT_LOADING";
  const friendlyPreviewErrorMessage = previewErrorMessage ? friendlyInlineMessage(previewErrorMessage) : null;
  const friendlyExportMessage = exportMessage ? friendlyInlineMessage(exportMessage) : null;
  const isSaved = Boolean(config && savedConfigFingerprint && configFingerprint(config) === savedConfigFingerprint);

  async function submitAuth(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setIsAuthBusy(true);
    setStatusMessage(authMode === "login" ? "Signing in" : "Creating account");
    try {
      const signedInUser =
        authMode === "login"
          ? await api.login(authEmail, authPassword)
          : await api.register(authName, authEmail, authPassword);
      setUser(signedInUser);
      setStatusMessage("Signed in");
    } catch (error) {
      setStatusMessage(messageFromError(error));
    } finally {
      setIsAuthBusy(false);
    }
  }

  async function useDemoAuth() {
    setIsAuthBusy(true);
    try {
      const demoUser = await api.demoLogin();
      setUser(demoUser);
      setStatusMessage("Demo session active");
    } catch (error) {
      setStatusMessage(messageFromError(error));
    } finally {
      setIsAuthBusy(false);
    }
  }



  async function loadEditorReadiness() {
    try {
      setEditorReadiness(await api.getEditorReadiness());
    } catch {
      setEditorReadiness(null);
    }
  }

  function changeDesktopApiMode(mode: DesktopApiMode) {
    if (mode === desktopApiMode) {
      return;
    }
    api.logout();
    setUser(null);
    setCloudProjects([]);
    setDesktopLaunchError(null);
    localStorage.setItem("kusshoes-desktop-api-mode", mode);
    setDesktopApiMode(mode);
  }

  async function loadCloudProjects() {
    if (cloudProjectsLoadingRef.current) {
      return;
    }
    cloudProjectsLoadingRef.current = true;
    setIsCloudProjectsLoading(true);
    try {
      setCloudProjects(await api.listProjects());
      setDesktopLaunchError(null);
    } catch (error) {
      setDesktopLaunchError(messageFromError(error));
    } finally {
      cloudProjectsLoadingRef.current = false;
      setIsCloudProjectsLoading(false);
    }
  }

  async function refreshDesktopRuntime() {
    setIsDesktopRuntimeLoading(true);
    setDesktopRuntimeError(null);
    try {
      const runtime = await getDesktopRuntime();
      setApiBaseUrl(runtime.apiBaseUrl);
      setDesktopRuntime(runtime);
      setStatusMessage(
        runtime.backendStatus === "ready"
          ? "EDITOR_READY"
          : "Ứng dụng chưa khởi động được backend local. Vui lòng mở Diagnostics hoặc thử Restart.",
      );
      if (runtime.backendStatus === "ready") {
        await loadEditorReadiness();
      }
    } catch (error) {
      const message = messageFromError(error);
      setDesktopRuntimeError(message);
      setStatusMessage(message);
    } finally {
      setIsDesktopRuntimeLoading(false);
    }
  }

  async function restartDesktopRuntimeBackend() {
    setIsDesktopRuntimeLoading(true);
    setDesktopRuntimeError(null);
    try {
      const runtime = await restartDesktopBackend();
      setApiBaseUrl(runtime.apiBaseUrl);
      setDesktopRuntime(runtime);
      setStatusMessage(runtime.backendStatus === "ready" ? "EDITOR_READY" : "Ứng dụng chưa khởi động được backend local.");
      if (runtime.backendStatus === "ready") {
        await loadEditorReadiness();
      }
    } catch (error) {
      const message = messageFromError(error);
      setDesktopRuntimeError(message);
      setStatusMessage(message);
    } finally {
      setIsDesktopRuntimeLoading(false);
    }
  }

  async function installPreviewRenderer() {
    setInstallProgress({
      name: "blender",
      status: "downloading",
      message: "Ứng dụng đang chuẩn bị cài Preview renderer.",
      percent: 5,
    });
    try {
      const progress = await installDesktopDependency("blender");
      setInstallProgress(progress);
      await refreshDesktopRuntime();
      if (progress.status === "installed") {
        setStatusMessage("Preview renderer đã sẵn sàng.");
      } else {
        setStatusMessage("Preview renderer cần được cấu hình trước khi cài đặt.");
      }
    } catch (error) {
      const message = messageFromError(error);
      setInstallProgress({
        name: "blender",
        status: "failed",
        message,
        percent: 0,
      });
      setStatusMessage(message);
    }
  }

  async function openDesktopDiagnostics() {
    try {
      await openDiagnosticsFolder();
    } catch (error) {
      setStatusMessage(messageFromError(error));
    }
  }

  async function copyDesktopDiagnostics() {
    const summary = desktopRuntime?.diagnosticSummary ?? desktopRuntimeError ?? "Desktop diagnostics are not available.";
    try {
      await navigator.clipboard.writeText(summary);
      setStatusMessage("Đã copy thông tin diagnostics.");
    } catch {
      setStatusMessage("Ứng dụng chưa copy được diagnostics. Vui lòng mở Logs để xem chi tiết.");
    }
  }

  function clearBakedPreview() {
    setPreviewModelUrl(null);
    setBakedLayerIds([]);
  }

  function clearSavedDesignState() {
    setSavedConfigFingerprint(null);
    setPreviewErrorMessage(null);
    clearBakedPreview();
  }

  function rememberAssetPreviewUrl(url: string): string {
    if (url.startsWith("blob:")) {
      assetPreviewUrlsRef.current.add(url);
    }
    return url;
  }

  function clearAssetPreviewUrls() {
    for (const url of assetPreviewUrlsRef.current) {
      URL.revokeObjectURL(url);
    }
    assetPreviewUrlsRef.current.clear();
  }

  function logout() {
    api.logout();
    setUser(null);
    setScanSession(null);
    setModelAsset(null);
    setModelUrl(null);
    clearAssetPreviewUrls();
    clearSavedDesignState();
    setDesign(null);
    setConfig(null);
    setExportPackage(null);
    setExportMessage(null);
    setActiveLayerId(null);
    setMeshBounds(null);
    setStatusMessage("Signed out");
  }

  async function loadScan() {
    if (!scanId.trim() || !user) {
      return;
    }

    setStatusMessage("Loading scan");
    setModelAsset(null);
    setModelUrl(null);
    clearAssetPreviewUrls();
    clearSavedDesignState();
    setExportPackage(null);
    setExportMessage(null);

    try {
      const loadedScan = await api.getScanSession(scanId.trim());
      setScanSession(loadedScan);

      setScanIdInUrl(loadedScan.id);

      if (!loadedScan.modelAssetId) {
        setStatusMessage(`${scanStatusLabel(loadedScan.status)}. Waiting for model output.`);
        return;
      }

      const loadedModel = await api.getModelAsset(loadedScan.modelAssetId);
      setModelAsset(loadedModel);
      setModelUrl(await api.fetchModelBlobUrl(loadedModel));
      const loadedPreview = await loadSavedDesign(loadedModel.id);
      setStatusMessage(loadedPreview ? "Model loaded with saved preview" : "Model loaded");
    } catch (error) {
      setStatusMessage(messageFromError(error));
    }
  }

  async function loadProjectEditorContext(context: EditorContext) {
    setStatusMessage("Loading project");
    setEditorPermissions(context.permissions);
    setScanSession(null);
    setModelAsset(null);
    setModelUrl(null);
    clearAssetPreviewUrls();
    clearSavedDesignState();
    setExportPackage(null);
    setExportMessage(null);
    setActiveLayerId(null);
    setMeshBounds(null);

    const loadedModel = context.modelAsset;
    if (!loadedModel) {
      setDesign(context.latestDesign);
      setConfig(null);
      setDesignName(context.latestDesign?.name ?? context.project.name);
      setStatusMessage("MODEL_PROCESSING: Project model is not ready yet.");
      return;
    }
    if (loadedModel.status === "failed") {
      setConfig(null);
      setStatusMessage("MODEL_PROCESSING: Project model processing failed.");
      return;
    }
    if (loadedModel.status !== "ready") {
      setConfig(null);
      setStatusMessage("MODEL_PROCESSING: Project model is still processing.");
      return;
    }

    try {
      setModelAsset(loadedModel);
      setModelUrl(await api.fetchModelBlobUrl(loadedModel));
      if (context.latestDesign) {
        setDesign(context.latestDesign);
        setDesignName(context.latestDesign.name);
        const hydratedConfig = normalizeFixedMaterial(
          await hydrateDesignAssetPreviewUrls(context.latestDesign.designConfig),
        );
        setConfig(hydratedConfig);
        setSavedConfigFingerprint(configFingerprint(context.latestDesign.designConfig));
        setPreviewErrorMessage(
          context.latestDesign.previewStatus === "failed"
            ? context.latestDesign.previewErrorMessage
            : null,
        );
        await loadBakedPreview(context.latestDesign);
      } else {
        setDesign(null);
        setDesignName(context.project.name);
        setConfig(createDefaultConfig(loadedModel.id));
        setSavedConfigFingerprint(null);
      }
      setStatusMessage(context.latestDesign?.previewGlbUrl ? "PREVIEW_READY" : "EDITOR_READY");
    } catch (error) {
      setStatusMessage(messageFromError(error));
    }
  }

  async function importModel(payload: ModelImportPayload) {
    setIsImporting(true);
    setStatusMessage("Importing model");
    setModelAsset(null);
    setModelUrl(null);
    clearAssetPreviewUrls();
    clearSavedDesignState();
    setDesign(null);
    setConfig(null);
    setExportPackage(null);
    setExportMessage(null);
    setActiveLayerId(null);
    setMeshBounds(null);

    try {
      const imported = await api.importModel(payload);
      setScanId(imported.scanSession.id);
      setScanSession(imported.scanSession);
      setModelAsset(imported.modelAsset);
      setScanIdInUrl(imported.scanSession.id);
      setModelUrl(await api.fetchModelBlobUrl(imported.modelAsset));
      const loadedPreview = await loadSavedDesign(imported.modelAsset.id);
      setStatusMessage(loadedPreview ? "Imported model loaded with saved preview" : "Imported model loaded");
    } catch (error) {
      setStatusMessage(messageFromError(error));
    } finally {
      setIsImporting(false);
    }
  }

  async function loadSavedDesign(modelAssetId: string): Promise<boolean> {
    const savedDesignId = localStorage.getItem(designStorageKey(modelAssetId));
    if (!savedDesignId) {
      const defaultConfig = createDefaultConfig(modelAssetId);
      setConfig(defaultConfig);
      setDesign(null);
      setDesignName("Untitled shoe design");
      clearSavedDesignState();
      return false;
    }

    try {
      const savedDesign = await api.getDesign(savedDesignId);
      setDesign(savedDesign);
      setDesignName(savedDesign.name);
      const hydratedConfig = normalizeFixedMaterial(await hydrateDesignAssetPreviewUrls(savedDesign.designConfig));
      const savedFingerprint = configFingerprint(savedDesign.designConfig);
      setConfig(hydratedConfig);
      setSavedConfigFingerprint(savedFingerprint);
      setPreviewErrorMessage(savedDesign.previewStatus === "failed" ? savedDesign.previewErrorMessage : null);
      if (configFingerprint(hydratedConfig) !== savedFingerprint) {
        clearBakedPreview();
        return false;
      }
      return await loadBakedPreview(savedDesign);
    } catch {
      localStorage.removeItem(designStorageKey(modelAssetId));
      setDesign(null);
      setConfig(createDefaultConfig(modelAssetId));
      clearSavedDesignState();
      return false;
    }
  }

  async function loadBakedPreview(savedDesign: Design): Promise<boolean> {
    if (!savedDesign.previewGlbUrl || savedDesign.previewStatus !== "ready") {
      clearBakedPreview();
      return false;
    }

    try {
      const previewUrl = await api.fetchDesignPreviewBlobUrl(savedDesign);
      if (!previewUrl) {
        clearBakedPreview();
        return false;
      }
      setPreviewModelUrl(previewUrl);
      setBakedLayerIds(layerIds(savedDesign.designConfig));
      return true;
    } catch (error) {
      clearBakedPreview();
      setStatusMessage(`Preview load failed: ${messageFromError(error)}`);
      return false;
    }
  }

  async function hydrateDesignAssetPreviewUrls(designConfig: DesignConfig): Promise<DesignConfig> {
    const stickers = await Promise.all(
      designConfig.stickers.map(async (sticker) => {
        if (!sticker.assetId || sticker.previewUrl) {
          return sticker;
        }
        try {
          return {
            ...sticker,
            previewUrl: rememberAssetPreviewUrl(await api.fetchDesignAssetBlobUrl(sticker.assetId)),
          };
        } catch {
          return sticker;
        }
      }),
    );
    return { ...designConfig, stickers };
  }

  async function persistDesignDraft(): Promise<Design | null> {
    if (!modelAsset || !config) {
      return null;
    }
    if (isProjectEditor && !editorPermissions.canEdit) {
      setStatusMessage("FORBIDDEN: You do not have permission to save this design.");
      return null;
    }

    const draftConfig = withEditorMetadata(await prepareBakeConfig(config));
    const savedDesign =
      isProjectEditor && editorProjectId
        ? await editorClient.saveDesign(editorProjectId, draftConfig, designName)
        : design
          ? await api.updateDesign(design.id, designName, draftConfig)
          : await api.createDesign(modelAsset.id, designName, draftConfig);
    const hydratedConfig = normalizeFixedMaterial(await hydrateDesignAssetPreviewUrls(savedDesign.designConfig));

    setDesign(savedDesign);
    setDesignName(savedDesign.name);
    setConfig(hydratedConfig);
    setSavedConfigFingerprint(configFingerprint(savedDesign.designConfig));
    setPreviewErrorMessage(savedDesign.previewStatus === "failed" ? savedDesign.previewErrorMessage : null);
    setExportPackage(null);
    setExportMessage(null);
    if (!isProjectEditor) {
      localStorage.setItem(designStorageKey(modelAsset.id), savedDesign.id);
    }
    await loadBakedPreview(savedDesign);
    return savedDesign;
  }

  async function saveDesign() {
    if (isSaving || isBakingPreview) {
      return null;
    }

    setIsSaving(true);
    setStatusMessage("SAVING_DRAFT");
    try {
      const savedDesign = await persistDesignDraft();
      if (savedDesign) {
        setStatusMessage("DRAFT_SAVED");
      }
      return savedDesign;
    } catch (error) {
      setStatusMessage(messageFromError(error));
      return null;
    } finally {
      setIsSaving(false);
    }
  }

  async function bakePreview() {
    if (isSaving || isBakingPreview || !modelAsset || !config) {
      return null;
    }
    if (isProjectEditor && (!editorPermissions.canEdit || !editorPermissions.canBake)) {
      setStatusMessage("FORBIDDEN: You do not have permission to bake this design.");
      return null;
    }
    if (!canUsePreviewRenderer) {
      const message = "Preview renderer cần cài đặt trước khi bake preview. Draft của bạn vẫn có thể lưu riêng.";
      setPreviewErrorMessage(message);
      setStatusMessage(message);
      return null;
    }

    setIsBakingPreview(true);
    setStatusMessage("SAVING_DRAFT");
    try {
      const savedDesign = await persistDesignDraft();
      if (!savedDesign) {
        return null;
      }

      const job = isProjectEditor
        ? await editorClient.bakeDesign(savedDesign.id)
        : await api.bakeDesign(savedDesign.id);
      setStatusMessage("BAKING");
      const completedJob = isProjectEditor
        ? await waitForBakeJob(job.id, editorClient.getJob)
        : await waitForBakeJob(job.id, api.getJob);
      const refreshedDesign = isProjectEditor
        ? await editorClient.getDesign(savedDesign.id)
        : await api.getDesign(savedDesign.id);
      setDesign(refreshedDesign);
      setDesignName(refreshedDesign.name);
      setConfig(normalizeFixedMaterial(await hydrateDesignAssetPreviewUrls(refreshedDesign.designConfig)));
      setSavedConfigFingerprint(configFingerprint(refreshedDesign.designConfig));
      if (!isProjectEditor) {
        localStorage.setItem(designStorageKey(modelAsset.id), refreshedDesign.id);
      }
      const hasPreview = await loadBakedPreview(refreshedDesign);
      if (completedJob.status === "failed" || refreshedDesign.previewStatus === "failed") {
        const message =
          completedJob.errorMessage ??
          refreshedDesign.previewErrorMessage ??
          "Move the sticker/text closer to the shoe and save again.";
        setPreviewErrorMessage(message);
        setStatusMessage(message);
      } else {
        setPreviewErrorMessage(null);
        setStatusMessage(hasPreview ? "PREVIEW_READY" : "EDITOR_READY");
      }
      return refreshedDesign;
    } catch (error) {
      setStatusMessage(messageFromError(error));
      return null;
    } finally {
      setIsBakingPreview(false);
    }
  }

  function handleConfigChange(nextConfig: DesignConfig) {
    if (isProjectEditor && !editorPermissions.canEdit) {
      setStatusMessage("FORBIDDEN: You do not have permission to edit this design.");
      return;
    }
    if (previewModelUrl && config && !canKeepBakedPreview(config, nextConfig, bakedLayerIds)) {
      clearBakedPreview();
    }
    setPreviewErrorMessage(null);
    setExportPackage(null);
    setExportMessage(null);
    setConfig(nextConfig);
  }

  function applyActiveLayerToSurface() {
    setSurfaceApplyRequest((value) => value + 1);
  }

  async function uploadDesignAssetWithPreview(file: File, sourceType: Extract<DesignAssetSource, "upload" | "canvas">) {
    if (isProjectEditor && !editorPermissions.canEdit) {
      throw new Error("You do not have permission to edit this design.");
    }
    const asset = await api.uploadDesignAsset(file, sourceType);
    return {
      assetId: asset.id,
      sourceType,
      fileName: asset.fileName,
      previewUrl: rememberAssetPreviewUrl(await api.fetchDesignAssetBlobUrl(asset.id)),
    };
  }

  async function exportDesign() {
    if (isSaving || isBakingPreview || isExporting) {
      return;
    }
    if (isProjectEditor && !editorPermissions.canExport) {
      setExportMessage("You do not have permission to export this design.");
      setStatusMessage("FORBIDDEN: You do not have permission to export this design.");
      return;
    }
    if (!canUsePreviewRenderer) {
      const message = "Preview renderer cần cài đặt trước khi export.";
      setExportMessage(message);
      setStatusMessage(message);
      return;
    }

    setIsExporting(true);
    setExportMessage("EXPORTING");
    setStatusMessage("EXPORTING");
    try {
      const hasUnsavedConfig = config ? configFingerprint(config) !== savedConfigFingerprint : false;
      const savedDesign = !design || hasUnsavedConfig ? await persistDesignDraft() : design;
      const activeDesignId =
        savedDesign?.id ??
        (isProjectEditor ? design?.id : modelAsset && localStorage.getItem(designStorageKey(modelAsset.id)));
      if (!activeDesignId) {
        setExportMessage("Save the draft before exporting.");
        setStatusMessage("Save the draft before exporting.");
        return;
      }

      setExportMessage("Creating ZIP package...");
      setStatusMessage("Creating export package");
      const createdExport = isProjectEditor
        ? await editorClient.exportDesign(activeDesignId)
        : await api.exportDesign(activeDesignId);
      setExportPackage(createdExport);
      setExportMessage("ZIP package ready. Download starting...");
      setStatusMessage("EXPORT_READY");
      await api.downloadExport(createdExport);
      setExportMessage("Download started. Use Download ZIP again if the browser blocked it.");
      setStatusMessage("EXPORT_READY");
    } catch (error) {
      const message = messageFromError(error);
      setExportMessage(message);
      setStatusMessage(message);
    } finally {
      setIsExporting(false);
    }
  }

  async function downloadExport() {
    if (!exportPackage || isSaving || isBakingPreview || isExporting) {
      return;
    }
    setIsExporting(true);
    setExportMessage("Downloading ZIP...");
    try {
      await api.downloadExport(exportPackage);
      setExportMessage("Download started.");
      setStatusMessage("Export package downloaded");
    } catch (error) {
      const message = messageFromError(error);
      setExportMessage(message);
      setStatusMessage(message);
    } finally {
      setIsExporting(false);
    }
  }

  async function downloadModelFile(urlPath: string, filename: string) {
    try {
      await api.downloadModelFile(urlPath, filename);
    } catch (error) {
      setStatusMessage(messageFromError(error));
    }
  }

  function openDesktopProject(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const projectId = projectIdFromEditorInput(desktopProjectInput);
    if (!projectId) {
      setDesktopLaunchError("Enter a Project ID or a valid /editor/{projectId} URL.");
      return;
    }
    openDesktopProjectId(projectId);
  }

  async function openDesktopDemoProject() {
    const projectId = sanitizeProjectId(DESKTOP_DEMO_PROJECT_ID);
    if (!projectId) {
      setDesktopLaunchError("Desktop demo project is not configured.");
      return;
    }
    setIsDesktopDemoOpening(true);
    setDesktopLaunchError(null);
    try {
      await api.demoLogin();
      openDesktopProjectId(projectId);
    } catch (error) {
      setDesktopLaunchError(messageFromError(error));
      setIsDesktopDemoOpening(false);
    }
  }

  async function importDesktopModel(payload: ModelImportPayload) {
    setIsImporting(true);
    setDesktopLaunchError(null);
    setStatusMessage("Đang import model vào desktop project.");
    try {
      await api.demoLogin();
      const imported = await api.importModel(payload);
      const projectId = sanitizeProjectId(imported.scanSession.projectId ?? "");
      if (!projectId) {
        throw new Error("Ứng dụng chưa tạo được project từ model vừa import. Vui lòng thử lại.");
      }
      openDesktopProjectId(projectId);
    } catch (error) {
      const message = friendlyInlineMessage(messageFromError(error));
      setDesktopLaunchError(message);
      setStatusMessage(message);
    } finally {
      setIsImporting(false);
    }
  }

  const isDesktopEditorLayout = isDesktopShell && isProjectEditor && Boolean(user);

  return (
    <AppShell
      user={user}
      onLogout={logout}
      hideHeader={isDesktopEditorLayout}
      className={isDesktopEditorLayout ? "desktop-editor-shell" : ""}
    >
      <main className="workspace" id="main-workspace">
        {isDesktopShell && !isProjectEditor ? (
          <div className="desktop-launcher-layout">
            {desktopApiMode === "local" ? (
              <DesktopRuntimePanel
                runtime={desktopRuntime}
                editorReadiness={editorReadiness}
                installProgress={installProgress}
                isLoading={isDesktopRuntimeLoading}
                errorMessage={desktopRuntimeError}
                onRefresh={refreshDesktopRuntime}
                onRestartBackend={restartDesktopRuntimeBackend}
                onInstallRenderer={installPreviewRenderer}
                onOpenDiagnostics={openDesktopDiagnostics}
                onCopyDiagnostics={copyDesktopDiagnostics}
              />
            ) : (
              <CloudConnectionPanel
                apiBaseUrl={DESKTOP_CLOUD_API_BASE_URL}
                isReady={desktopCloudReady}
                user={user}
                errorMessage={desktopRuntimeError}
                onLogout={logout}
              />
            )}
            <div className="desktop-launcher-stack">
              <DesktopApiModeSelector
                value={desktopApiMode}
                onChange={changeDesktopApiMode}
              />
              {desktopApiMode === "cloud" ? (
                !desktopCloudReady ? (
                  <EditorRouteState state="ERROR" message={desktopRuntimeError ?? "Cloud API is not configured."} />
                ) : !user ? (
                  <AuthPanel
                    mode={authMode}
                    name={authName}
                    email={authEmail}
                    password={authPassword}
                    isBusy={isAuthBusy}
                    statusMessage={friendlyInlineMessage(statusMessage)}
                    onModeChange={setAuthMode}
                    onNameChange={setAuthName}
                    onEmailChange={setAuthEmail}
                    onPasswordChange={setAuthPassword}
                    onSubmit={submitAuth}
                    onDemoAuth={useDemoAuth}
                    showDemo={false}
                  />
                ) : (
                  <CloudProjectLauncher
                    projects={cloudProjects}
                    isLoading={isCloudProjectsLoading}
                    errorMessage={desktopLaunchError}
                    onRefresh={loadCloudProjects}
                    onOpen={(projectId) => openDesktopProjectId(projectId)}
                  />
                )
              ) : (
                <>
                  <DesktopProjectLauncher
                    value={desktopProjectInput}
                    errorMessage={desktopLaunchError}
                    demoProjectId={DESKTOP_DEMO_PROJECT_ID}
                    isDemoOpening={isDesktopDemoOpening}
                    isImportOpen={isDesktopImportOpen}
                    backendReady={desktopRuntimeReady}
                    onValueChange={(value) => {
                      setDesktopProjectInput(value);
                      setDesktopLaunchError(null);
                    }}
                    onSubmit={openDesktopProject}
                    onOpenDemo={openDesktopDemoProject}
                    onToggleImport={() => setIsDesktopImportOpen((current) => !current)}
                  />
                  {isDesktopImportOpen ? (
                    <section className="desktop-import-card">
                      {canUsePreviewRenderer ? (
                        <ModelImportPanel
                          isBusy={isImporting || !desktopRuntimeReady}
                          onImport={importDesktopModel}
                        />
                      ) : (
                        <div className="desktop-import-blocked">
                          <Wrench size={20} aria-hidden="true" />
                          <div>
                            <h2>Preview renderer cần cài đặt</h2>
                            <p>
                              Import GLB/OBJ cần renderer local để chuẩn hóa model trước khi mở trong editor.
                              Bạn vẫn có thể mở demo project để review giao diện trước.
                            </p>
                          </div>
                          <button type="button" className="primary-button" onClick={installPreviewRenderer}>
                            <Wrench size={16} aria-hidden="true" />
                            Cài Preview renderer
                          </button>
                        </div>
                      )}
                    </section>
                  ) : null}
                </>
              )}
            </div>
          </div>
        ) : isProjectEditor && !user ? (
          <EditorRouteState
            state={editorContext.state}
            message={friendlyInlineMessage(editorContext.errorMessage ?? "Redirecting to login.")}
          />
        ) : !user ? (
          <AuthPanel
            mode={authMode}
            name={authName}
            email={authEmail}
            password={authPassword}
            isBusy={isAuthBusy}
            statusMessage={friendlyInlineMessage(statusMessage)}
            onModeChange={setAuthMode}
            onNameChange={setAuthName}
            onEmailChange={setAuthEmail}
            onPasswordChange={setAuthPassword}
            onSubmit={submitAuth}
            onDemoAuth={useDemoAuth}
          />
        ) : isDesktopShell && isProjectEditor ? (
          <section className="desktop-customize-shell" aria-label="Customize shoe design">
            <header className="desktop-editor-topbar">
              <div className="desktop-brand-lockup" aria-label="KusShoes desktop">
                <img className="desktop-brand-logo" src="/logo.png" alt="KusShoes" />
                <nav className="desktop-brand-nav" aria-label="Desktop sections">
                  <span>Studio</span>
                  <span>Customize</span>
                  <span>Export</span>
                </nav>
              </div>
              <div className="desktop-project-title">
                <span className="studio-eyebrow">
                  <Monitor size={14} aria-hidden="true" />
                  Desktop Studio
                </span>
                <h1>{editorContext.context?.project.name ?? designName ?? "KusShoes project"}</h1>
              </div>
              <div className={`desktop-save-status ${desktopEditorStatusTone({
                isSaving,
                isBakingPreview,
                isExporting,
                isSaved,
                hasBakedPreview: Boolean(previewModelUrl),
                canUsePreviewRenderer,
                previewErrorMessage,
              })}`}>
                {desktopEditorStatusLabel({
                  isSaving,
                  isBakingPreview,
                  isExporting,
                  isSaved,
                  hasBakedPreview: Boolean(previewModelUrl),
                  canUsePreviewRenderer,
                  previewErrorMessage,
                })}
              </div>
              <div className="desktop-topbar-actions">
                <button
                  type="button"
                  disabled={isSaving || isBakingPreview || isExporting || !editorPermissions.canEdit}
                  onClick={saveDesign}
                >
                  <Save size={16} aria-hidden="true" />
                  Save Draft
                </button>
                <button
                  type="button"
                  disabled={
                    isSaving ||
                    isBakingPreview ||
                    isExporting ||
                    !editorPermissions.canEdit ||
                    !editorPermissions.canBake ||
                    !canUsePreviewRenderer
                  }
                  onClick={bakePreview}
                >
                  <Cpu size={16} aria-hidden="true" />
                  Bake Preview
                </button>
                <button
                  type="button"
                  className="primary-button"
                  disabled={isSaving || isBakingPreview || isExporting || !editorPermissions.canExport || !canUsePreviewRenderer}
                  onClick={exportDesign}
                >
                  <Download size={16} aria-hidden="true" />
                  Export
                </button>
                <button
                  type="button"
                  className="desktop-icon-button"
                  aria-label="Open project details and diagnostics"
                  onClick={() => setIsDesktopDetailsOpen(true)}
                >
                  <Settings size={17} aria-hidden="true" />
                </button>
              </div>
            </header>

            <div className="desktop-editor-body">
              <section className="desktop-stage" aria-label="3D design preview">
                <EditorStatusNotice message={statusMessage} isBusy={isEditorBusy} compact />
                <ModelViewer
                  modelUrl={activeModelUrl}
                  config={config}
                  activeLayerId={activeLayerId}
                  gizmoMode={gizmoMode}
                  hiddenLayerIds={hiddenLayerIds}
                  isSaving={isSaving || isBakingPreview}
                  savingMessage={isBakingPreview ? "Baking preview..." : "Saving draft..."}
                  previewErrorMessage={friendlyPreviewErrorMessage}
                  surfaceApplyRequest={surfaceApplyRequest}
                  onConfigChange={handleConfigChange}
                  onActiveLayerChange={setActiveLayerId}
                  onMeshBoundsUpdate={setMeshBounds}
                  onSurfaceApplyResult={setStatusMessage}
                />
              </section>
              <section className="desktop-tools-sidebar" aria-label="Design tools">
                <EditorPanels
                  config={config}
                  modelAsset={modelAsset}
                  designName={designName}
                  isSaving={isSaving}
                  isBakingPreview={isBakingPreview}
                  isExporting={isExporting}
                  canEdit={editorPermissions.canEdit}
                  canBake={editorPermissions.canBake && canUsePreviewRenderer}
                  canExport={editorPermissions.canExport && canUsePreviewRenderer}
                  exportMessage={friendlyExportMessage}
                  exportPackage={exportPackage}
                  activeLayerId={activeLayerId}
                  meshBounds={meshBounds}
                  gizmoMode={gizmoMode}
                  onNameChange={setDesignName}
                  onConfigChange={handleConfigChange}
                  onActiveLayerChange={setActiveLayerId}
                  onApplyActiveLayerToSurface={applyActiveLayerToSurface}
                  onGizmoModeChange={setGizmoMode}
                  onSave={saveDesign}
                  onBakePreview={bakePreview}
                  onExport={exportDesign}
                  onDownload={downloadExport}
                  onDownloadModelFile={downloadModelFile}
                  onUploadDesignAsset={uploadDesignAssetWithPreview}
                  simplified
                />
              </section>
            </div>

            <DesktopDetailsDrawer
              isOpen={isDesktopDetailsOpen}
              onClose={() => setIsDesktopDetailsOpen(false)}
              runtime={desktopRuntime}
              editorReadiness={editorReadiness}
              installProgress={installProgress}
              isLoading={isDesktopRuntimeLoading}
              errorMessage={desktopRuntimeError}
              scanSession={scanSession}
              modelAsset={modelAsset}
              config={config}
              designName={designName}
              activeLayerId={activeLayerId}
              meshBounds={meshBounds}
              isSaved={isSaved}
              hasBakedPreview={Boolean(previewModelUrl)}
              hasExportPackage={Boolean(exportPackage)}
              projectId={editorProjectId ?? ""}
              routeState={editorContext.state}
              permissions={editorPermissions}
              onRefresh={refreshDesktopRuntime}
              onRestartBackend={restartDesktopRuntimeBackend}
              onInstallRenderer={installPreviewRenderer}
              onOpenDiagnostics={openDesktopDiagnostics}
              onCopyDiagnostics={copyDesktopDiagnostics}
            />
          </section>
        ) : (
          <>
            <section className="toolbar-band">
              <div className="toolbar-stack">
                <div className="studio-command-header">
                  <span className="studio-eyebrow">
                    <Cpu size={14} aria-hidden="true" />
                    AI + 3D Sneaker Studio
                  </span>
                  <div>
                    <h2>{isProjectEditor ? editorContext.context?.project.name ?? "Kus Studio workspace" : "Kus Studio workspace"}</h2>
                    <p>
                      {isProjectEditor
                        ? "Customize the project model, save a backend draft, bake preview, then export."
                        : "Load a scan or import a model, then customize the shoe in the 3D stage."}
                    </p>
                  </div>
                </div>
                {isProjectEditor ? (
                  <ProjectRouteSummary
                    projectId={editorProjectId ?? ""}
                    state={editorContext.state}
                    canEdit={editorPermissions.canEdit}
                    canBake={editorPermissions.canBake}
                    canExport={editorPermissions.canExport}
                  />
                ) : (
                  <>
                    <div className="scan-loader">
                      <label>
                        Scan session ID
                        <input
                          value={scanId}
                          onChange={(event) => setScanId(event.target.value)}
                          placeholder="scan_..."
                        />
                      </label>
                      <button type="button" disabled={!canLoad} onClick={loadScan}>
                        <Search size={16} aria-hidden="true" />
                        Load
                      </button>
                      <button type="button" disabled={!scanSession} onClick={loadScan}>
                        <RefreshCw size={16} aria-hidden="true" />
                        Refresh
                      </button>
                    </div>
                    <ModelImportPanel isBusy={isImporting} onImport={importModel} />
                  </>
                )}
              </div>
            </section>

            <EditorStatusNotice message={statusMessage} isBusy={isEditorBusy} />

            {isDesktopShell && (
              <DesktopRuntimePanel
                runtime={desktopRuntime}
                editorReadiness={editorReadiness}
                installProgress={installProgress}
                isLoading={isDesktopRuntimeLoading}
                errorMessage={desktopRuntimeError}
                onRefresh={refreshDesktopRuntime}
                onRestartBackend={restartDesktopRuntimeBackend}
                onInstallRenderer={installPreviewRenderer}
                onOpenDiagnostics={openDesktopDiagnostics}
                onCopyDiagnostics={copyDesktopDiagnostics}
              />
            )}

            <section className="main-grid">
              <MetadataPanel
                scanSession={scanSession}
                modelAsset={modelAsset}
                config={config}
                designName={designName}
                activeLayerId={activeLayerId}
                meshBounds={meshBounds}
                isSaved={isSaved}
                hasBakedPreview={Boolean(previewModelUrl)}
                hasExportPackage={Boolean(exportPackage)}
              />
              <ModelViewer
                modelUrl={activeModelUrl}
                config={config}
                activeLayerId={activeLayerId}
                gizmoMode={gizmoMode}
                hiddenLayerIds={hiddenLayerIds}
                isSaving={isSaving || isBakingPreview}
                savingMessage={isBakingPreview ? "Đang bake preview..." : "Đang lưu draft..."}
                previewErrorMessage={friendlyPreviewErrorMessage}
                surfaceApplyRequest={surfaceApplyRequest}
                onConfigChange={handleConfigChange}
                onActiveLayerChange={setActiveLayerId}
                onMeshBoundsUpdate={setMeshBounds}
                onSurfaceApplyResult={setStatusMessage}
              />
              <EditorPanels
                config={config}
                modelAsset={modelAsset}
                designName={designName}
                isSaving={isSaving}
                isBakingPreview={isBakingPreview}
                isExporting={isExporting}
                canEdit={!isProjectEditor || editorPermissions.canEdit}
                canBake={(!isProjectEditor || editorPermissions.canBake) && canUsePreviewRenderer}
                canExport={(!isProjectEditor || editorPermissions.canExport) && canUsePreviewRenderer}
                exportMessage={friendlyExportMessage}
                exportPackage={exportPackage}
                activeLayerId={activeLayerId}
                meshBounds={meshBounds}
                gizmoMode={gizmoMode}
                onNameChange={setDesignName}
                onConfigChange={handleConfigChange}
                onActiveLayerChange={setActiveLayerId}
                onApplyActiveLayerToSurface={applyActiveLayerToSurface}
                onGizmoModeChange={setGizmoMode}
                onSave={saveDesign}
                onBakePreview={bakePreview}
                onExport={exportDesign}
                onDownload={downloadExport}
                onDownloadModelFile={downloadModelFile}
                onUploadDesignAsset={uploadDesignAssetWithPreview}
              />
            </section>
          </>
        )}
      </main>
    </AppShell>
  );
}

function EditorRouteState({ state, message }: { state: string; message: string }) {
  return (
    <section className="auth-panel">
      <div className="empty-panel-callout">
        <RefreshCw size={22} aria-hidden="true" />
        <div>
          <h2>{editorRouteStateLabel(state)}</h2>
          <p>{message}</p>
        </div>
      </div>
    </section>
  );
}

function EditorStatusNotice({ message, isBusy, compact = false }: { message: string; isBusy: boolean; compact?: boolean }) {
  const notice = noticeFromStatus(message, isBusy);
  const role = notice.tone === "error" ? "alert" : "status";
  const ariaLive = notice.tone === "error" ? "assertive" : "polite";

  return (
    <section className={`editor-status-notice ${notice.tone} ${compact ? "compact" : ""}`} role={role} aria-live={ariaLive}>
      <span className="editor-status-icon">
        {notice.tone === "loading" ? (
          <Loader2 size={20} aria-hidden="true" />
        ) : notice.tone === "success" ? (
          <CheckCircle2 size={20} aria-hidden="true" />
        ) : notice.tone === "warning" || notice.tone === "error" ? (
          <AlertTriangle size={20} aria-hidden="true" />
        ) : (
          <Info size={20} aria-hidden="true" />
        )}
      </span>
      <div className="editor-status-copy">
        <h2>{notice.title}</h2>
        <p>{notice.detail}</p>
      </div>
    </section>
  );
}

function ProjectRouteSummary({
  projectId,
  state,
  canEdit,
  canBake,
  canExport,
}: {
  projectId: string;
  state: string;
  canEdit: boolean;
  canBake: boolean;
  canExport: boolean;
}) {
  return (
    <div className="scan-loader">
      <label>
        Project ID
        <input value={projectId} readOnly />
      </label>
      <span className="status-line">{editorRouteStateLabel(state)}</span>
      <span className="status-line">
        {canEdit ? "Edit" : "View"} / {canBake ? "Bake" : "No bake"} / {canExport ? "Export" : "No export"}
      </span>
    </div>
  );
}

type DesktopRuntimePanelProps = {
  runtime: DesktopRuntime | null;
  editorReadiness: EditorReadiness | null;
  installProgress: InstallProgress | null;
  isLoading: boolean;
  errorMessage: string | null;
  onRefresh: () => void;
  onRestartBackend: () => void;
  onInstallRenderer: () => void;
  onOpenDiagnostics: () => void;
  onCopyDiagnostics: () => void;
};

function DesktopRuntimePanel({
  runtime,
  editorReadiness,
  installProgress,
  isLoading,
  errorMessage,
  onRefresh,
  onRestartBackend,
  onInstallRenderer,
  onOpenDiagnostics,
  onCopyDiagnostics,
}: DesktopRuntimePanelProps) {
  const backendStatus = runtime?.backendStatus ?? (isLoading ? "starting" : "failed");
  const rendererStatus =
    editorReadiness?.previewRenderer.available || runtime?.blenderStatus === "installed"
      ? "installed"
      : installProgress?.status === "downloading"
        ? "downloading"
        : runtime?.blenderStatus ?? "missing";
  const demoStatus = runtime?.demoProjectStatus ?? "missing";
  const rendererMessage =
    installProgress?.message ??
    friendlyRendererMessage(editorReadiness, runtime);

  return (
    <section className="desktop-runtime-panel" aria-label="Desktop editor readiness">
      <div className="desktop-runtime-header">
        <div>
          <span className="studio-eyebrow">
            <Monitor size={14} aria-hidden="true" />
            Desktop beta runtime
          </span>
          <h2>Editor readiness</h2>
          <p>
            Desktop beta tập trung vào mở model, đặt sticker/text, bake preview và export.
            Scan-to-3D không chạy trong bản này.
          </p>
        </div>
        <div className="desktop-runtime-actions">
          <button type="button" onClick={onRefresh} disabled={isLoading}>
            <RefreshCw size={16} aria-hidden="true" />
            Refresh
          </button>
          <button type="button" onClick={onOpenDiagnostics}>
            <Wrench size={16} aria-hidden="true" />
            Logs
          </button>
          <button type="button" onClick={onCopyDiagnostics}>
            <Info size={16} aria-hidden="true" />
            Copy diagnostics
          </button>
        </div>
      </div>

      <div className="desktop-runtime-grid">
        <RuntimeStatusItem
          title="Local backend"
          status={backendStatus}
          detail={
            backendStatus === "ready"
              ? `Ready at ${runtime?.apiBaseUrl ?? "local API"}`
              : errorMessage ?? "Ứng dụng đang khởi động backend local."
          }
          actionLabel={backendStatus === "ready" ? undefined : "Restart backend"}
          onAction={backendStatus === "ready" ? undefined : onRestartBackend}
        />
        <RuntimeStatusItem
          title="Preview renderer"
          status={rendererStatus}
          detail={rendererMessage}
          actionLabel={rendererStatus === "installed" ? undefined : "Install renderer"}
          onAction={rendererStatus === "installed" ? undefined : onInstallRenderer}
        />
        <RuntimeStatusItem
          title="Demo project"
          status={demoStatus}
          detail={
            demoStatus === "ready"
              ? "Demo project is ready for review."
              : "Ứng dụng sẽ seed demo project khi backend local sẵn sàng."
          }
        />
      </div>
    </section>
  );
}

function RuntimeStatusItem({
  title,
  status,
  detail,
  actionLabel,
  onAction,
}: {
  title: string;
  status: string;
  detail: string;
  actionLabel?: string;
  onAction?: () => void;
}) {
  const tone =
    status === "ready" || status === "installed"
      ? "ready"
      : status === "starting" || status === "downloading"
        ? "working"
        : "blocked";
  return (
    <div className={`runtime-status-item ${tone}`}>
      <div className="runtime-status-title">
        {tone === "ready" ? <CheckCircle2 size={18} aria-hidden="true" /> : <AlertTriangle size={18} aria-hidden="true" />}
        <div>
          <strong>{title}</strong>
          <span>{runtimeStatusLabel(status)}</span>
        </div>
      </div>
      <p>{detail}</p>
      {actionLabel && onAction ? (
        <button type="button" onClick={onAction}>
          {actionLabel}
        </button>
      ) : null}
    </div>
  );
}

type DesktopDetailsDrawerProps = {
  isOpen: boolean;
  onClose: () => void;
  runtime: DesktopRuntime | null;
  editorReadiness: EditorReadiness | null;
  installProgress: InstallProgress | null;
  isLoading: boolean;
  errorMessage: string | null;
  scanSession: ScanSession | null;
  modelAsset: ModelAsset | null;
  config: DesignConfig | null;
  designName: string;
  activeLayerId: string | null;
  meshBounds: { center: [number, number, number]; size: [number, number, number] } | null;
  isSaved: boolean;
  hasBakedPreview: boolean;
  hasExportPackage: boolean;
  projectId: string;
  routeState: string;
  permissions: EditorPermissions;
  onRefresh: () => void;
  onRestartBackend: () => void;
  onInstallRenderer: () => void;
  onOpenDiagnostics: () => void;
  onCopyDiagnostics: () => void;
};

function DesktopDetailsDrawer({
  isOpen,
  onClose,
  runtime,
  editorReadiness,
  installProgress,
  isLoading,
  errorMessage,
  scanSession,
  modelAsset,
  config,
  designName,
  activeLayerId,
  meshBounds,
  isSaved,
  hasBakedPreview,
  hasExportPackage,
  projectId,
  routeState,
  permissions,
  onRefresh,
  onRestartBackend,
  onInstallRenderer,
  onOpenDiagnostics,
  onCopyDiagnostics,
}: DesktopDetailsDrawerProps) {
  if (!isOpen) {
    return null;
  }

  return (
    <div className="desktop-details-overlay" role="presentation" onMouseDown={onClose}>
      <aside
        className="desktop-details-drawer"
        role="dialog"
        aria-modal="true"
        aria-label="Project details and diagnostics"
        onMouseDown={(event) => event.stopPropagation()}
      >
        <header className="desktop-details-header">
          <div>
            <span className="studio-eyebrow">
              <Info size={14} aria-hidden="true" />
              Project Details
            </span>
            <h2>{designName || "Untitled design"}</h2>
          </div>
          <button type="button" className="desktop-icon-button" aria-label="Close details" onClick={onClose}>
            <X size={18} aria-hidden="true" />
          </button>
        </header>

        <div className="desktop-details-content">
          <ProjectRouteSummary
            projectId={projectId}
            state={routeState}
            canEdit={permissions.canEdit}
            canBake={permissions.canBake}
            canExport={permissions.canExport}
          />
          <MetadataPanel
            scanSession={scanSession}
            modelAsset={modelAsset}
            config={config}
            designName={designName}
            activeLayerId={activeLayerId}
            meshBounds={meshBounds}
            isSaved={isSaved}
            hasBakedPreview={hasBakedPreview}
            hasExportPackage={hasExportPackage}
          />
          <DesktopRuntimePanel
            runtime={runtime}
            editorReadiness={editorReadiness}
            installProgress={installProgress}
            isLoading={isLoading}
            errorMessage={errorMessage}
            onRefresh={onRefresh}
            onRestartBackend={onRestartBackend}
            onInstallRenderer={onInstallRenderer}
            onOpenDiagnostics={onOpenDiagnostics}
            onCopyDiagnostics={onCopyDiagnostics}
          />
        </div>
      </aside>
    </div>
  );
}

function DesktopApiModeSelector({
  value,
  onChange,
}: {
  value: DesktopApiMode;
  onChange: (mode: DesktopApiMode) => void;
}) {
  return (
    <div className="desktop-api-mode" role="tablist" aria-label="Desktop data source">
      <button
        type="button"
        role="tab"
        aria-selected={value === "local"}
        className={value === "local" ? "active" : ""}
        onClick={() => onChange("local")}
      >
        <HardDrive size={16} aria-hidden="true" />
        Local
      </button>
      <button
        type="button"
        role="tab"
        aria-selected={value === "cloud"}
        className={value === "cloud" ? "active" : ""}
        onClick={() => onChange("cloud")}
      >
        <Cloud size={16} aria-hidden="true" />
        Cloud
      </button>
    </div>
  );
}

function CloudConnectionPanel({
  apiBaseUrl,
  isReady,
  user,
  errorMessage,
  onLogout,
}: {
  apiBaseUrl: string;
  isReady: boolean;
  user: User | null;
  errorMessage: string | null;
  onLogout: () => void;
}) {
  return (
    <section className="desktop-runtime-panel">
      <div className="desktop-launcher-title">
        <span className="desktop-launcher-icon"><Cloud size={22} aria-hidden="true" /></span>
        <div>
          <h2>Cloud workspace</h2>
          <p className="desktop-cloud-endpoint">{apiBaseUrl || "Not configured"}</p>
        </div>
      </div>
      <span className={`status-line ${isReady ? "success-text" : "danger-text"}`}>
        {isReady ? "Cloud API ready" : errorMessage ?? "Cloud API unavailable"}
      </span>
      {user ? (
        <div className="desktop-cloud-account">
          <span>{user.name}</span>
          <small>{user.email}</small>
          <button type="button" onClick={onLogout}>Sign out</button>
        </div>
      ) : null}
    </section>
  );
}

function CloudProjectLauncher({
  projects,
  isLoading,
  errorMessage,
  onRefresh,
  onOpen,
}: {
  projects: CloudProject[];
  isLoading: boolean;
  errorMessage: string | null;
  onRefresh: () => void;
  onOpen: (projectId: string) => void;
}) {
  return (
    <section className="auth-form desktop-launcher desktop-cloud-projects">
      <header className="desktop-cloud-projects-header">
        <div>
          <h2>Cloud projects</h2>
          <span>{projects.length} projects</span>
        </div>
        <button type="button" className="desktop-icon-button" aria-label="Refresh projects" onClick={onRefresh}>
          <RefreshCw size={17} className={isLoading ? "spin" : ""} aria-hidden="true" />
        </button>
      </header>
      <div className="desktop-cloud-project-list">
        {projects.map((project) => (
          <div className="desktop-cloud-project-row" key={project.id}>
            <FolderOpen size={18} aria-hidden="true" />
            <div>
              <strong>{project.name}</strong>
              <span>{project.status.replaceAll("_", " ")}</span>
            </div>
            <button
              type="button"
              className="desktop-icon-button"
              aria-label={`Open ${project.name}`}
              disabled={project.status !== "ready"}
              onClick={() => onOpen(project.id)}
            >
              <Monitor size={17} aria-hidden="true" />
            </button>
          </div>
        ))}
        {!isLoading && projects.length === 0 ? <span className="status-line">No cloud projects yet.</span> : null}
      </div>
      {errorMessage ? <span className="status-line danger-text">{errorMessage}</span> : null}
    </section>
  );
}

type DesktopProjectLauncherProps = {
  value: string;
  errorMessage: string | null;
  demoProjectId: string;
  isDemoOpening: boolean;
  isImportOpen: boolean;
  backendReady: boolean;
  onValueChange: (value: string) => void;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
  onOpenDemo: () => void;
  onToggleImport: () => void;
};

function DesktopProjectLauncher({
  value,
  errorMessage,
  demoProjectId,
  isDemoOpening,
  isImportOpen,
  backendReady,
  onValueChange,
  onSubmit,
  onOpenDemo,
  onToggleImport,
}: DesktopProjectLauncherProps) {
  const hasDemoProject = Boolean(sanitizeProjectId(demoProjectId));

  return (
    <section className="auth-panel">
      <form className="auth-form desktop-launcher" onSubmit={onSubmit}>
        <div className="desktop-launcher-title">
          <span className="desktop-launcher-icon">
            <Monitor size={22} aria-hidden="true" />
          </span>
          <div>
            <h2>KusShoes Desktop Editor</h2>
            <p>Mở demo project hoặc dán project URL. Ứng dụng tự quản lý backend local cho tester beta.</p>
          </div>
        </div>
        <label>
          Project ID hoặc editor URL
          <input
            value={value}
            onChange={(event) => onValueChange(event.target.value)}
            placeholder="proj_... or https://.../editor/proj_..."
            autoFocus
          />
        </label>
        <button type="submit" className="primary-button" disabled={!backendReady}>
          <Monitor size={16} aria-hidden="true" />
          Mở editor
        </button>
        {hasDemoProject ? (
          <button type="button" disabled={isDemoOpening || !backendReady} onClick={onOpenDemo}>
            <LogIn size={16} aria-hidden="true" />
            {isDemoOpening ? "Đang mở demo" : "Mở demo project"}
          </button>
        ) : null}
        <button type="button" disabled={!backendReady} onClick={onToggleImport}>
          <ImagePlus size={16} aria-hidden="true" />
          {isImportOpen ? "Ẩn import" : "Import GLB/OBJ"}
        </button>
        {errorMessage ? <span className="status-line danger-text">{errorMessage}</span> : null}
      </form>
    </section>
  );
}


type AuthPanelProps = {
  mode: "login" | "register";
  name: string;
  email: string;
  password: string;
  isBusy: boolean;
  statusMessage: string;
  onModeChange: (mode: "login" | "register") => void;
  onNameChange: (value: string) => void;
  onEmailChange: (value: string) => void;
  onPasswordChange: (value: string) => void;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
  onDemoAuth: () => void;
  showDemo?: boolean;
};

function AuthPanel({
  mode,
  name,
  email,
  password,
  isBusy,
  statusMessage,
  onModeChange,
  onNameChange,
  onEmailChange,
  onPasswordChange,
  onSubmit,
  onDemoAuth,
  showDemo = true,
}: AuthPanelProps) {
  return (
    <section className="auth-panel">
      <form className="auth-form" onSubmit={onSubmit}>
        <div className="auth-tabs" role="tablist" aria-label="Authentication mode">
          <button type="button" className={mode === "login" ? "active" : ""} onClick={() => onModeChange("login")}>
            <LogIn size={16} aria-hidden="true" />
            Login
          </button>
          <button
            type="button"
            className={mode === "register" ? "active" : ""}
            onClick={() => onModeChange("register")}
          >
            <UserPlus size={16} aria-hidden="true" />
            Register
          </button>
        </div>

        {mode === "register" ? (
          <label>
            Name
            <input value={name} onChange={(event) => onNameChange(event.target.value)} required minLength={1} />
          </label>
        ) : null}

        <label>
          Email
          <input type="email" value={email} onChange={(event) => onEmailChange(event.target.value)} required />
        </label>
        <label>
          Password
          <input
            type="password"
            value={password}
            onChange={(event) => onPasswordChange(event.target.value)}
            required
            minLength={mode === "register" ? 8 : 1}
          />
        </label>

        <div className="button-row">
          <button type="submit" className="primary-button" disabled={isBusy}>
            {mode === "login" ? <LogIn size={16} aria-hidden="true" /> : <UserPlus size={16} aria-hidden="true" />}
            {mode === "login" ? "Login" : "Create account"}
          </button>
          {showDemo ? (
            <button type="button" disabled={isBusy} onClick={onDemoAuth}>
              Demo
            </button>
          ) : null}
        </div>
        <span className="status-line">{statusMessage}</span>
      </form>
    </section>
  );
}

async function prepareBakeConfig(config: DesignConfig): Promise<DesignConfig> {
  const persistable = persistableConfig(config);
  const stickers = await Promise.all(
    persistable.stickers.map(async (sticker) => {
      if (sticker.assetId) {
        return sticker;
      }
      return {
        ...sticker,
        imageUrl: sticker.imageUrl ? await rasterizeSvgDataUriToPng(sticker.imageUrl) : sticker.imageUrl,
      };
    }),
  );
  const texts = await Promise.all(
    persistable.texts.map(async (textLayer) => ({
      ...textLayer,
      renderAssetId: await uploadRenderedTextLayer(textLayer),
    })),
  );
  return { ...persistable, stickers, texts };
}

async function rasterizeSvgDataUriToPng(imageUrl: string): Promise<string> {
  if (!isSvgDataUri(imageUrl)) {
    return imageUrl;
  }

  try {
    const image = await loadImage(imageUrl);
    const width = clampInt(image.naturalWidth || image.width || 512, 1, 1024);
    const height = clampInt(image.naturalHeight || image.height || 512, 1, 1024);
    const canvas = document.createElement("canvas");
    canvas.width = width;
    canvas.height = height;
    const context = canvas.getContext("2d");
    if (!context) {
      return imageUrl;
    }
    context.clearRect(0, 0, width, height);
    context.drawImage(image, 0, 0, width, height);
    return canvas.toDataURL("image/png");
  } catch {
    return imageUrl;
  }
}

function isSvgDataUri(imageUrl: string): boolean {
  return /^data:image\/svg\+xml/i.test(imageUrl.trim());
}

function loadImage(src: string): Promise<HTMLImageElement> {
  return new Promise((resolve, reject) => {
    const image = new Image();
    image.onload = () => resolve(image);
    image.onerror = () => reject(new Error("Sticker SVG could not be rasterized."));
    image.src = src;
  });
}

function clampInt(value: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, Math.round(value)));
}

async function uploadRenderedTextLayer(layer: TextLayer): Promise<string | undefined> {
  if (!layer.value.trim()) {
    return undefined;
  }
  const file = await renderTextLayerToPngFile(layer);
  const asset = await api.uploadDesignAsset(file, "text-render");
  return asset.id;
}

async function renderTextLayerToPngFile(layer: TextLayer): Promise<File> {
  const aspect = textAspect(layer.value);
  const width = clampInt(512 * aspect, 512, 4096);
  const height = 512;
  const canvas = document.createElement("canvas");
  canvas.width = width;
  canvas.height = height;
  const context = canvas.getContext("2d");
  if (!context) {
    throw new Error("Text render failed.");
  }

  const fontFamily = cssFontFamily(layer.font || "Arial");
  if (document.fonts?.load) {
    await document.fonts.load(`700 300px ${fontFamily}`);
  }

  context.clearRect(0, 0, width, height);
  context.fillStyle = safeTextColor(layer.color);
  context.textAlign = "center";
  context.textBaseline = "middle";

  let fontSize = 300;
  do {
    context.font = `700 ${fontSize}px ${fontFamily}`;
    if (context.measureText(layer.value).width <= width * 0.9 || fontSize <= 72) {
      break;
    }
    fontSize -= 12;
  } while (fontSize > 72);

  context.fillText(layer.value, width / 2, height / 2);
  const blob = await new Promise<Blob>((resolve, reject) => {
    canvas.toBlob((value) => (value ? resolve(value) : reject(new Error("Text render export failed."))), "image/png");
  });
  return new File([blob], `${layer.id || "text"}-${Date.now()}.png`, { type: "image/png" });
}

function textAspect(value: string): number {
  return Math.max(value.trim().length * 0.62, 1);
}

function cssFontFamily(value: string): string {
  const cleaned = value.replace(/["\\]/g, "").trim() || "Arial";
  return `"${cleaned}", sans-serif`;
}

function safeTextColor(value: string): string {
  return /^#[0-9A-Fa-f]{6}$/.test(value) ? value : "#ffffff";
}

function layerIds(config: DesignConfig): string[] {
  return [...config.stickers.map((sticker) => sticker.id), ...config.texts.map((text) => text.id)];
}

function configFingerprint(config: DesignConfig): string {
  return JSON.stringify(persistableConfig(config));
}

function canKeepBakedPreview(
  previousConfig: DesignConfig,
  nextConfig: DesignConfig,
  bakedLayerIds: string[],
): boolean {
  if (
    previousConfig.baseColor !== nextConfig.baseColor ||
    JSON.stringify(previousConfig.material) !== JSON.stringify(nextConfig.material)
  ) {
    return false;
  }

  for (const layerId of bakedLayerIds) {
    const previousLayer = findLayer(previousConfig, layerId);
    const nextLayer = findLayer(nextConfig, layerId);
    if (
      !previousLayer ||
      !nextLayer ||
      JSON.stringify(stripRuntimeLayer(previousLayer)) !== JSON.stringify(stripRuntimeLayer(nextLayer))
    ) {
      return false;
    }
  }
  return true;
}

function findLayer(config: DesignConfig, layerId: string) {
  return config.stickers.find((sticker) => sticker.id === layerId) ?? config.texts.find((text) => text.id === layerId);
}

function persistableConfig(config: DesignConfig): DesignConfig {
  const fixedConfig = normalizeFixedMaterial(config);
  return {
    ...fixedConfig,
    stickers: fixedConfig.stickers.map((sticker) => {
      const { previewUrl: _previewUrl, ...persistableSticker } = sticker;
      return persistableSticker;
    }),
  };
}

function stripRuntimeLayer(layer: ReturnType<typeof findLayer>) {
  if (!layer || !("type" in layer)) {
    return layer;
  }
  const { previewUrl: _previewUrl, ...persistableLayer } = layer;
  return persistableLayer;
}

function createDefaultConfig(modelAssetId: string): DesignConfig {
  return {
    modelAssetId,
    baseColor: FIXED_BASE_COLOR,
    material: {
      ...FIXED_MATERIAL,
    },
    stickers: [],
    texts: [],
    camera: {},
    metadata: {
      editorVersion: "1.0.0",
    },
  };
}

function withEditorMetadata(config: DesignConfig): DesignConfig {
  return {
    ...config,
    metadata: {
      ...(config.metadata ?? {}),
      editorVersion: "1.0.0",
    },
  };
}

const FIXED_BASE_COLOR = "#ffffff";
const FIXED_MATERIAL = {
  roughness: 1,
  metallic: 0,
};

function normalizeFixedMaterial(config: DesignConfig): DesignConfig {
  return {
    ...config,
    baseColor: FIXED_BASE_COLOR,
    material: { ...FIXED_MATERIAL },
  };
}

function setScanIdInUrl(scanSessionId: string) {
  const url = new URL(window.location.href);
  url.searchParams.set("scanId", scanSessionId);
  window.history.replaceState({}, "", url);
}

function projectIdFromEditorPath(pathname: string): string | null {
  const match = pathname.match(/^\/editor\/([^/?#]+)/);
  return match ? decodeURIComponent(match[1]) : null;
}

function editorProjectIdFromLocation(isDesktopShell: boolean): string | null {
  const pathProjectId = projectIdFromEditorPath(window.location.pathname);
  if (pathProjectId) {
    return pathProjectId;
  }
  if (!isDesktopShell) {
    return null;
  }
  const queryProjectId = new URLSearchParams(window.location.search).get("projectId");
  return queryProjectId ? sanitizeProjectId(queryProjectId) : null;
}

function isDesktopShellLocation(): boolean {
  const params = new URLSearchParams(window.location.search);
  return params.get("desktop") === "1" || import.meta.env.VITE_DESKTOP_SHELL === "true";
}

function projectIdFromEditorInput(value: string): string | null {
  const trimmed = value.trim();
  if (!trimmed) {
    return null;
  }

  try {
    const parsedUrl = new URL(trimmed);
    const routeProjectId = projectIdFromEditorPath(parsedUrl.pathname);
    if (routeProjectId) {
      return sanitizeProjectId(routeProjectId);
    }
    const customProtocolProjectId = projectIdFromEditorPath(`/${parsedUrl.host}${parsedUrl.pathname}`);
    if (customProtocolProjectId) {
      return sanitizeProjectId(customProtocolProjectId);
    }
  } catch {
    // Treat non-URL input as either a route fragment or a raw project id.
  }

  const routeProjectId = projectIdFromEditorPath(trimmed.startsWith("/") ? trimmed : `/${trimmed}`);
  if (routeProjectId) {
    return sanitizeProjectId(routeProjectId);
  }
  return sanitizeProjectId(trimmed);
}

function openDesktopProjectId(projectId: string): void {
  const url = new URL(window.location.href);
  url.searchParams.set("desktop", "1");
  url.searchParams.set("projectId", projectId);
  url.hash = "";
  window.location.assign(url.toString());
}

function sanitizeProjectId(value: string): string | null {
  const projectId = value.trim();
  return /^[A-Za-z0-9_-]{3,120}$/.test(projectId) ? projectId : null;
}

function loginRedirectUrl(): string {
  const url = new URL(MARKETING_LOGIN_URL);
  url.searchParams.set("redirect", window.location.href);
  return url.toString();
}

async function waitForBakeJob(jobId: string, getJob: (jobId: string) => Promise<Job>): Promise<Job> {
  for (let attempt = 0; attempt < 180; attempt += 1) {
    const job = await getJob(jobId);
    if (job.status === "completed" || job.status === "failed") {
      return job;
    }
    await delay(2000);
  }
  throw new Error("Bake job timed out.");
}

function delay(milliseconds: number): Promise<void> {
  return new Promise((resolve) => window.setTimeout(resolve, milliseconds));
}

function scanStatusLabel(status: string): string {
  const labels: Record<string, string> = {
    created: "Created",
    waiting_for_uploads: "Waiting for both shoe videos",
    uploaded: "Uploaded",
    queued: "Queued for reconstruction",
    toolchain_unavailable: "Reconstruction toolchain unavailable",
    extracting_frames: "Extracting frames",
    filtering_frames: "Filtering frames",
    preparing_reconstruction: "Preparing reconstruction",
    reconstructing: "Reconstructing mesh",
    cleaning_mesh: "Cleaning mesh",
    uv_unwrapping: "Preparing UVs",
    texture_baking: "Baking texture",
    exporting: "Exporting model files",
    kiri_processing: "Processing with Kiri Engine",
    kiri_ready: "Ready for crop",
    crop_baking: "Applying crop",
    crop_ready: "Cloud model ready",
    completed: "Completed",
    failed: "Failed",
  };
  return labels[status] ?? status;
}

function formatResource(resource: { available: number | null; required: number; unit: string } | undefined): string {
  if (!resource || resource.available === null) {
    return "unknown";
  }
  return `${resource.available.toFixed(1)}/${resource.required.toFixed(1)} ${resource.unit}`;
}

type DesktopEditorStatusInput = {
  isSaving: boolean;
  isBakingPreview: boolean;
  isExporting: boolean;
  isSaved: boolean;
  hasBakedPreview: boolean;
  canUsePreviewRenderer: boolean;
  previewErrorMessage: string | null;
};

function desktopEditorStatusLabel(status: DesktopEditorStatusInput): string {
  if (status.isSaving) {
    return "Saving...";
  }
  if (status.isBakingPreview) {
    return "Baking preview...";
  }
  if (status.isExporting) {
    return "Exporting...";
  }
  if (!status.canUsePreviewRenderer) {
    return "Renderer needs setup";
  }
  if (status.previewErrorMessage) {
    return "Preview needs attention";
  }
  if (status.hasBakedPreview) {
    return "Preview ready";
  }
  if (status.isSaved) {
    return "Draft saved";
  }
  return "Unsaved changes";
}

function desktopEditorStatusTone(status: DesktopEditorStatusInput): "ready" | "working" | "warning" | "neutral" {
  if (status.isSaving || status.isBakingPreview || status.isExporting) {
    return "working";
  }
  if (!status.canUsePreviewRenderer || status.previewErrorMessage) {
    return "warning";
  }
  if (status.hasBakedPreview || status.isSaved) {
    return "ready";
  }
  return "neutral";
}

function friendlyRendererMessage(editorReadiness: EditorReadiness | null, runtime: DesktopRuntime | null): string {
  if (editorReadiness?.previewRenderer.available || runtime?.blenderStatus === "installed") {
    return "Preview renderer đã sẵn sàng để bake preview và export.";
  }
  if (runtime?.blenderStatus === "failed" || editorReadiness?.previewRenderer.status === "failed") {
    return "Ứng dụng chưa chuẩn bị được Preview renderer. Vui lòng thử cài lại hoặc mở Logs để gửi diagnostics cho team.";
  }
  return "Preview renderer cần cài đặt để bake preview, import GLB/OBJ và export. Save Draft vẫn hoạt động khi renderer chưa sẵn sàng.";
}

function runtimeStatusLabel(status: string): string {
  const labels: Record<string, string> = {
    ready: "Ready",
    installed: "Installed",
    starting: "Starting",
    downloading: "Installing",
    missing: "Needs setup",
    failed: "Needs attention",
    repairing: "Repairing",
  };
  return labels[status] ?? status;
}
