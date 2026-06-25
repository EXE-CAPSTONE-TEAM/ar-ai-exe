import { useRef, useState } from "react";
import {
  Crosshair,
  Cpu,
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
  isBakingPreview: boolean;
  isExporting: boolean;
  canEdit: boolean;
  canBake: boolean;
  canExport: boolean;
  exportMessage: string | null;
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
  onBakePreview: () => void;
  onExport: () => void;
  onDownload: () => void;
  onDownloadModelFile: (urlPath: string, filename: string) => void;
  onUploadDesignAsset: (
    file: File,
    sourceType: ArtworkAssetSource,
  ) => Promise<UploadedDesignAssetPreview>;
  simplified?: boolean;
};

export function EditorPanels({
  config,
  modelAsset,
  designName,
  isSaving,
  isBakingPreview,
  isExporting,
  canEdit,
  canBake,
  canExport,
  exportMessage,
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
  onBakePreview,
  onExport,
  onDownload,
  onDownloadModelFile,
  onUploadDesignAsset,
  simplified = false,
}: EditorPanelsProps) {
  const [activeCategory, setActiveCategory] = useState<string>("all");
  const [isArtworkEditorOpen, setIsArtworkEditorOpen] = useState(false);
  const [isUploadingArtwork, setIsUploadingArtwork] = useState(false);
  const [artworkMessage, setArtworkMessage] = useState<string | null>(null);
  const artworkInputRef = useRef<HTMLInputElement | null>(null);

  if (!config) {
    return (
      <aside className="editor-panel">
        <section className="panel-section">
          <div className="empty-panel-callout">
            <ImagePlus size={22} aria-hidden="true" />
            <div>
              <h2>Design tools are locked</h2>
              <p>Load a completed scan or import a model to start adding artwork.</p>
            </div>
          </div>
        </section>
      </aside>
    );
  }

  const update = (patch: Partial<DesignConfig>) => onConfigChange({ ...config, ...patch });

  const activeSticker = config.stickers.find((s) => s.id === activeLayerId);
  const activeText = config.texts.find((t) => t.id === activeLayerId);
  const activeLayer = activeSticker || activeText;
  const activeLayerIsApplied = Boolean(activeLayer?.targetMeshName);
  const isDesignBusy = isSaving || isBakingPreview || isExporting || !canEdit;
  const isArtworkBusy = isDesignBusy || isUploadingArtwork;

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
        <div className="section-heading">
          <PenLine size={18} aria-hidden="true" />
          <div>
            <h2>Design Tools</h2>
            {!simplified ? <p className="muted">Name the draft before saving it.</p> : null}
          </div>
        </div>
        <label>
          Draft name
          <input value={designName} disabled={!canEdit || isSaving || isBakingPreview || isExporting} onChange={(event) => onNameChange(event.target.value)} />
        </label>
      </section>

      <section className="panel-section">
        <div className="section-heading">
          <ImagePlus size={18} aria-hidden="true" />
          <div>
            <h3>{simplified ? "Artwork" : "Decals & Text"}</h3>
            {!simplified ? <p className="muted">Add the artwork first, then place it on the model.</p> : null}
          </div>
        </div>
        {!simplified ? <div className="decal-guidance">
          <ImagePlus size={18} aria-hidden="true" />
          <ol className="mini-guide-list">
            <li>Add text, upload an image, draw artwork, or choose a preset.</li>
            <li>Select the layer, then apply it to the shoe surface.</li>
            <li>Save the draft first, then bake the preview when you need a rendered check.</li>
          </ol>
        </div> : null}
        <div className="button-row">
          <button type="button" disabled={isDesignBusy} onClick={() => {
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
            disabled={isDesignBusy}
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
            {stickerCategoryTabs.map((category) => (
              <button
                type="button"
                className={activeCategory === category.id ? "active" : ""}
                key={category.id}
                onClick={() => setActiveCategory(category.id)}
              >
                {category.label}
              </button>
            ))}
          </div>
          <div className="sticker-gallery">
            {stickerPresets
              .filter(p => activeCategory === "all" || p.category === activeCategory)
              .map(preset => (
                <button
                  key={preset.id}
                  className="sticker-card"
                  title={preset.label}
                  disabled={isDesignBusy}
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
        <div className="section-heading">
          <Type size={18} aria-hidden="true" />
          <div>
            <h3>Layers</h3>
            {!simplified ? <p className="muted">Select a layer to edit its placement and style.</p> : null}
          </div>
        </div>
        <div className="layer-list" onClick={(e) => {
          if (e.target === e.currentTarget) onActiveLayerChange(null);
        }}>
          {config.stickers.map((sticker) => (
            <div
              className={`layer-row ${activeLayerId === sticker.id ? "active" : ""}`}
              key={sticker.id}
              role="button"
              tabIndex={0}
              onClick={() => onActiveLayerChange(sticker.id)}
              onKeyDown={(event) => {
                if (event.key === "Enter" || event.key === " ") {
                  event.preventDefault();
                  onActiveLayerChange(sticker.id);
                }
              }}
            >
              <div className="layer-info">
                {stickerThumbUrl(sticker) ? (
                  <img src={stickerThumbUrl(sticker)} className="sticker-thumb" alt="sticker" />
                ) : (
                  <div className="color-swatch" />
                )}
                <span>{stickerLayerLabel(sticker)}</span>
              </div>
              <button type="button" className="delete-btn" title="Delete layer" disabled={isDesignBusy} onClick={(e) => { e.stopPropagation(); removeLayer(sticker.id); }}>
                <Trash2 size={14} aria-hidden="true" />
              </button>
            </div>
          ))}
          {config.texts.map((textLayer) => (
            <div
              className={`layer-row ${activeLayerId === textLayer.id ? "active" : ""}`}
              key={textLayer.id}
              role="button"
              tabIndex={0}
              onClick={() => onActiveLayerChange(textLayer.id)}
              onKeyDown={(event) => {
                if (event.key === "Enter" || event.key === " ") {
                  event.preventDefault();
                  onActiveLayerChange(textLayer.id);
                }
              }}
            >
              <div className="layer-info">
                <div className="color-swatch" style={{ backgroundColor: textLayer.color }} />
                <span>{textLayer.value}</span>
              </div>
              <button type="button" className="delete-btn" title="Delete layer" disabled={isDesignBusy} onClick={(e) => { e.stopPropagation(); removeLayer(textLayer.id); }}>
                <Trash2 size={14} aria-hidden="true" />
              </button>
            </div>
          ))}
          {config.stickers.length === 0 && config.texts.length === 0 ? (
            <div className="empty-layer-state">
              <ImagePlus size={18} aria-hidden="true" />
              <strong>No layers yet</strong>
              <span>Add text or artwork. New layers appear here.</span>
            </div>
          ) : null}
        </div>
      </section>

      {activeLayer && (
        <section className="panel-section highlight">
          <div className="section-heading">
            <Crosshair size={18} aria-hidden="true" />
            <div>
              <h3>{simplified ? "Placement" : "Layer Properties"}</h3>
              {!simplified ? <p className="muted">Use the familiar move, rotate, and scale order.</p> : null}
            </div>
          </div>
          <div className="button-row gizmo-toolbar">
            <button
              type="button"
              className={gizmoMode === "translate" ? "active" : ""}
              aria-label="Move selected layer"
              aria-pressed={gizmoMode === "translate"}
              disabled={isDesignBusy}
              onClick={() => onGizmoModeChange("translate")}
              title="Move (3D)"
            >
              <Move size={16} />
            </button>
            <button
              type="button"
              className={gizmoMode === "rotate" ? "active" : ""}
              aria-label="Rotate selected layer"
              aria-pressed={gizmoMode === "rotate"}
              disabled={isDesignBusy}
              onClick={() => onGizmoModeChange("rotate")}
              title="Rotate (3D)"
            >
              <RotateCcw size={16} />
            </button>
            <button
              type="button"
              className={gizmoMode === "scale" ? "active" : ""}
              aria-label="Scale selected layer"
              aria-pressed={gizmoMode === "scale"}
              disabled={isDesignBusy}
              onClick={() => onGizmoModeChange("scale")}
              title="Scale (3D)"
            >
              <Maximize2 size={16} />
            </button>
            <button
              type="button"
              className="apply-surface-button"
              aria-label="Apply selected layer to the shoe surface"
              disabled={isDesignBusy}
              onClick={onApplyActiveLayerToSurface}
              title={simplified ? "Snap to shoe" : "Apply to surface"}
            >
              <Crosshair size={16} />
              {simplified
                ? activeLayerIsApplied ? "Snap again" : "Snap to Shoe"
                : activeLayerIsApplied ? "Reapply to surface" : "Apply to surface"}
            </button>
          </div>
          {!simplified ? <span className={`surface-status-line ${activeLayerIsApplied ? "applied" : "blocked"}`}>
            {activeLayerIsApplied
              ? `Applied to ${activeLayer?.targetMeshName}`
              : "Positioned manually. Apply to surface to snap it onto the shoe."}
          </span> : null}
          {activeText && (
            <>
              <label>
                Text
                <input
                  value={activeText.value}
                  disabled={isDesignBusy}
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
                  disabled={isDesignBusy}
                  onChange={(e) => updateLayer(activeLayer.id, { font: e.target.value, renderAssetId: undefined })}
                >
                  {fontChoices(activeText.font).map((font) => (
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
                    disabled={isDesignBusy}
                    onChange={(e) => updateLayer(activeLayer.id, { color: e.target.value, renderAssetId: undefined })}
                  />
                  <span>{activeText.color.toUpperCase()}</span>
                </div>
              </label>
            </>
          )}
          {!simplified ? <label>
            Scale
            <input
              type="range"
              min="0.05"
              max="2"
              step="0.05"
              value={activeLayer.scale}
              disabled={isDesignBusy}
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
          </label> : null}
          {!simplified ? <label>
            Rotation
            <input
              type="range"
              min="-3.14"
              max="3.14"
              step="0.05"
              value={activeLayer.rotation[2]}
              disabled={isDesignBusy}
              onChange={(e) => {
                const rot = [...activeLayer.rotation];
                rot[2] = Number(e.target.value);
                updateLayer(activeLayer.id, { rotation: rot as [number, number, number] });
              }}
            />
          </label> : null}
        </section>
      )}

      {!simplified ? <section className="panel-section action-stack" id="export-tools">
        <div className="section-heading">
          <Save size={18} aria-hidden="true" />
          <div>
            <h3>Save & Export</h3>
            <p className="muted">Export creates the ZIP and starts the download automatically.</p>
          </div>
        </div>
        <button className="primary-button" type="button" disabled={isSaving || isBakingPreview || isExporting || !canEdit} onClick={onSave}>
          <Save size={16} aria-hidden="true" />
          {isSaving ? "Saving..." : "Save Draft"}
        </button>
        <button type="button" disabled={isSaving || isBakingPreview || isExporting || !canEdit || !canBake} onClick={onBakePreview}>
          <Cpu size={16} aria-hidden="true" />
          {isBakingPreview ? "Baking..." : "Bake Preview"}
        </button>
        <button type="button" disabled={isSaving || isBakingPreview || isExporting || !canExport} onClick={onExport}>
          <Download size={16} aria-hidden="true" />
          {isExporting ? "Creating ZIP..." : "Export & Download ZIP"}
        </button>
        {exportPackage ? (
          <button type="button" disabled={isSaving || isBakingPreview || isExporting || !canExport} onClick={onDownload}>
            <Download size={16} aria-hidden="true" />
            Download ZIP again
          </button>
        ) : null}
        {exportMessage ? (
          <span className="export-status-line" role="status" aria-live="polite">
            {exportMessage}
          </span>
        ) : null}
      </section> : null}

      {modelAsset && !simplified ? (
        <section className="panel-section">
          <div className="section-heading">
            <Download size={18} aria-hidden="true" />
            <div>
              <h3>Reconstruction Files</h3>
              <p className="muted">Download source model files when needed.</p>
            </div>
          </div>
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
  const defaultValue = "KICKS";

  return {
    ...config,
    texts: [
      ...config.texts,
      {
        id: `text_${String(index).padStart(3, "0")}`,
        value: defaultValue,
        font: "Bahnschrift",
        color: "#ffffff",
        position: [c[0] + s[0] * 0.4, c[1] + s[1] * 0.1, c[2] + s[2] * 0.1],
        rotation: [0, 1.57, 0],
        scale: scale,
        width: scale * textAspect(defaultValue),
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

const stickerCategoryTabs = [
  { id: "all", label: "All" },
  { id: "popular", label: "Featured" },
  { id: "street", label: "Street" },
  { id: "racing", label: "Racing" },
  { id: "marks", label: "Marks" },
  { id: "type", label: "Type" },
];

const fontOptions = [
  "Bahnschrift",
  "Agency FB",
  "Impact",
  "Arial Black",
  "Haettenschweiler",
  "Stencil",
  "Copperplate Gothic Bold",
  "Segoe Script",
  "Brush Script MT",
  "Lucida Handwriting",
  "Freestyle Script",
  "Segoe Print",
];

function fontChoices(currentFont: string): string[] {
  return fontOptions.includes(currentFont) ? fontOptions : [currentFont, ...fontOptions];
}
