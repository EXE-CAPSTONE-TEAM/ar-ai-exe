import { LogIn, RefreshCw, Search, UserPlus } from "lucide-react";
import { FormEvent, useEffect, useMemo, useState } from "react";

import { api, ApiError, designStorageKey } from "./api/client";
import { EditorPanels } from "./components/Editor/EditorPanels";
import { AppShell } from "./components/Layout/AppShell";
import { MetadataPanel } from "./components/MetadataPanel/MetadataPanel";
import { ModelViewer } from "./components/ModelViewer/ModelViewer";
import type { Design, DesignConfig, ExportPackage, ModelAsset, ScanSession, User } from "./types";

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
  const [statusMessage, setStatusMessage] = useState("Ready");
  const [isSaving, setIsSaving] = useState(false);
  const [authMode, setAuthMode] = useState<"login" | "register">("login");
  const [authName, setAuthName] = useState("");
  const [authEmail, setAuthEmail] = useState("");
  const [authPassword, setAuthPassword] = useState("");
  const [isAuthBusy, setIsAuthBusy] = useState(false);

  useEffect(() => {
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

      const url = new URL(window.location.href);
      url.searchParams.set("scanId", loadedScan.id);
      window.history.replaceState({}, "", url);

      if (!loadedScan.modelAssetId) {
        setStatusMessage(`Scan is ${loadedScan.status}. Waiting for model output.`);
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
              <span className="status-line">{statusMessage}</span>
            </section>

            <section className="main-grid">
              <MetadataPanel scanSession={scanSession} modelAsset={modelAsset} />
              <ModelViewer modelUrl={modelUrl} config={config} />
              <EditorPanels
                config={config}
                designName={designName}
                isSaving={isSaving}
                exportPackage={exportPackage}
                onNameChange={setDesignName}
                onConfigChange={setConfig}
                onSave={saveDesign}
                onExport={exportDesign}
                onDownload={downloadExport}
              />
            </section>
          </>
        )}
      </main>
    </AppShell>
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

function messageFromError(error: unknown): string {
  if (error instanceof ApiError) {
    return `${error.status}: ${error.message}`;
  }
  if (error instanceof Error) {
    return error.message;
  }
  return "Unexpected error";
}