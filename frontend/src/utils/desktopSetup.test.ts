import { describe, expect, it } from "vitest";
import { setupBannerView, updatePercent } from "./desktopSetup";

const base = { name: "blender", message: "m", percent: 0 };

describe("setupBannerView", () => {
  it("hides when nothing is known or the renderer was already there", () => {
    expect(setupBannerView(null)).toBeNull();
    expect(setupBannerView({ ...base, status: "missing", stage: "missing" })).toBeNull();
    // get_install_progress reports a renderer installed on an earlier run as stage "present".
    expect(setupBannerView({ ...base, status: "installed", stage: "present" })).toBeNull();
  });

  it("shows determinate progress while downloading, indeterminate before the first byte", () => {
    expect(setupBannerView({ ...base, status: "downloading", stage: "downloading", percent: 0 })?.percent).toBeNull();
    const view = setupBannerView({ ...base, status: "downloading", stage: "extracting", percent: 87.6 });
    expect(view).toMatchObject({ tone: "progress", percent: 88, canRetry: false });
  });

  it("offers a retry on failure and confirms a fresh install", () => {
    expect(setupBannerView({ ...base, status: "failed", stage: "failed" })).toMatchObject({ tone: "error", canRetry: true });
    expect(setupBannerView({ ...base, status: "installed", stage: "installed", percent: 100 })).toMatchObject({ tone: "done", percent: 100 });
  });

  it("keeps the raw shell error behind technical details instead of the headline copy", () => {
    const view = setupBannerView({ ...base, status: "failed", stage: "failed", message: "Preview renderer manifest was not found." });
    expect(view?.technicalDetail).toBe("Preview renderer manifest was not found.");
    expect(view?.detail).not.toContain("manifest");
  });
});

describe("updatePercent", () => {
  it("is null without a known size and clamps otherwise", () => {
    expect(updatePercent(null)).toBeNull();
    expect(updatePercent({ downloadedBytes: 5, totalBytes: 0 })).toBeNull();
    expect(updatePercent({ downloadedBytes: 50, totalBytes: 200 })).toBe(25);
    expect(updatePercent({ downloadedBytes: 300, totalBytes: 200 })).toBe(100);
  });
});
