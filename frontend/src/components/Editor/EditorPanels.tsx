import { Download, ImagePlus, Save, Type } from "lucide-react";

import type { DesignConfig, ExportPackage, ModelAsset } from "../../types";

type EditorPanelsProps = {
  config: DesignConfig | null;
  modelAsset: ModelAsset | null;
  designName: string;
  isSaving: boolean;
  exportPackage: ExportPackage | null;
  activeLayerId: string | null;
  onNameChange: (name: string) => void;
  onConfigChange: (config: DesignConfig) => void;
  onActiveLayerChange: (id: string | null) => void;
  onSave: () => void;
  onExport: () => void;
  onDownload: () => void;
  onDownloadModelFile: (urlPath: string, filename: string) => void;
};

export function EditorPanels({
  config,
  modelAsset,
  designName,
  isSaving,
  exportPackage,
  activeLayerId,
  onNameChange,
  onConfigChange,
  onActiveLayerChange,
  onSave,
  onExport,
  onDownload,
  onDownloadModelFile,
}: EditorPanelsProps) {
  if (!config) {
    return (
      <aside className="editor-panel">
        <h2>Design Tools</h2>
        <p className="muted">Tools unlock after a completed scan model is loaded.</p>
      </aside>
    );
  }

  const update = (patch: Partial<DesignConfig>) => onConfigChange({ ...config, ...patch });

  const activeSticker = config.stickers.find((s) => s.id === activeLayerId);
  const activeText = config.texts.find((t) => t.id === activeLayerId);
  const activeLayer = activeSticker || activeText;

  function updateLayer(id: string, patch: any) {
    if (activeSticker) {
      update({
        stickers: config!.stickers.map((s) => (s.id === id ? { ...s, ...patch } : s)),
      });
    } else if (activeText) {
      update({
        texts: config!.texts.map((t) => (t.id === id ? { ...t, ...patch } : t)),
      });
    }
  }

  return (
    <aside className="editor-panel">
      <section className="panel-section">
        <h2>Design Tools</h2>
        <label>
          Draft name
          <input value={designName} onChange={(event) => onNameChange(event.target.value)} />
        </label>
      </section>

      <section className="panel-section">
        <h3>Material</h3>
        <label>
          Base color
          <input
            type="color"
            value={config.baseColor}
            onChange={(event) => update({ baseColor: event.target.value })}
          />
        </label>
        <label>
          Roughness
          <input
            type="range"
            min="0"
            max="1"
            step="0.05"
            value={config.material.roughness}
            onChange={(event) =>
              update({
                material: { ...config.material, roughness: Number(event.target.value) },
              })
            }
          />
        </label>
      </section>

      <section className="panel-section">
        <h3>Decals</h3>
        <div className="button-row">
          <button type="button" onClick={() => onConfigChange(addSticker(config))}>
            <ImagePlus size={16} aria-hidden="true" />
            Sticker
          </button>
          <button type="button" onClick={() => onConfigChange(addText(config))}>
            <Type size={16} aria-hidden="true" />
            Text
          </button>
        </div>
      </section>

      <section className="panel-section">
        <h3>Layers</h3>
        <div className="layer-list" onClick={(e) => {
          if (e.target === e.currentTarget) onActiveLayerChange(null);
        }}>
          {config.stickers.map((sticker) => (
            <div
              className={`layer-row ${activeLayerId === sticker.id ? "active" : ""}`}
              key={sticker.id}
              onClick={() => onActiveLayerChange(sticker.id)}
            >
              <span>{sticker.id}</span>
              <span>sticker</span>
            </div>
          ))}
          {config.texts.map((textLayer) => (
            <div
              className={`layer-row ${activeLayerId === textLayer.id ? "active" : ""}`}
              key={textLayer.id}
              onClick={() => onActiveLayerChange(textLayer.id)}
            >
              <span>{textLayer.value}</span>
              <span>text</span>
            </div>
          ))}
          {config.stickers.length === 0 && config.texts.length === 0 ? (
            <p className="muted">No decal layers yet.</p>
          ) : null}
        </div>
      </section>

      {activeLayer && (
        <section className="panel-section highlight">
          <h3>Layer Properties</h3>
          {activeText && (
            <label>
              Text
              <input
                value={activeText.value}
                onChange={(e) => updateLayer(activeLayer.id, { value: e.target.value })}
              />
            </label>
          )}
          <label>
            Scale
            <input
              type="range"
              min="0.05"
              max="2"
              step="0.05"
              value={activeLayer.scale}
              onChange={(e) => updateLayer(activeLayer.id, { scale: Number(e.target.value) })}
            />
          </label>
          <label>
            Rotation
            <input
              type="range"
              min="-3.14"
              max="3.14"
              step="0.05"
              value={activeLayer.rotation[2]}
              onChange={(e) => {
                const rot = [...activeLayer.rotation];
                rot[2] = Number(e.target.value);
                updateLayer(activeLayer.id, { rotation: rot as [number, number, number] });
              }}
            />
          </label>
        </section>
      )}

      <section className="panel-section">
        <button className="primary-button" type="button" disabled={isSaving} onClick={onSave}>
          <Save size={16} aria-hidden="true" />
          {isSaving ? "Saving" : "Save Draft"}
        </button>
        <button type="button" onClick={onExport}>
          <Download size={16} aria-hidden="true" />
          Export Package
        </button>
        {exportPackage ? (
          <button type="button" onClick={onDownload}>
            <Download size={16} aria-hidden="true" />
            Download ZIP
          </button>
        ) : null}
      </section>

      {modelAsset ? (
        <section className="panel-section">
          <h3>Reconstruction Files</h3>
          <div className="download-grid">
            <button
              type="button"
              onClick={() => onDownloadModelFile(modelAsset.glbUrl, "shoe_preview.glb")}
            >
              <Download size={16} aria-hidden="true" />
              GLB
            </button>
            <button type="button" onClick={() => onDownloadModelFile(modelAsset.objUrl, "shoe.obj")}>
              <Download size={16} aria-hidden="true" />
              OBJ
            </button>
            <button type="button" onClick={() => onDownloadModelFile(modelAsset.mtlUrl, "shoe.mtl")}>
              <Download size={16} aria-hidden="true" />
              MTL
            </button>
            <button
              type="button"
              onClick={() => onDownloadModelFile(modelAsset.textureUrl, "shoe_texture.png")}
            >
              <Download size={16} aria-hidden="true" />
              Texture
            </button>
            <button
              type="button"
              onClick={() =>
                onDownloadModelFile(modelAsset.objPackageZipUrl, "shoe_obj_package.zip")
              }
            >
              <Download size={16} aria-hidden="true" />
              OBJ ZIP
            </button>
          </div>
        </section>
      ) : null}
    </aside>
  );
}

function addSticker(config: DesignConfig): DesignConfig {
  const index = config.stickers.length + 1;
  return {
    ...config,
    stickers: [
      ...config.stickers,
      {
        id: `sticker_${String(index).padStart(3, "0")}`,
        type: "image",
        imageUrl: "/assets/stickers/flame.png",
        position: [0.25, 0.45, 0.35],
        rotation: [0, 0.35, 0],
        scale: 0.35,
      },
    ],
  };
}

function addText(config: DesignConfig): DesignConfig {
  const index = config.texts.length + 1;
  return {
    ...config,
    texts: [
      ...config.texts,
      {
        id: `text_${String(index).padStart(3, "0")}`,
        value: "TAK",
        font: "Arial",
        color: "#111111",
        position: [-0.1, 0.48, 0.42],
        rotation: [0, 0.35, 0],
        scale: 0.22,
      },
    ],
  };
}
