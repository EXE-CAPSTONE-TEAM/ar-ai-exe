import type { ModelAsset, ScanSession } from "../../types";

type MetadataPanelProps = {
  scanSession: ScanSession | null;
  modelAsset: ModelAsset | null;
};

export function MetadataPanel({ scanSession, modelAsset }: MetadataPanelProps) {
  const qualityReport = modelAsset?.qualityReport;
  const isImport = scanSession?.sourceType === "import";

  return (
    <aside className="metadata-panel">
      <section className="panel-section">
        <h2>{isImport ? "Import" : "Scan"}</h2>
        {scanSession ? (
          <dl>
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
          <p className="muted">No scan loaded.</p>
        )}
      </section>

      <section className="panel-section">
        <h2>Quality</h2>
        {qualityReport ? (
          <div className="quality-stack">
            <dl className="quality-summary">
              <dt>Overall</dt>
              <dd>{formatQualityValue(qualityReport.overallScore)}</dd>
              <dt>Texture</dt>
              <dd>{formatQualityValue(qualityReport.textureConfidence)}</dd>
              <dt>Geometry</dt>
              <dd>{formatQualityValue(qualityReport.geometryConfidence)}</dd>
              <dt>Coverage</dt>
              <dd>{formatQualityValue(qualityReport.coverageScore)}</dd>
            </dl>
            {Array.isArray(qualityReport.warnings) && qualityReport.warnings.length > 0 ? (
              <div className="warning-list">
                {qualityReport.warnings.map((warning) => (
                  <p key={String(warning)}>{String(warning)}</p>
                ))}
              </div>
            ) : null}
          </div>
        ) : (
          <p className="muted">Quality report appears after processing completes.</p>
        )}
      </section>
    </aside>
  );
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
