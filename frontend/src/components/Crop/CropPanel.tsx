import {
  AlertTriangle,
  CheckCircle2,
  Crop,
  Loader2,
  Maximize2,
  Move,
  RefreshCw,
  RotateCcw,
} from "lucide-react";

export type PrepareStep = "idle" | "downloading" | "cropping" | "cleaning" | "uploading" | "done";

type CropPanelProps = {
  projectName: string;
  gizmoMode: "translate" | "rotate" | "scale";
  onGizmoModeChange: (mode: "translate" | "rotate" | "scale") => void;
  onResetCropBox: () => void;
  onPrepare: () => void;
  isPreparing: boolean;
  prepareStep: PrepareStep;
  errorMessage: string | null;
  onRetry: () => void;
  needsResetConfirmation?: boolean;
  onConfirmResetDesign?: () => void;
  onCancelResetDesign?: () => void;
  onCancelCropMode?: () => void;
};

const PREPARE_STEPS: Array<{ key: PrepareStep; label: string }> = [
  { key: "downloading", label: "Đang tải model" },
  { key: "cropping", label: "Đang cắt" },
  { key: "cleaning", label: "Đang làm sạch" },
  { key: "uploading", label: "Đang tải lên" },
  { key: "done", label: "Hoàn tất" },
];

export function CropPanel({
  projectName,
  gizmoMode,
  onGizmoModeChange,
  onResetCropBox,
  onPrepare,
  isPreparing,
  prepareStep,
  errorMessage,
  onRetry,
  needsResetConfirmation,
  onConfirmResetDesign,
  onCancelResetDesign,
  onCancelCropMode,
}: CropPanelProps) {
  const currentStepIndex = PREPARE_STEPS.findIndex((s) => s.key === prepareStep);

  return (
    <aside className="crop-panel" aria-label="Khung cắt model thô">
      <div className="crop-panel-card">
        <header className="crop-panel-header">
          <div className="crop-panel-title">
            <Crop size={18} aria-hidden="true" />
            <div>
              <h3>Chuẩn bị model</h3>
              <p className="crop-project-name">{projectName}</p>
            </div>
          </div>
        </header>

        <section className="crop-notice-warning" role="status">
          <AlertTriangle size={18} aria-hidden="true" />
          <div>
            <strong>Model thô từ scan</strong>
            <p>Cần cắt trước khi thiết kế để loại bỏ phần sàn và tạp chất xung quanh giày.</p>
          </div>
        </section>

        <section className="crop-gizmo-section">
          <div className="crop-section-title">
            <span>Công cụ chỉnh khung</span>
          </div>
          <div className="button-row gizmo-toolbar crop-toolbar">
            <button
              type="button"
              className={gizmoMode === "translate" ? "active" : ""}
              aria-label="Di chuyển khung cắt"
              aria-pressed={gizmoMode === "translate"}
              disabled={isPreparing}
              onClick={() => onGizmoModeChange("translate")}
              title="Di chuyển"
            >
              <Move size={15} aria-hidden="true" />
              <span>Di chuyển</span>
            </button>
            <button
              type="button"
              className={gizmoMode === "rotate" ? "active" : ""}
              aria-label="Xoay khung cắt"
              aria-pressed={gizmoMode === "rotate"}
              disabled={isPreparing}
              onClick={() => onGizmoModeChange("rotate")}
              title="Xoay"
            >
              <RotateCcw size={15} aria-hidden="true" />
              <span>Xoay</span>
            </button>
            <button
              type="button"
              className={gizmoMode === "scale" ? "active" : ""}
              aria-label="Co giãn khung cắt"
              aria-pressed={gizmoMode === "scale"}
              disabled={isPreparing}
              onClick={() => onGizmoModeChange("scale")}
              title="Co giãn"
            >
              <Maximize2 size={15} aria-hidden="true" />
              <span>Co giãn</span>
            </button>
            <button
              type="button"
              className="crop-reset-btn"
              aria-label="Đặt lại khung cắt về mặc định"
              disabled={isPreparing}
              onClick={onResetCropBox}
              title="Đặt lại khung"
            >
              <RefreshCw size={15} aria-hidden="true" />
              <span>Đặt lại khung</span>
            </button>
          </div>
        </section>

        {needsResetConfirmation && (
          <section className="crop-notice-warning crop-confirm-box" role="alert">
            <AlertTriangle size={18} aria-hidden="true" />
            <div>
              <strong>Xác nhận cắt lại</strong>
              <p>Cắt lại sẽ xoá thiết kế hiện tại. Bạn có chắc?</p>
              <div className="crop-confirm-actions">
                <button
                  type="button"
                  className="primary-button danger-btn"
                  onClick={onConfirmResetDesign}
                  disabled={isPreparing}
                >
                  Xác nhận xoá thiết kế
                </button>
                <button
                  type="button"
                  onClick={onCancelResetDesign}
                  disabled={isPreparing}
                >
                  Hủy
                </button>
              </div>
            </div>
          </section>
        )}

        {errorMessage && !needsResetConfirmation && (
          <section className="crop-notice-error" role="alert">
            <AlertTriangle size={18} aria-hidden="true" />
            <div>
              <strong>Lỗi chuẩn bị model</strong>
              <p>{errorMessage}</p>
              <button type="button" className="crop-retry-btn" onClick={onRetry}>
                <RefreshCw size={14} aria-hidden="true" />
                Thử lại
              </button>
            </div>
          </section>
        )}

        {isPreparing && (
          <section className="crop-progress-stepper" aria-label="Tiến trình cắt và làm sạch">
            <ol className="crop-step-list">
              {PREPARE_STEPS.map((step, index) => {
                const isCurrent = step.key === prepareStep;
                const isPassed = currentStepIndex > index || prepareStep === "done";
                return (
                  <li
                    key={step.key}
                    className={`crop-step-item ${isCurrent ? "current" : ""} ${isPassed ? "passed" : ""}`}
                  >
                    <span className="crop-step-indicator">
                      {isCurrent ? (
                        <Loader2 size={14} className="spinning" aria-hidden="true" />
                      ) : isPassed ? (
                        <CheckCircle2 size={14} aria-hidden="true" />
                      ) : (
                        index + 1
                      )}
                    </span>
                    <span className="crop-step-label">{step.label}</span>
                  </li>
                );
              })}
            </ol>
          </section>
        )}

        <footer className="crop-panel-footer">
          <button
            type="button"
            className="primary-button crop-submit-btn"
            disabled={isPreparing || Boolean(needsResetConfirmation)}
            onClick={onPrepare}
          >
            {isPreparing ? (
              <>
                <Loader2 size={16} className="spinning" aria-hidden="true" />
                Đang xử lý...
              </>
            ) : (
              "Cắt & làm sạch"
            )}
          </button>
          {onCancelCropMode && (
            <button
              type="button"
              className="crop-cancel-btn"
              disabled={isPreparing}
              onClick={onCancelCropMode}
            >
              Hủy
            </button>
          )}
        </footer>
      </div>
    </aside>
  );
}
