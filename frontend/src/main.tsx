import React from "react";
import ReactDOM from "react-dom/client";

import { App } from "./App";
import "./styles.css";

// Last-resort boundary: a render error shows a recovery screen instead of a blank window.
class RootErrorBoundary extends React.Component<
  { children: React.ReactNode },
  { hasError: boolean; error: Error | null }
> {
  constructor(props: { children: React.ReactNode }) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error) {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: React.ErrorInfo) {
    console.error("RootErrorBoundary caught:", error, errorInfo);
  }

  render() {
    if (this.state.hasError) {
      return (
        <div
          style={{
            position: "fixed",
            inset: 0,
            zIndex: 999999,
            background: "#fff",
            padding: 32,
            fontFamily: "sans-serif",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
          }}
        >
          <div
            style={{
              maxWidth: 720,
              width: "100%",
              background: "#fff",
              border: "2px solid #ef4444",
              borderRadius: 8,
              padding: 24,
              boxShadow: "0 10px 25px rgba(0,0,0,0.1)",
            }}
          >
            <h2 style={{ color: "#ef4444", marginTop: 0 }}>Lỗi giao diện (Render Error)</h2>
            <p style={{ fontWeight: 600, color: "#1e293b", margin: "12px 0" }}>
              {this.state.error?.message}
            </p>
            <pre
              style={{
                background: "#f1f5f9",
                padding: 16,
                borderRadius: 6,
                overflow: "auto",
                maxHeight: 300,
                fontSize: 13,
                color: "#334155",
              }}
            >
              {this.state.error?.stack}
            </pre>
            <button
              type="button"
              style={{
                marginTop: 16,
                padding: "8px 16px",
                background: "#ef4444",
                color: "#fff",
                border: "none",
                borderRadius: 4,
                cursor: "pointer",
                fontWeight: 600,
              }}
              onClick={() => {
                const isDesktop =
                  new URLSearchParams(window.location.search).get("desktop") === "1" ||
                  import.meta.env.VITE_DESKTOP_SHELL === "true";
                window.location.href = isDesktop ? "/?desktop=1" : "/";
              }}
            >
              Quay lại màn hình chính
            </button>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <RootErrorBoundary>
      <App />
    </RootErrorBoundary>
  </React.StrictMode>,
);
