import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { clearAccessToken, storedAccessToken } from "./authStorage";
import {
  adoptCloudSession,
  hasCloudSession,
  refreshCloudSession,
  resetCloudSessionForTesting,
  restoreCloudSession,
  signOutCloudSession,
} from "./cloudSession";
import { isDesktopAuthDeepLink } from "./desktopGoogleAuth";

const ACCESS = "access-token-0123456789";
const REFRESH_1 = "refresh-token-one-0123456789";
const REFRESH_2 = "refresh-token-two-0123456789";

let keyring: string | null;
let invoke: ReturnType<typeof vi.fn>;

function json(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
}

beforeEach(() => {
  keyring = null;
  invoke = vi.fn(async (command: string, args?: { value?: string }) => {
    if (command === "load_cloud_session") return keyring;
    if (command === "save_cloud_session") keyring = args?.value ?? null;
    if (command === "clear_cloud_session") keyring = null;
    return null;
  });
  vi.stubGlobal("window", {
    __TAURI__: { core: { invoke } },
    setTimeout: globalThis.setTimeout,
    clearTimeout: globalThis.clearTimeout,
  });
});

afterEach(() => {
  resetCloudSessionForTesting();
  clearAccessToken();
  vi.unstubAllGlobals();
});

describe("cloud session", () => {
  it("persists the refresh token to the credential store and restores it after a restart", async () => {
    await adoptCloudSession({ accessToken: ACCESS, refreshToken: REFRESH_1, userId: "u1" });
    expect(JSON.parse(keyring!)).toEqual({ userId: "u1", refreshToken: REFRESH_1 });

    // Simulate a restart: memory is gone, the credential store is not.
    resetCloudSessionForTesting();
    clearAccessToken();
    const fetchMock = vi.fn(async () => json(200, { access_token: "fresh-access-0123456789", refresh_token: REFRESH_2 }));
    vi.stubGlobal("fetch", fetchMock);

    await expect(restoreCloudSession()).resolves.toBe("ok");
    expect(storedAccessToken()).toBe("fresh-access-0123456789");
    const [, init] = fetchMock.mock.calls[0] as unknown as [string, RequestInit];
    expect(JSON.parse(String(init.body))).toEqual({ refresh_token: REFRESH_1 });
    expect((init.headers as Record<string, string>)["X-KusShoes-Client"]).toBe("desktop");
    // The rotated token replaced the spent one right away.
    expect(JSON.parse(keyring!).refreshToken).toBe(REFRESH_2);
  });

  it("shares one refresh between concurrent callers (refresh tokens are single-use)", async () => {
    await adoptCloudSession({ accessToken: ACCESS, refreshToken: REFRESH_1 });
    const fetchMock = vi.fn(async () => json(200, { access_token: "fresh-access-0123456789", refresh_token: REFRESH_2 }));
    vi.stubGlobal("fetch", fetchMock);

    const results = await Promise.all([refreshCloudSession(), refreshCloudSession(), refreshCloudSession()]);
    expect(results).toEqual(["ok", "ok", "ok"]);
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("keeps the saved session when offline and forgets it only when KusShoes rejects it", async () => {
    await adoptCloudSession({ accessToken: ACCESS, refreshToken: REFRESH_1 });

    vi.stubGlobal("fetch", vi.fn(async () => Promise.reject(new TypeError("Failed to fetch"))));
    await expect(refreshCloudSession()).resolves.toBe("offline");
    expect(hasCloudSession()).toBe(true);
    expect(keyring).not.toBeNull();

    vi.stubGlobal("fetch", vi.fn(async () => json(503, {})));
    await expect(refreshCloudSession()).resolves.toBe("offline");
    expect(keyring).not.toBeNull();

    vi.stubGlobal("fetch", vi.fn(async () => json(401, { code: "AUTH_REFRESH_INVALID" })));
    await expect(refreshCloudSession()).resolves.toBe("rejected");
    expect(hasCloudSession()).toBe(false);
    expect(keyring).toBeNull();
    expect(storedAccessToken()).toBeNull();
  });

  it("sign-out revokes on KusShoes and always forgets the session locally", async () => {
    await adoptCloudSession({ accessToken: ACCESS, refreshToken: REFRESH_1 });
    const fetchMock = vi.fn(async () => Promise.reject(new TypeError("offline")));
    vi.stubGlobal("fetch", fetchMock);

    await signOutCloudSession();
    const [url, init] = fetchMock.mock.calls[0] as unknown as [string, RequestInit];
    expect(url).toContain("/api/v1/auth/logout");
    expect(JSON.parse(String(init.body))).toEqual({ refresh_token: REFRESH_1 });
    expect(keyring).toBeNull();
    expect(hasCloudSession()).toBe(false);
  });

  it("returns 'none' when nothing was saved", async () => {
    await expect(restoreCloudSession()).resolves.toBe("none");
  });
});

describe("desktop Google deep links", () => {
  it("accepts only the one-time PKCE code callback, never a token in the URL", () => {
    expect(isDesktopAuthDeepLink("kusshoes-editor://auth/google/callback?code=abc")).toBe(true);
    expect(isDesktopAuthDeepLink("kusshoes-editor://auth/google/callback?error=AUTH_CONSENT_REQUIRED")).toBe(true);
    expect(isDesktopAuthDeepLink("kusshoes-editor://auth/callback?access_token=stolen")).toBe(false);
    expect(isDesktopAuthDeepLink("kusshoes-editor://launch?ticket=abc")).toBe(false);
  });
});
