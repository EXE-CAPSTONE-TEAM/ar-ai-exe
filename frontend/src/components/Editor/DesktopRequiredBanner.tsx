import { AlertTriangle, Download, ExternalLink, Monitor, X } from "lucide-react";

type DesktopRequiredBannerProps = {
  onClose: () => void;
  deepLinkUrl?: string;
  downloadUrl?: string;
};

export function DesktopRequiredBanner({
  onClose,
  deepLinkUrl = "kusshoes-editor://launch",
  downloadUrl = "https://kusshoes.vercel.app/products",
}: DesktopRequiredBannerProps) {
  return (
    <div className="desktop-required-banner" role="alert" aria-live="assertive">
      <div className="desktop-required-content">
        <span className="desktop-required-icon">
          <Monitor size={18} aria-hidden="true" />
        </span>
        <div className="desktop-required-text">
          <strong>Tính năng này cần KusStudio Desktop (Windows)</strong>
          <p>Bake, export và chuẩn bị model 3D được xử lý trên máy của bạn để đảm bảo tốc độ và chất lượng tốt nhất.</p>
        </div>
      </div>
      <div className="desktop-required-actions">
        <a
          href={deepLinkUrl}
          className="desktop-required-btn primary-action"
          onClick={(e) => {
            e.preventDefault();
            window.location.href = deepLinkUrl;
          }}
        >
          <ExternalLink size={14} aria-hidden="true" />
          Mở trong Desktop
        </a>
        <a
          href={downloadUrl}
          target="_blank"
          rel="noopener noreferrer"
          className="desktop-required-btn secondary-action"
        >
          <Download size={14} aria-hidden="true" />
          Tải installer
        </a>
        <button
          type="button"
          className="desktop-required-close"
          onClick={onClose}
          aria-label="Đóng thông báo"
        >
          <X size={16} aria-hidden="true" />
        </button>
      </div>
    </div>
  );
}

type RawModelWebBannerProps = {
  deepLinkUrl?: string;
  downloadUrl?: string;
};

export function RawModelWebBanner({
  deepLinkUrl = "kusshoes-editor://launch",
  downloadUrl = "https://kusshoes.vercel.app/products",
}: RawModelWebBannerProps) {
  return (
    <div className="raw-model-web-banner" role="status">
      <div className="raw-model-banner-content">
        <AlertTriangle size={18} aria-hidden="true" />
        <div className="raw-model-banner-text">
          <strong>Model thô từ scan</strong>
          <span>Mở KusStudio Desktop (Windows) để cắt & làm sạch trước khi thiết kế.</span>
        </div>
      </div>
      <div className="raw-model-banner-actions">
        <a
          href={deepLinkUrl}
          className="raw-model-btn primary-action"
          onClick={(e) => {
            e.preventDefault();
            window.location.href = deepLinkUrl;
          }}
        >
          <ExternalLink size={14} aria-hidden="true" />
          Mở trong Desktop
        </a>
        <a
          href={downloadUrl}
          target="_blank"
          rel="noopener noreferrer"
          className="raw-model-btn secondary-action"
        >
          <Download size={14} aria-hidden="true" />
          Tải installer
        </a>
      </div>
    </div>
  );
}
