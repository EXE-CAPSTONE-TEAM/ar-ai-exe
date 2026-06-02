import { useRef, useState } from "react";
import {
  Crosshair,
  Download,
  ImagePlus,
  Maximize2,
  Move,
  PenLine,
  RotateCcw,
  Save,
  Type,
  Trash2,
  Upload,
} from "lucide-react";

import { stickerPresets } from "../../data/stickerPresets";
import type { StickerPreset } from "../../data/stickerPresets";
import type { DesignAssetSource, DesignConfig, ExportPackage, ModelAsset, StickerLayer } from "../../types";
import { ArtworkCanvasEditor } from "./ArtworkCanvasEditor";

const MAX_ARTWORK_FILE_BYTES = 5 * 1024 * 1024;
type ArtworkAssetSource = Extract<DesignAssetSource, "upload" | "canvas">;

export type UploadedDesignAssetPreview = {
  assetId: string;
  sourceType: ArtworkAssetSource;
  fileName: string;
  previewUrl: string;
};

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
  onApplyActiveLayerToSurface: () => void;
  onGizmoModeChange: (mode: "translate" | "rotate" | "scale") => void;
  onSave: () => void;
  onExport: () => void;
  onDownload: () => void;
  onDownloadModelFile: (urlPath: string, filename: string) => void;
  onUploadDesignAsset: (
    file: File,
    sourceType: ArtworkAssetSource,
  ) => Promise<UploadedDesignAssetPreview>;
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
  onApplyActiveLayerToSurface,
  onGizmoModeChange,
  onSave,
  onExport,
  onDownload,
  onDownloadModelFile,
  onUploadDesignAsset,
}: EditorPanelsProps) {
  const [activeCategory, setActiveCategory] = useState<string>("all");
  const [isArtworkEditorOpen, setIsArtworkEditorOpen] = useState(false);
  const [isUploadingArtwork, setIsUploadingArtwork] = useState(false);
  const [artworkMessage, setArtworkMessage] = useState<string | null>(null);
  const artworkInputRef = useRef<HTMLInputElement | null>(null);

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
  const isArtworkBusy = isSaving || isUploadingArtwork;

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

  async function addArtworkFromFile(file: File, sourceType: ArtworkAssetSource) {
    if (!config) {
      return;
    }
    const clientError = validateArtworkFile(file);
    if (clientError) {
      setArtworkMessage(clientError);
      return;
    }

    setIsUploadingArtwork(true);
    setArtworkMessage(sourceType === "canvas" ? "Saving artwork" : "Uploading artwork");
    try {
      const uploaded = await onUploadDesignAsset(file, sourceType);
      const newConfig = addArtworkSticker(config, uploaded, meshBounds);
      onConfigChange(newConfig);
      onActiveLayerChange(newConfig.stickers[newConfig.stickers.length - 1].id);
      setArtworkMessage(sourceType === "canvas" ? "Artwork added" : "Image added");
    } catch (error) {
      setArtworkMessage(error instanceof Error ? error.message : "Artwork upload failed.");
    } finally {
      setIsUploadingArtwork(false);
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
        <h3>Decals & Text</h3>
        <div className="decal-guidance">
          <ImagePlus size={18} aria-hidden="true" />
          <p>Thêm sticker hoặc text, kéo sát bề mặt giày nhất có thể, rồi bấm Save Draft để áp ảnh vào giày.</p>
        </div>
        <div className="button-row">
          <button type="button" disabled={isSaving} onClick={() => {
            const newConfig = addText(config, meshBounds);
            onConfigChange(newConfig);
            onActiveLayerChange(newConfig.texts[newConfig.texts.length - 1].id);
          }}>
            <Type size={16} aria-hidden="true" />
            Add Text
          </button>
        </div>
        <div className="artwork-actions">
          <input
            ref={artworkInputRef}
            type="file"
            accept="image/png,image/jpeg"
            className="sr-only"
            disabled={isArtworkBusy}
            onChange={(event) => {
              const file = event.target.files?.[0];
              event.target.value = "";
              if (file) void addArtworkFromFile(file, "upload");
            }}
          />
          <button type="button" disabled={isArtworkBusy} onClick={() => artworkInputRef.current?.click()}>
            <Upload size={16} aria-hidden="true" />
            Upload image
          </button>
          <button
            type="button"
            className={isArtworkEditorOpen ? "active" : ""}
            disabled={isSaving}
            onClick={() => setIsArtworkEditorOpen((value) => !value)}
          >
            <PenLine size={16} aria-hidden="true" />
            Draw artwork
          </button>
        </div>
        {artworkMessage ? <span className="status-line">{artworkMessage}</span> : null}
        {isArtworkEditorOpen ? (
          <ArtworkCanvasEditor
            disabled={isArtworkBusy}
            onExport={(file) => addArtworkFromFile(file, "canvas")}
          />
        ) : null}
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
                  disabled={isSaving}
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
                {stickerThumbUrl(sticker) ? (
                  <img src={stickerThumbUrl(sticker)} className="sticker-thumb" alt="sticker" />
                ) : (
                  <div className="color-swatch" />
                )}
                <span>{stickerLayerLabel(sticker)}</span>
              </div>
              <button type="button" className="delete-btn" title="Delete layer" disabled={isSaving} onClick={(e) => { e.stopPropagation(); removeLayer(sticker.id); }}>
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
              <button type="button" className="delete-btn" title="Delete layer" disabled={isSaving} onClick={(e) => { e.stopPropagation(); removeLayer(textLayer.id); }}>
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
              disabled={isSaving}
              onClick={() => onGizmoModeChange("translate")}
              title="Move (3D)"
            >
              <Move size={16} />
            </button>
            <button
              type="button"
              className={gizmoMode === "rotate" ? "active" : ""}
              disabled={isSaving}
              onClick={() => onGizmoModeChange("rotate")}
              title="Rotate (3D)"
            >
              <RotateCcw size={16} />
            </button>
            <button
              type="button"
              className={gizmoMode === "scale" ? "active" : ""}
              disabled={isSaving}
              onClick={() => onGizmoModeChange("scale")}
              title="Scale (3D)"
            >
              <Maximize2 size={16} />
            </button>
            <button
              type="button"
              className="apply-surface-button"
              disabled={isSaving}
              onClick={onApplyActiveLayerToSurface}
              title="Apply to surface"
            >
              <Crosshair size={16} />
              Apply to surface
            </button>
          </div>
          {activeText && (
            <>
              <label>
                Text
                <input
                  value={activeText.value}
                  disabled={isSaving}
                  maxLength={80}
                  onChange={(e) =>
                    updateLayer(activeLayer.id, {
                      value: e.target.value,
                      width: activeText.scale * textAspect(e.target.value),
                      renderAssetId: undefined,
                    })
                  }
                />
              </label>
              <label>
                Font
                <select
                  value={activeText.font}
                  disabled={isSaving}
                  onChange={(e) => updateLayer(activeLayer.id, { font: e.target.value, renderAssetId: undefined })}
                >
                  {fontOptions.map((font) => (
                    <option value={font} key={font}>
                      {font}
                    </option>
                  ))}
                </select>
              </label>
              <label className="color-picker-row">
                Color
                <div className="color-input-wrapper">
                  <input
                    type="color"
                    value={activeText.color}
                    disabled={isSaving}
                    onChange={(e) => updateLayer(activeLayer.id, { color: e.target.value, renderAssetId: undefined })}
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
              disabled={isSaving}
              onChange={(e) => {
                const scale = Number(e.target.value);
                updateLayer(
                  activeLayer.id,
                  activeSticker
                    ? {
                        scale,
                        width: scale,
                        height: scale,
                        projectionDepth: Math.max(activeSticker.projectionDepth ?? 0, scale * 3, 0.05),
                      }
                    : {
                        scale,
                        width: scale * textAspect(activeText?.value ?? ""),
                        height: scale,
                        projectionDepth: Math.max(activeText?.projectionDepth ?? 0, scale * 3, 0.05),
                      },
                );
              }}
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
              disabled={isSaving}
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
          {isSaving ? "Applying..." : "Save Draft"}
        </button>
        <button type="button" disabled={isSaving} onClick={onExport}>
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
  const maxModelSize = Math.max(s[0], s[1], s[2]);
  const stickerScale = maxModelSize * 0.15;

  return {
    ...config,
    stickers: [
      ...config.stickers,
      {
        id: `sticker_${String(index).padStart(3, "0")}`,
        type: "image",
        source: "preset",
        imageUrl: preset.imageUrl,
        position: [c[0] + s[0] * 0.4, c[1], c[2]],
        rotation: [0, 1.57, 0],
        normal: [1, 0, 0],
        targetMeshName: null,
        scale: stickerScale,
        width: stickerScale,
        height: stickerScale,
        offset: 0.004,
        projectionDepth: Math.max(maxModelSize * 1.25, stickerScale * 2, 0.05),
        subdivisions: 32,
      },
    ],
  };
}

function addArtworkSticker(
  config: DesignConfig,
  uploaded: UploadedDesignAssetPreview,
  meshBounds: { center: [number, number, number]; size: [number, number, number] } | null,
): DesignConfig {
  const index = config.stickers.length + 1;
  const c = meshBounds ? meshBounds.center : [0, 0, 0];
  const s = meshBounds ? meshBounds.size : [1, 1, 1];
  const maxModelSize = Math.max(s[0], s[1], s[2]);
  const stickerScale = maxModelSize * 0.15;

  return {
    ...config,
    stickers: [
      ...config.stickers,
      {
        id: `artwork_${String(index).padStart(3, "0")}`,
        type: "image",
        source: uploaded.sourceType,
        assetId: uploaded.assetId,
        previewUrl: uploaded.previewUrl,
        position: [c[0] + s[0] * 0.4, c[1], c[2]],
        rotation: [0, 1.57, 0],
        normal: [1, 0, 0],
        targetMeshName: null,
        scale: stickerScale,
        width: stickerScale,
        height: stickerScale,
        offset: 0.004,
        projectionDepth: Math.max(maxModelSize * 1.25, stickerScale * 2, 0.05),
        subdivisions: 32,
      },
    ],
  };
}

function addText(config: DesignConfig, meshBounds: { center: [number, number, number]; size: [number, number, number] } | null): DesignConfig {
  const index = config.texts.length + 1;
  const c = meshBounds ? meshBounds.center : [0, 0, 0];
  const s = meshBounds ? meshBounds.size : [1, 1, 1];
  const maxModelSize = Math.max(s[0], s[1], s[2]);
  const scale = maxModelSize * 0.1;

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
        width: scale * 1.9,
        height: scale,
        offset: 0.004,
        projectionDepth: Math.max(maxModelSize * 1.25, scale * 2, 0.05),
        subdivisions: 32,
        targetMeshName: null,
      },
    ],
  };
}

function textAspect(value: string): number {
  return Math.max(value.trim().length * 0.62, 1);
}

function validateArtworkFile(file: File): string | null {
  if (!["image/png", "image/jpeg"].includes(file.type)) {
    return "Artwork must be a PNG or JPEG image.";
  }
  if (file.size > MAX_ARTWORK_FILE_BYTES) {
    return "Artwork image must be 5 MB or smaller.";
  }
  return null;
}

function stickerThumbUrl(sticker: StickerLayer): string | undefined {
  return sticker.previewUrl ?? sticker.imageUrl;
}

function stickerLayerLabel(sticker: StickerLayer): string {
  if (sticker.source === "canvas") return "Drawn artwork";
  if (sticker.source === "upload") return "Uploaded image";
  return sticker.id;
}

const fontOptions = [
  "Arial",
  "Helvetica",
  "Georgia",
  "Times New Roman",
  "Courier New",
  "Verdana",
  "Trebuchet MS",
  "Impact",
];
