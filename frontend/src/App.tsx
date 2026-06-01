import { AlertTriangle, CheckCircle2, Cpu, HardDrive, LogIn, RefreshCw, Search, UserPlus, Wrench } from "lucide-react";
import { FormEvent, useEffect, useMemo, useRef, useState } from "react";

import { api, ApiError, designStorageKey } from "./api/client";
import type { ModelImportPayload } from "./api/client";
import { EditorPanels } from "./components/Editor/EditorPanels";
import { AppShell } from "./components/Layout/AppShell";
import { MetadataPanel } from "./components/MetadataPanel/MetadataPanel";
import { ModelImportPanel } from "./components/ModelImport/ModelImportPanel";
import { ModelViewer } from "./components/ModelViewer/ModelViewer";
import type {
  Design,
  DesignAssetSource,
  DesignConfig,
  ExportPackage,
  ModelAsset,
  ReconstructionReadiness,
  ScanSession,
  TextLayer,
  User,
} from "./types";

export function App() {
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
  const assetPreviewUrlsRef = useRef<Set<string>>(new Set());

  useEffect(() => {
    void loadReadiness();
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
  }, []);

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

    setIsSaving(true);
    setStatusMessage("Đang áp sticker/text vào giày...");
    try {
      const bakeConfig = await prepareBakeConfig(config);
      const savedDesign = design
        ? await api.updateDesign(design.id, designName, bakeConfig)
        : await api.createDesign(modelAsset.id, designName, bakeConfig);
      setDesign(savedDesign);
      setDesignName(savedDesign.name);
      setConfig(await hydrateDesignAssetPreviewUrls(savedDesign.designConfig));
      setSavedConfigFingerprint(configFingerprint(savedDesign.designConfig));
      localStorage.setItem(designStorageKey(modelAsset.id), savedDesign.id);
      const hasPreview = await loadBakedPreview(savedDesign);
      if (savedDesign.previewStatus === "failed") {
        setPreviewErrorMessage(savedDesign.previewErrorMessage ?? "Move the sticker/text closer to the shoe and save again.");
        setStatusMessage(savedDesign.previewErrorMessage ?? "Draft saved, but preview bake failed.");
      } else {
        setPreviewErrorMessage(null);
        setStatusMessage(hasPreview ? "Draft saved and applied to shoe" : "Design saved");
      }
      return savedDesign;
    } catch (error) {
      setStatusMessage(messageFromError(error));
      return null;
    } finally {
      setIsSaving(false);
    }
  }

  function handleConfigChange(nextConfig: DesignConfig) {
    if (previewModelUrl && config && !canKeepBakedPreview(config, nextConfig, bakedLayerIds)) {
      clearBakedPreview();
    }
    setPreviewErrorMessage(null);
    setConfig(nextConfig);
  }

  function applyActiveLayerToSurface() {
    setSurfaceApplyRequest((value) => value + 1);
  }

  async function uploadDesignAssetWithPreview(file: File, sourceType: Extract<DesignAssetSource, "upload" | "canvas">) {
    const asset = await api.uploadDesignAsset(file, sourceType);
    return {
      assetId: asset.id,
      sourceType,
      fileName: asset.fileName,
      previewUrl: rememberAssetPreviewUrl(await api.fetchDesignAssetBlobUrl(asset.id)),
    };
  }

  async function exportDesign() {
    const hasUnsavedConfig = config ? configFingerprint(config) !== savedConfigFingerprint : false;
    const savedDesign = !design || hasUnsavedConfig ? await saveDesign() : design;
    const activeDesignId = savedDesign?.id ?? (modelAsset && localStorage.getItem(designStorageKey(modelAsset.id)));
    if (!activeDesignId) {
      setStatusMessage("Save the draft before exporting.");
      return;
    }

    try {
      setStatusMessage("Creating export package");
      const createdExport = await api.exportDesign(activeDesignId);
      setExportPackage(createdExport);
      setStatusMessage("Export package ready");
    } catch (error) {
      setStatusMessage(messageFromError(error));
    }
  }

  async function downloadExport() {
    if (!exportPackage) {
      return;
    }
    try {
      await api.downloadExport(exportPackage);
    } catch (error) {
      setStatusMessage(messageFromError(error));
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
    <AppShell user={user}>
      <main className="workspace">
        {!user ? (
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
                  <button type="button" onClick={logout}>
                    Sign out
                  </button>
                </div>
                <ModelImportPanel isBusy={isImporting} onImport={importModel} />
              </div>
              <span className="status-line">{statusMessage}</span>
            </section>

            <ReadinessBanner readiness={readiness} onRefresh={loadReadiness} />

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
