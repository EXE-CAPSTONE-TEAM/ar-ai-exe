import {
  Activity,
  CheckCircle2,
  Circle,
  Info,
  Layers3,
  Ruler,
  Sparkles,
  Target,
} from "lucide-react";
import type { DesignConfig, ModelAsset, ScanSession } from "../../types";

type MeshBounds = {
  center: [number, number, number];
  size: [number, number, number];
};

type MetadataPanelProps = {
  scanSession: ScanSession | null;
  modelAsset: ModelAsset | null;
  config: DesignConfig | null;
  designName: string;
  activeLayerId: string | null;
  meshBounds: MeshBounds | null;
  isSaved: boolean;
  hasBakedPreview: boolean;
  hasExportPackage: boolean;
};

export function MetadataPanel({
  scanSession,
  modelAsset,
  config,
  designName,
  activeLayerId,
  meshBounds,
  isSaved,
  hasBakedPreview,
  hasExportPackage,
}: MetadataPanelProps) {
  const qualityReport = modelAsset?.qualityReport;
  const isImport = scanSession?.sourceType === "import";
  const layerCount = (config?.stickers.length ?? 0) + (config?.texts.length ?? 0);
  const activeLayer = config ? findLayerLabel(config, activeLayerId) : null;
  const nextAction = nextActionState({
    hasModel: Boolean(modelAsset),
    layerCount,
    activeLayer,
    isSaved,
    hasBakedPreview,
    hasExportPackage,
  });

  return (
    <aside className="metadata-panel">
      <section className="panel-section sidebar-hero">
        <div className="section-heading">
          <Sparkles size={18} aria-hidden="true" />
          <div>
            <h2>Workspace</h2>
            <p className="muted">{designName || "Untitled shoe design"}</p>
          </div>
        </div>
        <div className="sidebar-kpi-grid" aria-label="Design summary">
          <div className="sidebar-kpi">
            <span>Layers</span>
            <strong>{layerCount}</strong>
          </div>
          <div className="sidebar-kpi">
            <span>Active</span>
            <strong>{activeLayer ?? "None"}</strong>
          </div>
          <div className="sidebar-kpi">
            <span>Preview</span>
            <strong>{hasBakedPreview ? "Ready" : isSaved ? "Saved" : "Draft"}</strong>
          </div>
        </div>
      </section>

      <section className="panel-section next-action-panel">
        <div className="section-heading">
          <Target size={18} aria-hidden="true" />
          <div>
            <h2>Next action</h2>
            <p className="muted">{nextAction.detail}</p>
          </div>
        </div>
        <strong className="next-action-title">{nextAction.title}</strong>
        <ol className="progress-rail" aria-label="Editor progress">
          {progressSteps({
            hasModel: Boolean(modelAsset),
            layerCount,
            hasActiveLayer: Boolean(activeLayer),
            isSaved,
            hasExportPackage,
          }).map((step) => (
            <li className={`progress-step ${step.state}`} key={step.label}>
              <span className="progress-dot" aria-hidden="true">
                {step.state === "complete" ? <CheckCircle2 size={14} /> : <Circle size={14} />}
              </span>
              <span>{step.label}</span>
            </li>
          ))}
        </ol>
      </section>

      <section className="panel-section">
        <div className="section-heading">
          <Ruler size={18} aria-hidden="true" />
          <div>
            <h2>Model fit</h2>
            <p className="muted">Viewer bounds and source status.</p>
          </div>
        </div>
        {meshBounds ? (
          <div className="model-dimension-grid">
            <DimensionPill label="W" value={meshBounds.size[0]} />
            <DimensionPill label="H" value={meshBounds.size[1]} />
            <DimensionPill label="D" value={meshBounds.size[2]} />
          </div>
        ) : (
          <p className="sidebar-empty-note">Model dimensions appear after the viewer finishes loading.</p>
        )}
      </section>

      <section className="panel-section">
        <div className="section-heading">
          <Info size={18} aria-hidden="true" />
          <div>
            <h2>{isImport ? "Import source" : "Scan source"}</h2>
            <p className="muted">{scanSession ? "Source and processing status." : "Load or import a model to fill this area."}</p>
          </div>
        </div>
        {scanSession ? (
          <dl className="compact-dl">
            <dt>Session</dt>
            <dd>{scanSession.id}</dd>
            {isImport ? (
              <>
                <dt>Name</dt>
                <dd>{scanSession.importName ?? "Imported model"}</dd>
              </>
            ) : null}
            <dt>Status</dt>
            <dd>
              <span className={`status-pill status-${scanSession.status}`}>{scanStatusLabel(scanSession.status)}</span>
            </dd>
            {!isImport ? (
              <>
                <dt>Videos</dt>
                <dd>
                  {scanSession.uploadedPasses.length}/{scanSession.requiredPasses.length} uploaded
                </dd>
              </>
            ) : null}
            <dt>Model</dt>
            <dd>{scanSession.modelAssetId ?? "pending"}</dd>
            {scanSession.errorMessage ? (
              <>
                <dt>Error</dt>
                <dd className="error-text">{scanSession.errorMessage}</dd>
              </>
            ) : null}
          </dl>
        ) : (
          <div className="empty-layer-state">
            <Info size={18} aria-hidden="true" />
            <strong>No source loaded</strong>
            <span>Load a scan ID or import a GLB/OBJ model.</span>
          </div>
        )}
      </section>

      <section className="panel-section">
        <div className="section-heading">
          <Activity size={18} aria-hidden="true" />
          <div>
            <h2>Quality</h2>
            <p className="muted">Import and reconstruction checks.</p>
          </div>
        </div>
        {qualityReport ? (
          <div className="quality-stack">
            <div className="quality-meter-list">
              <QualityMeter label="Overall" value={qualityReport.overallScore} />
              <QualityMeter label="Texture" value={qualityReport.textureConfidence} />
              <QualityMeter label="Geometry" value={qualityReport.geometryConfidence} />
              <QualityMeter label="Coverage" value={qualityReport.coverageScore} />
            </div>
            {Array.isArray(qualityReport.warnings) && qualityReport.warnings.length > 0 ? (
              <div className="warning-list">
                {qualityReport.warnings.map((warning) => (
                  <p key={String(warning)}>{String(warning)}</p>
                ))}
              </div>
            ) : null}
          </div>
        ) : (
          <p className="sidebar-empty-note">Quality report appears after processing completes.</p>
        )}
      </section>
    </aside>
  );
}

function DimensionPill({ label, value }: { label: string; value: number }) {
  return (
    <span className="dimension-pill">
      <small>{label}</small>
      <strong>{value.toFixed(2)}</strong>
    </span>
  );
}

function QualityMeter({ label, value }: { label: string; value: unknown }) {
  return (
    <div className="quality-meter-row">
      <div>
        <strong>{label}</strong>
        <span>{formatQualityValue(value)}</span>
      </div>
      <span className="quality-meter-track" aria-hidden="true">
        <span className="quality-meter-fill" style={{ width: qualityPercent(value) }} />
      </span>
    </div>
  );
}

function findLayerLabel(config: DesignConfig, activeLayerId: string | null): string | null {
  if (!activeLayerId) {
    return null;
  }
  const stickerIndex = config.stickers.findIndex((sticker) => sticker.id === activeLayerId);
  if (stickerIndex >= 0) {
    const sticker = config.stickers[stickerIndex];
    if (sticker.source === "canvas") return "Drawing";
    if (sticker.source === "upload") return "Upload";
    return `Sticker ${stickerIndex + 1}`;
  }
  const textIndex = config.texts.findIndex((text) => text.id === activeLayerId);
  if (textIndex >= 0) {
    return `Text ${textIndex + 1}`;
  }
  return null;
}

function nextActionState({
  hasModel,
  layerCount,
  activeLayer,
  isSaved,
  hasBakedPreview,
  hasExportPackage,
}: {
  hasModel: boolean;
  layerCount: number;
  activeLayer: string | null;
  isSaved: boolean;
  hasBakedPreview: boolean;
  hasExportPackage: boolean;
}) {
  if (!hasModel) {
    return { title: "Load a model", detail: "Start with a scan ID, demo project, or GLB/OBJ import." };
  }
  if (layerCount === 0) {
    return { title: "Add artwork", detail: "Use the right panel to add text, upload an image, draw, or choose a preset." };
  }
  if (!activeLayer) {
    return { title: "Select a layer", detail: "Pick a layer so the 3D controls can move, rotate, scale, and snap it." };
  }
  if (!isSaved || !hasBakedPreview) {
    return { title: "Save draft", detail: "Save Draft bakes a fresh preview after placement changes." };
  }
  if (!hasExportPackage) {
    return { title: "Export ZIP", detail: "The preview is ready. Export when the design is approved." };
  }
  return { title: "Review download", detail: "The export is ready. Download again if the tester needs the ZIP." };
}

function progressSteps({
  hasModel,
  layerCount,
  hasActiveLayer,
  isSaved,
  hasExportPackage,
}: {
  hasModel: boolean;
  layerCount: number;
  hasActiveLayer: boolean;
  isSaved: boolean;
  hasExportPackage: boolean;
}) {
  return [
    { label: "Model", state: hasModel ? "complete" : "current" },
    { label: "Artwork", state: !hasModel ? "upcoming" : layerCount > 0 ? "complete" : "current" },
    { label: "Placement", state: layerCount === 0 ? "upcoming" : hasActiveLayer || isSaved ? "complete" : "current" },
    { label: "Export", state: hasExportPackage ? "complete" : isSaved ? "current" : "upcoming" },
  ] as const;
}

function scanStatusLabel(status: string): string {
  const labels: Record<string, string> = {
    created: "Created",
    waiting_for_uploads: "Waiting for videos",
    uploaded: "Uploaded",
    queued: "Queued",
    toolchain_unavailable: "Toolchain unavailable",
    extracting_frames: "Extracting frames",
    filtering_frames: "Filtering frames",
    preparing_reconstruction: "Preparing",
    reconstructing: "Reconstructing",
    cleaning_mesh: "Cleaning mesh",
    uv_unwrapping: "UV unwrap",
    texture_baking: "Texture bake",
    exporting: "Exporting",
    completed: "Completed",
    failed: "Failed",
  };
  return labels[status] ?? status;
}

function formatQualityValue(value: unknown): string {
  if (typeof value === "number") {
    return Number.isInteger(value) ? String(value) : value.toFixed(1);
  }
  if (typeof value === "string") {
    return value;
  }
  return "n/a";
}

function qualityPercent(value: unknown): string {
  if (typeof value !== "number" || !Number.isFinite(value)) {
    return "0%";
  }
  const normalized = value <= 1 ? value * 100 : value;
  return `${Math.max(0, Math.min(100, normalized))}%`;
}
