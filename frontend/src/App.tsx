import { AlertTriangle, CheckCircle2, Cpu, HardDrive, LogIn, RefreshCw, Search, UserPlus, Wrench } from "lucide-react";
import { FormEvent, useEffect, useMemo, useState } from "react";

import { api, ApiError, designStorageKey } from "./api/client";
import type { ModelImportPayload } from "./api/client";
import { EditorPanels } from "./components/Editor/EditorPanels";
import { AppShell } from "./components/Layout/AppShell";
import { MetadataPanel } from "./components/MetadataPanel/MetadataPanel";
import { ModelImportPanel } from "./components/ModelImport/ModelImportPanel";
import { ModelViewer } from "./components/ModelViewer/ModelViewer";
import type {
  Design,
  DesignConfig,
  ExportPackage,
  ModelAsset,
  ReconstructionReadiness,
  ScanSession,
  User,
} from "./types";

export function App() {
  const [user, setUser] = useState<User | null>(null);
  const [scanId, setScanId] = useState(() => new URLSearchParams(window.location.search).get("scanId") ?? "");
  const [scanSession, setScanSession] = useState<ScanSession | null>(null);
  const [modelAsset, setModelAsset] = useState<ModelAsset | null>(null);
  const [modelUrl, setModelUrl] = useState<string | null>(null);
  const [design, setDesign] = useState<Design | null>(null);
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

  const canLoad = useMemo(() => scanId.trim().length > 0 && Boolean(user), [scanId, user]);

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

  function logout() {
    api.logout();
    setUser(null);
    setScanSession(null);
    setModelAsset(null);
    setModelUrl(null);
    setDesign(null);
    setConfig(null);
    setExportPackage(null);
    setStatusMessage("Signed out");
  }

  async function loadScan() {
    if (!scanId.trim() || !user) {
      return;
    }

    setStatusMessage("Loading scan");
    setModelAsset(null);
    setModelUrl(null);
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
      await loadSavedDesign(loadedModel.id);
      setStatusMessage("Model loaded");
    } catch (error) {
      setStatusMessage(messageFromError(error));
    }
  }

  async function importModel(payload: ModelImportPayload) {
    setIsImporting(true);
    setStatusMessage("Importing model");
    setModelAsset(null);
    setModelUrl(null);
    setDesign(null);
    setConfig(null);
    setExportPackage(null);

    try {
      const imported = await api.importModel(payload);
      setScanId(imported.scanSession.id);
      setScanSession(imported.scanSession);
      setModelAsset(imported.modelAsset);
      setScanIdInUrl(imported.scanSession.id);
      setModelUrl(await api.fetchModelBlobUrl(imported.modelAsset));
      await loadSavedDesign(imported.modelAsset.id);
      setStatusMessage("Imported model loaded");
    } catch (error) {
      setStatusMessage(messageFromError(error));
    } finally {
      setIsImporting(false);
    }
  }

  async function loadSavedDesign(modelAssetId: string) {
    const savedDesignId = localStorage.getItem(designStorageKey(modelAssetId));
    if (!savedDesignId) {
      const defaultConfig = createDefaultConfig(modelAssetId);
      setConfig(defaultConfig);
      setDesign(null);
      setDesignName("Untitled shoe design");
      return;
    }

    try {
      const savedDesign = await api.getDesign(savedDesignId);
      setDesign(savedDesign);
      setDesignName(savedDesign.name);
      setConfig(savedDesign.designConfig);
    } catch {
      localStorage.removeItem(designStorageKey(modelAssetId));
      setConfig(createDefaultConfig(modelAssetId));
    }
  }

  async function saveDesign() {
    if (!modelAsset || !config) {
      return;
    }

    setIsSaving(true);
    setStatusMessage("Saving design");
    try {
      const savedDesign = design
        ? await api.updateDesign(design.id, designName, config)
        : await api.createDesign(modelAsset.id, designName, config);
      setDesign(savedDesign);
      setDesignName(savedDesign.name);
      setConfig(savedDesign.designConfig);
      localStorage.setItem(designStorageKey(modelAsset.id), savedDesign.id);
      setStatusMessage("Design saved");
      return savedDesign;
    } catch (error) {
      setStatusMessage(messageFromError(error));
      return null;
    } finally {
      setIsSaving(false);
    }
  }

  async function exportDesign() {
    const savedDesign = design ?? (await saveDesign());
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
              <ModelViewer modelUrl={modelUrl} config={config} />
              <EditorPanels
                config={config}
                modelAsset={modelAsset}
                designName={designName}
                isSaving={isSaving}
                exportPackage={exportPackage}
                onNameChange={setDesignName}
                onConfigChange={setConfig}
                onSave={saveDesign}
                onExport={exportDesign}
                onDownload={downloadExport}
                onDownloadModelFile={downloadModelFile}
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

function createDefaultConfig(modelAssetId: string): DesignConfig {
  return {
    modelAssetId,
    baseColor: "#ffffff",
    material: {
      roughness: 0.5,
      metallic: 0,
    },
    stickers: [],
    texts: [],
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
