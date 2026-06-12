import {
  AlertTriangle,
  CheckCircle2,
  Cpu,
  HardDrive,
  ImagePlus,
  LogIn,
  MousePointer2,
  RefreshCw,
  Save,
  Search,
  UserPlus,
  Wrench,
} from "lucide-react";
import { FormEvent, useEffect, useMemo, useRef, useState } from "react";

import { api, ApiError, designStorageKey } from "./api/client";
import type { ModelImportPayload } from "./api/client";
import { editorClient } from "./api/editorClient";
import { EditorPanels } from "./components/Editor/EditorPanels";
import { AppShell } from "./components/Layout/AppShell";
import { MetadataPanel } from "./components/MetadataPanel/MetadataPanel";
import { ModelImportPanel } from "./components/ModelImport/ModelImportPanel";
import { ModelViewer } from "./components/ModelViewer/ModelViewer";
import { useEditorContext } from "./hooks/useEditorContext";
import type {
  Design,
  DesignAssetSource,
  DesignConfig,
  EditorContext,
  EditorPermissions,
  ExportPackage,
  Job,
  ModelAsset,
  ReconstructionReadiness,
  ScanSession,
  TextLayer,
  User,
} from "./types";

const MARKETING_LOGIN_URL = import.meta.env.VITE_MARKETING_LOGIN_URL ?? "https://kusshoes.vn/login";
const DEFAULT_EDITOR_PERMISSIONS: EditorPermissions = { canEdit: true, canBake: true, canExport: true };

export function App() {
  const editorProjectId = useMemo(() => projectIdFromEditorPath(window.location.pathname), []);
  const isProjectEditor = Boolean(editorProjectId);
  const editorContext = useEditorContext(editorProjectId);
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
  const [readiness, setReadiness] = useState<ReconstructionReadiness | null>(null);
  const [statusMessage, setStatusMessage] = useState("Ready");
  const [isSaving, setIsSaving] = useState(false);
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
  const assetPreviewUrlsRef = useRef<Set<string>>(new Set());

  useEffect(() => {
    void loadReadiness();
    if (isProjectEditor) {
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
  }, [isProjectEditor]);

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

  async function loadReadiness() {
    try {
      setReadiness(await api.getReconstructionReadiness());
    } catch (error) {
      setReadiness(null);
      setStatusMessage(messageFromError(error));
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

  async function saveDesign() {
    if (!modelAsset || !config) {
      return;
    }
    if (isProjectEditor && (!editorPermissions.canEdit || !editorPermissions.canBake)) {
      setStatusMessage("FORBIDDEN: You do not have permission to save or bake this design.");
      return null;
    }

    setIsSaving(true);
    setStatusMessage("SAVING_DRAFT");
    try {
      const bakeConfig = withEditorMetadata(await prepareBakeConfig(config));
      const savedDesign =
        isProjectEditor && editorProjectId
          ? await editorClient.saveDesign(editorProjectId, bakeConfig, designName)
          : design
            ? await api.updateDesign(design.id, designName, bakeConfig)
            : await api.createDesign(modelAsset.id, designName, bakeConfig);
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
      setConfig(await hydrateDesignAssetPreviewUrls(refreshedDesign.designConfig));
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
      setIsSaving(false);
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
    if (isSaving || isExporting) {
      return;
    }
    if (isProjectEditor && !editorPermissions.canExport) {
      setExportMessage("You do not have permission to export this design.");
      setStatusMessage("FORBIDDEN: You do not have permission to export this design.");
      return;
    }

    setIsExporting(true);
    setExportMessage("EXPORTING");
    setStatusMessage("EXPORTING");
    try {
      const hasUnsavedConfig = config ? configFingerprint(config) !== savedConfigFingerprint : false;
      const savedDesign = !design || hasUnsavedConfig ? await saveDesign() : design;
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
    if (!exportPackage || isExporting) {
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

  return (
    <AppShell user={user} onLogout={logout}>
      <main className="workspace" id="main-workspace">
        {isProjectEditor && !user ? (
          <EditorRouteState
            state={editorContext.state}
            message={editorContext.errorMessage ?? "Redirecting to login."}
          />
        ) : !user ? (
          <AuthPanel
            mode={authMode}
            name={authName}
            email={authEmail}
            password={authPassword}
            isBusy={isAuthBusy}
            statusMessage={statusMessage}
            onModeChange={setAuthMode}
            onNameChange={setAuthName}
            onEmailChange={setAuthEmail}
            onPasswordChange={setAuthPassword}
            onSubmit={submitAuth}
            onDemoAuth={useDemoAuth}
          />
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
              <span className="status-line">{statusMessage}</span>
            </section>

            <ReadinessBanner readiness={readiness} onRefresh={loadReadiness} />

            <WorkflowGuide
              hasModel={Boolean(modelAsset && activeModelUrl)}
              layerCount={(config?.stickers.length ?? 0) + (config?.texts.length ?? 0)}
              hasActiveLayer={Boolean(activeLayerId)}
              isSaved={Boolean(config && savedConfigFingerprint && configFingerprint(config) === savedConfigFingerprint)}
              hasExportPackage={Boolean(exportPackage)}
            />

            <section className="main-grid">
              <MetadataPanel scanSession={scanSession} modelAsset={modelAsset} />
              <ModelViewer
                modelUrl={activeModelUrl}
                config={config}
                activeLayerId={activeLayerId}
                gizmoMode={gizmoMode}
                hiddenLayerIds={hiddenLayerIds}
                isSaving={isSaving}
                previewErrorMessage={previewErrorMessage}
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
                isExporting={isExporting}
                canEdit={!isProjectEditor || editorPermissions.canEdit}
                canBake={!isProjectEditor || editorPermissions.canBake}
                canExport={!isProjectEditor || editorPermissions.canExport}
                exportMessage={exportMessage}
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

type WorkflowGuideProps = {
  hasModel: boolean;
  layerCount: number;
  hasActiveLayer: boolean;
  isSaved: boolean;
  hasExportPackage: boolean;
};

function EditorRouteState({ state, message }: { state: string; message: string }) {
  return (
    <section className="auth-panel">
      <div className="empty-panel-callout">
        <RefreshCw size={22} aria-hidden="true" />
        <div>
          <h2>{state}</h2>
          <p>{message}</p>
        </div>
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
      <span className="status-line">{state}</span>
      <span className="status-line">
        {canEdit ? "Edit" : "View"} / {canBake ? "Bake" : "No bake"} / {canExport ? "Export" : "No export"}
      </span>
    </div>
  );
}

type WorkflowStepState = "complete" | "current" | "upcoming";

function WorkflowGuide({
  hasModel,
  layerCount,
  hasActiveLayer,
  isSaved,
  hasExportPackage,
}: WorkflowGuideProps) {
  const hasLayers = layerCount > 0;
  const placementState: WorkflowStepState = !hasLayers ? "upcoming" : isSaved ? "complete" : "current";
  const exportState: WorkflowStepState = hasExportPackage ? "complete" : isSaved ? "current" : "upcoming";

  const steps: Array<{
    icon: typeof Search;
    title: string;
    detail: string;
    state: WorkflowStepState;
  }> = [
    {
      icon: Search,
      title: "Load or import",
      detail: hasModel ? "Model is ready in the viewer." : "Paste a scan ID or import a GLB/OBJ model.",
      state: hasModel ? "complete" : "current",
    },
    {
      icon: ImagePlus,
      title: "Add artwork",
      detail: hasLayers ? `${layerCount} layer${layerCount === 1 ? "" : "s"} added.` : "Use text, upload, draw, or preset stickers.",
      state: !hasModel ? "upcoming" : hasLayers ? "complete" : "current",
    },
    {
      icon: MousePointer2,
      title: "Place on shoe",
      detail: hasActiveLayer ? "Use move, rotate, scale, then apply to surface." : "Select a layer before adjusting placement.",
      state: placementState,
    },
    {
      icon: Save,
      title: "Save and export",
      detail: hasExportPackage ? "ZIP package is ready to download." : "Save Draft bakes the preview before export.",
      state: exportState,
    },
  ];

  return (
    <section className="workflow-guide" id="workflow-guide" aria-label="Editor workflow">
      <div className="workflow-guide-header">
        <div>
          <h2>Editor flow</h2>
          <p>Follow the same left-to-right order used by most creation tools.</p>
        </div>
      </div>
      <ol className="workflow-steps">
        {steps.map((step, index) => {
          const Icon = step.icon;
          return (
            <li className={`workflow-step ${step.state}`} key={step.title}>
              <span className="workflow-step-index">{index + 1}</span>
              <span className="workflow-step-icon">
                <Icon size={18} aria-hidden="true" />
              </span>
              <span className="workflow-step-copy">
                <strong>{step.title}</strong>
                <span>{step.detail}</span>
              </span>
            </li>
          );
        })}
      </ol>
    </section>
  );
}

type ReadinessBannerProps = {
  readiness: ReconstructionReadiness | null;
  onRefresh: () => void;
};

function ReadinessBanner({ readiness, onRefresh }: ReadinessBannerProps) {
  if (!readiness) {
    return (
      <section className="readiness-banner warning">
        <Wrench size={18} aria-hidden="true" />
        <div>
          <h2>Reconstruction readiness unknown</h2>
          <p>Backend readiness could not be loaded.</p>
        </div>
        <button type="button" onClick={onRefresh}>
          <RefreshCw size={16} aria-hidden="true" />
          Retry
        </button>
      </section>
    );
  }

  const memory = readiness.resources.find((resource) => resource.name === "available_memory");
  const storage = readiness.resources.find((resource) => resource.name === "storage_free");

  return (
    <section className={`readiness-banner ${readiness.ready ? "ready" : "warning"}`}>
      {readiness.ready ? <CheckCircle2 size={18} aria-hidden="true" /> : <AlertTriangle size={18} aria-hidden="true" />}
      <div className="readiness-copy">
        <h2>{readiness.ready ? "Reconstruction ready" : "Reconstruction blocked"}</h2>
        <p>{readiness.message}</p>
        <div className="readiness-metrics">
          <span>
            <Cpu size={14} aria-hidden="true" />
            RAM {formatResource(memory)}
          </span>
          <span>
            <HardDrive size={14} aria-hidden="true" />
            Storage {formatResource(storage)}
          </span>
          <span>
            <Wrench size={14} aria-hidden="true" />
            Threads {String(readiness.settings.maxThreads ?? "n/a")}
          </span>
        </div>
        {readiness.missingTools.length > 0 ? (
          <div className="tool-chip-row">
            {readiness.missingTools.map((tool) => (
              <span className="tool-chip" key={tool}>
                {tool}
              </span>
            ))}
          </div>
        ) : null}
      </div>
      <button type="button" onClick={onRefresh}>
        <RefreshCw size={16} aria-hidden="true" />
        Refresh
      </button>
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
          <button type="button" disabled={isBusy} onClick={onDemoAuth}>
            Demo
          </button>
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

function messageFromError(error: unknown): string {
  if (error instanceof ApiError) {
    return `${error.status}: ${error.message}`;
  }
  if (error instanceof Error) {
    return error.message;
  }
  return "Unexpected error";
}
