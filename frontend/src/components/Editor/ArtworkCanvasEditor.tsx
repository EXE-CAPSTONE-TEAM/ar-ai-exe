import { Brush, Check, Eraser, Redo2, Trash2, Undo2 } from "lucide-react";
import { PointerEvent, useEffect, useRef, useState } from "react";

const CANVAS_SIZE = 512;
const MAX_HISTORY = 24;

type DrawingTool = "brush" | "eraser";

type ArtworkCanvasEditorProps = {
  disabled: boolean;
  onExport: (file: File) => Promise<void>;
};

export function ArtworkCanvasEditor({ disabled, onExport }: ArtworkCanvasEditorProps) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const drawingRef = useRef(false);
  const lastPointRef = useRef<{ x: number; y: number } | null>(null);
  const [tool, setTool] = useState<DrawingTool>("brush");
  const [color, setColor] = useState("#111827");
  const [brushSize, setBrushSize] = useState(18);
  const [undoStack, setUndoStack] = useState<ImageData[]>([]);
  const [redoStack, setRedoStack] = useState<ImageData[]>([]);
  const [isExporting, setIsExporting] = useState(false);
  const toolRef = useRef(tool);
  const colorRef = useRef(color);
  const brushSizeRef = useRef(brushSize);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    canvas.width = CANVAS_SIZE;
    canvas.height = CANVAS_SIZE;
  }, []);

  useEffect(() => {
    toolRef.current = tool;
  }, [tool]);

  useEffect(() => {
    colorRef.current = color;
  }, [color]);

  useEffect(() => {
    brushSizeRef.current = brushSize;
  }, [brushSize]);

  const canvasContext = (): CanvasRenderingContext2D | null => {
    const canvas = canvasRef.current;
    return canvas?.getContext("2d", { willReadFrequently: true }) ?? null;
  };

  const snapshot = () => {
    const context = canvasContext();
    if (!context) return;
    const imageData = context.getImageData(0, 0, CANVAS_SIZE, CANVAS_SIZE);
    setUndoStack((items) => [...items.slice(-(MAX_HISTORY - 1)), imageData]);
    setRedoStack([]);
  };

  const canvasPoint = (event: PointerEvent<HTMLCanvasElement>) => {
    const canvas = event.currentTarget;
    const rect = canvas.getBoundingClientRect();
    return {
      x: ((event.clientX - rect.left) / rect.width) * CANVAS_SIZE,
      y: ((event.clientY - rect.top) / rect.height) * CANVAS_SIZE,
    };
  };

  const drawTo = (point: { x: number; y: number }) => {
    const context = canvasContext();
    if (!context) return;

    const previous = lastPointRef.current ?? point;
    context.save();
    context.lineCap = "round";
    context.lineJoin = "round";
    context.lineWidth = brushSizeRef.current;
    context.globalCompositeOperation = toolRef.current === "eraser" ? "destination-out" : "source-over";
    context.strokeStyle = colorRef.current;
    context.beginPath();
    context.moveTo(previous.x, previous.y);
    context.lineTo(point.x, point.y);
    context.stroke();
    context.restore();
    lastPointRef.current = point;
  };

  const startDrawing = (event: PointerEvent<HTMLCanvasElement>) => {
    if (disabled) return;
    event.currentTarget.setPointerCapture(event.pointerId);
    snapshot();
    drawingRef.current = true;
    lastPointRef.current = canvasPoint(event);
    drawTo(lastPointRef.current);
  };

  const continueDrawing = (event: PointerEvent<HTMLCanvasElement>) => {
    if (!drawingRef.current || disabled) return;
    drawTo(canvasPoint(event));
  };

  const stopDrawing = (event: PointerEvent<HTMLCanvasElement>) => {
    if (event.currentTarget.hasPointerCapture(event.pointerId)) {
      event.currentTarget.releasePointerCapture(event.pointerId);
    }
    drawingRef.current = false;
    lastPointRef.current = null;
  };

  const applyImageData = (imageData: ImageData) => {
    const context = canvasContext();
    if (!context) return;
    context.putImageData(imageData, 0, 0);
  };

  const undo = () => {
    const context = canvasContext();
    if (!context || undoStack.length === 0) return;
    const current = context.getImageData(0, 0, CANVAS_SIZE, CANVAS_SIZE);
    const previous = undoStack[undoStack.length - 1];
    setUndoStack((items) => items.slice(0, -1));
    setRedoStack((items) => [...items, current]);
    applyImageData(previous);
  };

  const redo = () => {
    const context = canvasContext();
    if (!context || redoStack.length === 0) return;
    const current = context.getImageData(0, 0, CANVAS_SIZE, CANVAS_SIZE);
    const next = redoStack[redoStack.length - 1];
    setRedoStack((items) => items.slice(0, -1));
    setUndoStack((items) => [...items, current]);
    applyImageData(next);
  };

  const clearCanvas = () => {
    const context = canvasContext();
    if (!context) return;
    snapshot();
    context.clearRect(0, 0, CANVAS_SIZE, CANVAS_SIZE);
  };

  const exportCanvas = async () => {
    const canvas = canvasRef.current;
    if (!canvas || disabled || isExporting) return;
    setIsExporting(true);
    try {
      const blob = await new Promise<Blob>((resolve, reject) => {
        canvas.toBlob((value) => (value ? resolve(value) : reject(new Error("Canvas export failed."))), "image/png");
      });
      await onExport(new File([blob], `artwork-${Date.now()}.png`, { type: "image/png" }));
    } finally {
      setIsExporting(false);
    }
  };

  const updateColor = (nextColor: string) => {
    colorRef.current = nextColor;
    setColor(nextColor);
  };

  const updateTool = (nextTool: DrawingTool) => {
    toolRef.current = nextTool;
    setTool(nextTool);
  };

  const updateBrushSize = (nextBrushSize: number) => {
    brushSizeRef.current = nextBrushSize;
    setBrushSize(nextBrushSize);
  };

  return (
    <div className="artwork-editor">
      <div className="artwork-toolbar">
        <button
          type="button"
          className={tool === "brush" ? "active" : ""}
          disabled={disabled}
          title="Brush"
          onClick={() => updateTool("brush")}
        >
          <Brush size={16} aria-hidden="true" />
        </button>
        <button
          type="button"
          className={tool === "eraser" ? "active" : ""}
          disabled={disabled}
          title="Eraser"
          onClick={() => updateTool("eraser")}
        >
          <Eraser size={16} aria-hidden="true" />
        </button>
        <button type="button" disabled={disabled || undoStack.length === 0} title="Undo" onClick={undo}>
          <Undo2 size={16} aria-hidden="true" />
        </button>
        <button type="button" disabled={disabled || redoStack.length === 0} title="Redo" onClick={redo}>
          <Redo2 size={16} aria-hidden="true" />
        </button>
        <button type="button" disabled={disabled} title="Clear" onClick={clearCanvas}>
          <Trash2 size={16} aria-hidden="true" />
        </button>
      </div>

      <div className="artwork-canvas-frame">
        <canvas
          ref={canvasRef}
          aria-label="Artwork drawing canvas"
          onPointerDown={startDrawing}
          onPointerMove={continueDrawing}
          onPointerUp={stopDrawing}
          onPointerCancel={stopDrawing}
        />
      </div>

      <div className="artwork-control-grid">
        <label className="color-picker-row">
          Color
          <div className="color-input-wrapper">
            <input
              type="color"
              value={color}
              disabled={disabled}
              onInput={(event) => updateColor(event.currentTarget.value)}
              onChange={(event) => updateColor(event.currentTarget.value)}
            />
            <span>{color.toUpperCase()}</span>
          </div>
        </label>
        <label>
          Size
          <input
            type="range"
            min="2"
            max="64"
            step="1"
            value={brushSize}
            disabled={disabled}
            onInput={(event) => updateBrushSize(Number(event.currentTarget.value))}
            onChange={(event) => updateBrushSize(Number(event.currentTarget.value))}
          />
        </label>
      </div>

      <button type="button" className="primary-button" disabled={disabled || isExporting} onClick={exportCanvas}>
        <Check size={16} aria-hidden="true" />
        Add artwork
      </button>
    </div>
  );
}
