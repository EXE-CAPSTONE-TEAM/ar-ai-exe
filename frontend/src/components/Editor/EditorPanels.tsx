import { useState } from "react";
import { Download, ImagePlus, Save, Type, Trash2, Move, RotateCcw, Maximize2 } from "lucide-react";

import { stickerPresets } from "../../data/stickerPresets";
import type { StickerPreset } from "../../data/stickerPresets";
import type { DesignConfig, ExportPackage, ModelAsset } from "../../types";

type EditorPanelsProps = {
  config: DesignConfig | null;
  modelAsset: ModelAsset | null;
  designName: string;
  isSaving: boolean;
  exportPackage: ExportPackage | null;
  activeLayerId: string | null;
  meshBounds: { center: [number, number, number]; size: [number, number, number] } | null;
  gizmoMode: "translate" | "rotate" | "scale";
  onNameChange: (name: string) => void;
  onConfigChange: (config: DesignConfig) => void;
  onActiveLayerChange: (id: string | null) => void;
  onGizmoModeChange: (mode: "translate" | "rotate" | "scale") => void;
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
  meshBounds,
  gizmoMode,
  onNameChange,
  onConfigChange,
  onActiveLayerChange,
  onGizmoModeChange,
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

  const [activeCategory, setActiveCategory] = useState<string>("all");

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

  function removeLayer(id: string) {
    if (config!.stickers.find((s) => s.id === id)) {
      update({ stickers: config!.stickers.filter((s) => s.id !== id) });
    } else if (config!.texts.find((t) => t.id === id)) {
      update({ texts: config!.texts.filter((t) => t.id !== id) });
    }
    if (activeLayerId === id) {
      onActiveLayerChange(null);
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
        <h3>Decals & Text</h3>
        <div className="button-row">
          <button type="button" onClick={() => {
            const newConfig = addText(config, meshBounds);
            onConfigChange(newConfig);
            onActiveLayerChange(newConfig.texts[newConfig.texts.length - 1].id);
          }}>
            <Type size={16} aria-hidden="true" />
            Add Text
          </button>
        </div>
        <div className="sticker-gallery-container">
          <div className="category-tabs">
            <button className={activeCategory === "all" ? "active" : ""} onClick={() => setActiveCategory("all")}>All</button>
            <button className={activeCategory === "popular" ? "active" : ""} onClick={() => setActiveCategory("popular")}>Popular</button>
            <button className={activeCategory === "symbols" ? "active" : ""} onClick={() => setActiveCategory("symbols")}>Symbols</button>
            <button className={activeCategory === "nature" ? "active" : ""} onClick={() => setActiveCategory("nature")}>Nature</button>
            <button className={activeCategory === "sport" ? "active" : ""} onClick={() => setActiveCategory("sport")}>Sport</button>
          </div>
          <div className="sticker-gallery">
            {stickerPresets
              .filter(p => activeCategory === "all" || p.category === activeCategory)
              .map(preset => (
                <button
                  key={preset.id}
                  className="sticker-card"
                  title={preset.label}
                  onClick={() => {
                    const newConfig = addSticker(config, preset, meshBounds);
                    onConfigChange(newConfig);
                    onActiveLayerChange(newConfig.stickers[newConfig.stickers.length - 1].id);
                  }}
                >
                  <img src={preset.imageUrl} alt={preset.label} />
                </button>
              ))}
          </div>
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
              <div className="layer-info">
                <img src={sticker.imageUrl} className="sticker-thumb" alt="sticker" />
                <span>{sticker.id}</span>
              </div>
              <button type="button" className="delete-btn" title="Delete layer" onClick={(e) => { e.stopPropagation(); removeLayer(sticker.id); }}>
                <Trash2 size={14} aria-hidden="true" />
              </button>
            </div>
          ))}
          {config.texts.map((textLayer) => (
            <div
              className={`layer-row ${activeLayerId === textLayer.id ? "active" : ""}`}
              key={textLayer.id}
              onClick={() => onActiveLayerChange(textLayer.id)}
            >
              <div className="layer-info">
                <div className="color-swatch" style={{ backgroundColor: textLayer.color }} />
                <span>{textLayer.value}</span>
              </div>
              <button type="button" className="delete-btn" title="Delete layer" onClick={(e) => { e.stopPropagation(); removeLayer(textLayer.id); }}>
                <Trash2 size={14} aria-hidden="true" />
              </button>
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
          <div className="button-row gizmo-toolbar">
            <button
              type="button"
              className={gizmoMode === "translate" ? "active" : ""}
              onClick={() => onGizmoModeChange("translate")}
              title="Move (3D)"
            >
              <Move size={16} />
            </button>
            <button
              type="button"
              className={gizmoMode === "rotate" ? "active" : ""}
              onClick={() => onGizmoModeChange("rotate")}
              title="Rotate (3D)"
            >
              <RotateCcw size={16} />
            </button>
            <button
              type="button"
              className={gizmoMode === "scale" ? "active" : ""}
              onClick={() => onGizmoModeChange("scale")}
              title="Scale (3D)"
            >
              <Maximize2 size={16} />
            </button>
          </div>
          {activeText && (
            <>
              <label>
                Text
                <input
                  value={activeText.value}
                  onChange={(e) => updateLayer(activeLayer.id, { value: e.target.value })}
                />
              </label>
              <label className="color-picker-row">
                Color
                <div className="color-input-wrapper">
                  <input
                    type="color"
                    value={activeText.color}
                    onChange={(e) => updateLayer(activeLayer.id, { color: e.target.value })}
                  />
                  <span>{activeText.color.toUpperCase()}</span>
                </div>
              </label>
            </>
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

function addSticker(config: DesignConfig, preset: StickerPreset, meshBounds: { center: [number, number, number]; size: [number, number, number] } | null): DesignConfig {
  const index = config.stickers.length + 1;
  const c = meshBounds ? meshBounds.center : [0, 0, 0];
  const s = meshBounds ? meshBounds.size : [1, 1, 1];
  const stickerScale = Math.max(s[0], s[1], s[2]) * 0.15;

  return {
    ...config,
    stickers: [
      ...config.stickers,
      {
        id: `sticker_${String(index).padStart(3, "0")}`,
        type: "image",
        imageUrl: preset.imageUrl,
        position: [c[0] + s[0] * 0.4, c[1], c[2]],
        rotation: [0, 1.57, 0],
        scale: stickerScale,
      },
    ],
  };
}

function addText(config: DesignConfig, meshBounds: { center: [number, number, number]; size: [number, number, number] } | null): DesignConfig {
  const index = config.texts.length + 1;
  const c = meshBounds ? meshBounds.center : [0, 0, 0];
  const s = meshBounds ? meshBounds.size : [1, 1, 1];
  const scale = Math.max(s[0], s[1], s[2]) * 0.1;

  return {
    ...config,
    texts: [
      ...config.texts,
      {
        id: `text_${String(index).padStart(3, "0")}`,
        value: "TAK",
        font: "Arial",
        color: "#ffffff",
        position: [c[0] + s[0] * 0.4, c[1] + s[1] * 0.1, c[2] + s[2] * 0.1],
        rotation: [0, 1.57, 0],
        scale: scale,
      },
    ],
  };
}
