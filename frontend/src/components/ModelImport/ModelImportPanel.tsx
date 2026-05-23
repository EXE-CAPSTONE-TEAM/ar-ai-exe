import { PackageOpen, Upload } from "lucide-react";
import { FormEvent, useState } from "react";

import type { ModelImportPayload } from "../../api/client";
import type { ScanMetadata } from "../../types";

type ModelImportPanelProps = {
  isBusy: boolean;
  onImport: (payload: ModelImportPayload) => Promise<void>;
};

type ImportFormat = "glb" | "obj";
type ObjInputMode = "files" | "zip";

export function ModelImportPanel({ isBusy, onImport }: ModelImportPanelProps) {
  const [name, setName] = useState("Imported shoe model");
  const [format, setFormat] = useState<ImportFormat>("glb");
  const [objMode, setObjMode] = useState<ObjInputMode>("files");
  const [modelFile, setModelFile] = useState<File | null>(null);
  const [mtlFile, setMtlFile] = useState<File | null>(null);
  const [textureFile, setTextureFile] = useState<File | null>(null);
  const [packageFile, setPackageFile] = useState<File | null>(null);
  const [metadata, setMetadata] = useState<ScanMetadata>(defaultMetadata);

  async function submitImport(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    await onImport({
      name,
      format,
      metadata,
      model: format === "glb" || objMode === "files" ? modelFile : null,
      mtl: format === "obj" && objMode === "files" ? mtlFile : null,
      texture: format === "obj" && objMode === "files" ? textureFile : null,
      package: format === "obj" && objMode === "zip" ? packageFile : null,
    });
  }

  function patchMetadata(patch: Partial<ScanMetadata>) {
    setMetadata((current) => ({ ...current, ...patch }));
  }

  return (
    <form className="model-import-panel" onSubmit={submitImport}>
      <div className="import-title-row">
        <h2>Import Model</h2>
        <div className="format-tabs" role="tablist" aria-label="Model format">
          <button
            type="button"
            className={format === "glb" ? "active" : ""}
            onClick={() => setFormat("glb")}
          >
            GLB
          </button>
          <button
            type="button"
            className={format === "obj" ? "active" : ""}
            onClick={() => setFormat("obj")}
          >
            OBJ
          </button>
        </div>
      </div>

      <div className="import-form-grid">
        <label>
          Model name
          <input value={name} onChange={(event) => setName(event.target.value)} required minLength={1} />
        </label>

        {format === "obj" ? (
          <label>
            OBJ source
            <select value={objMode} onChange={(event) => setObjMode(event.target.value as ObjInputMode)}>
              <option value="files">Files</option>
              <option value="zip">ZIP</option>
            </select>
          </label>
        ) : null}

        {format === "glb" ? (
          <FileInput label="GLB file" accept=".glb" required disabled={isBusy} onChange={setModelFile} />
        ) : objMode === "zip" ? (
          <FileInput label="OBJ ZIP" accept=".zip" required disabled={isBusy} onChange={setPackageFile} />
        ) : (
          <>
            <FileInput label="OBJ file" accept=".obj" required disabled={isBusy} onChange={setModelFile} />
            <FileInput label="MTL file" accept=".mtl" disabled={isBusy} onChange={setMtlFile} />
            <FileInput
              label="Texture"
              accept=".png,.jpg,.jpeg"
              disabled={isBusy}
              onChange={setTextureFile}
            />
          </>
        )}
      </div>

      <div className="metadata-form-grid">
        <label>
          Size system
          <select
            value={metadata.shoe.sizeSystem}
            onChange={(event) =>
              patchMetadata({
                shoe: { ...metadata.shoe, sizeSystem: event.target.value as ScanMetadata["shoe"]["sizeSystem"] },
              })
            }
          >
            <option value="EU">EU</option>
            <option value="US">US</option>
            <option value="UK">UK</option>
            <option value="CM">CM</option>
          </select>
        </label>
        <TextField
          label="Size"
          value={metadata.shoe.size}
          onChange={(size) => patchMetadata({ shoe: { ...metadata.shoe, size } })}
        />
        <label>
          Side
          <select
            value={metadata.shoe.side}
            onChange={(event) =>
              patchMetadata({ shoe: { ...metadata.shoe, side: event.target.value as ScanMetadata["shoe"]["side"] } })
            }
          >
            <option value="left">Left</option>
            <option value="right">Right</option>
            <option value="both">Both</option>
          </select>
        </label>
        <label>
          Type
          <select
            value={metadata.shoe.type}
            onChange={(event) =>
              patchMetadata({ shoe: { ...metadata.shoe, type: event.target.value as ScanMetadata["shoe"]["type"] } })
            }
          >
            <option value="sneaker">Sneaker</option>
            <option value="running">Running</option>
            <option value="boot">Boot</option>
            <option value="sandal">Sandal</option>
            <option value="other">Other</option>
          </select>
        </label>
        <label>
          Material
          <select
            value={metadata.shoe.material}
            onChange={(event) =>
              patchMetadata({
                shoe: { ...metadata.shoe, material: event.target.value as ScanMetadata["shoe"]["material"] },
              })
            }
          >
            <option value="canvas">Canvas</option>
            <option value="leather">Leather</option>
            <option value="synthetic">Synthetic</option>
            <option value="mesh">Mesh</option>
            <option value="unknown">Unknown</option>
          </select>
        </label>
        <TextField
          label="Condition"
          value={metadata.shoe.condition}
          onChange={(condition) => patchMetadata({ shoe: { ...metadata.shoe, condition } })}
        />
        <NumberField
          label="Length cm"
          value={metadata.measurements.lengthCm}
          onChange={(lengthCm) => patchMetadata({ measurements: { ...metadata.measurements, lengthCm } })}
        />
        <NumberField
          label="Width cm"
          value={metadata.measurements.widthCm}
          onChange={(widthCm) => patchMetadata({ measurements: { ...metadata.measurements, widthCm } })}
        />
        <TextField
          label="Calibration"
          value={metadata.scanSetup.calibrationReference}
          onChange={(calibrationReference) =>
            patchMetadata({ scanSetup: { ...metadata.scanSetup, calibrationReference } })
          }
        />
        <TextField
          label="Lighting"
          value={metadata.scanSetup.lighting}
          onChange={(lighting) => patchMetadata({ scanSetup: { ...metadata.scanSetup, lighting } })}
        />
        <TextField
          label="Background"
          value={metadata.scanSetup.background}
          onChange={(background) => patchMetadata({ scanSetup: { ...metadata.scanSetup, background } })}
        />
        <label>
          Goal
          <textarea
            value={metadata.customizationGoal.join(", ")}
            onChange={(event) => patchMetadata({ customizationGoal: splitGoals(event.target.value) })}
            required
          />
        </label>
      </div>

      <button type="submit" className="primary-button" disabled={isBusy}>
        {format === "obj" && objMode === "zip" ? (
          <PackageOpen size={16} aria-hidden="true" />
        ) : (
          <Upload size={16} aria-hidden="true" />
        )}
        {isBusy ? "Importing" : "Import"}
      </button>
    </form>
  );
}

function FileInput({
  label,
  accept,
  required = false,
  disabled,
  onChange,
}: {
  label: string;
  accept: string;
  required?: boolean;
  disabled: boolean;
  onChange: (file: File | null) => void;
}) {
  return (
    <label>
      {label}
      <input
        type="file"
        accept={accept}
        required={required}
        disabled={disabled}
        onChange={(event) => onChange(event.target.files?.[0] ?? null)}
      />
    </label>
  );
}

function TextField({ label, value, onChange }: { label: string; value: string; onChange: (value: string) => void }) {
  return (
    <label>
      {label}
      <input value={value} onChange={(event) => onChange(event.target.value)} required minLength={1} />
    </label>
  );
}

function NumberField({ label, value, onChange }: { label: string; value: number; onChange: (value: number) => void }) {
  return (
    <label>
      {label}
      <input
        type="number"
        min="0.1"
        step="0.1"
        value={Number.isFinite(value) ? value : ""}
        onChange={(event) => onChange(Number(event.target.value))}
        required
      />
    </label>
  );
}

function splitGoals(value: string): string[] {
  return value
    .split(/[\n,]/)
    .map((item) => item.trim())
    .filter(Boolean);
}

const defaultMetadata: ScanMetadata = {
  shoe: {
    sizeSystem: "EU",
    size: "42",
    side: "both",
    type: "sneaker",
    material: "unknown",
    condition: "Imported model",
  },
  measurements: {
    lengthCm: 28,
    widthCm: 10,
  },
  scanSetup: {
    calibrationReference: "Manual import",
    lighting: "n/a",
    background: "n/a",
  },
  customizationGoal: ["visual customization"],
};
