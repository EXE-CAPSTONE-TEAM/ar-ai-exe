import { clearAccessToken, clearUserAccessToken, storeAccessToken, storedAccessToken } from "./authStorage";
import { clearPersistedCloudSession, loadPersistedCloudSession, savePersistedCloudSession } from "./desktopRuntime";
import { getKusShoesApiBaseUrl } from "./editorLaunch";

/**
 * The signed-in KusShoes cloud session of KusStudio Desktop.
 *
 * KusShoes access tokens live 5 minutes and the web keeps itself signed in with an HttpOnly
 * refresh cookie the desktop webview cannot use. For a verified desktop client KusShoes returns
 * the (single-use, rotating) refresh token in the response body instead. This module is the only
 * place that holds it: in memory, plus the OS credential store so a restart stays signed in.
 * The local sidecar's built-in account never comes through here and is never persisted.
 */

/** Opt-in header; KusShoes only honours it together with the Tauri webview Origin. */
export const DESKTOP_CLIENT_HEADERS: Readonly<Record<string, string>> = { "X-KusShoes-Client": "desktop" };

const REQUEST_TIMEOUT_MS = 15_000;
const REFRESH_TOKEN_PATTERN = /^[A-Za-z0-9._~+/=-]{16,4096}$/;

type PersistedSession = { userId: string | null; refreshToken: string };

export type CloudRefreshResult = "ok" | "rejected" | "offline";

let refreshToken: string | null = null;
let sessionUserId: string | null = null;
let refreshInFlight: Promise<CloudRefreshResult> | null = null;

export function hasCloudSession(): boolean {
  return refreshToken !== null;
}

export function cloudSessionUserId(): string | null {
  return sessionUserId;
}

/**
 * Loads a session saved by an earlier run into memory without contacting KusShoes. Lets a cold
 * start from a web launch know it is already signed in (and as whom) before claiming the ticket.
 */
export async function loadSavedCloudSession(): Promise<boolean> {
  if (!refreshToken) {
    const saved = await readPersisted();
    if (!refreshToken && saved) {
      refreshToken = saved.refreshToken;
      sessionUserId = saved.userId;
    }
  }
  return hasCloudSession();
}

/** Records which KusShoes user the saved session belongs to (resolved after sign-in/restore). */
export async function rememberCloudSessionUser(userId: string): Promise<void> {
  if (!refreshToken || sessionUserId === userId) {
    return;
  }
  sessionUserId = userId;
  await persist();
}

/** Signs the app in with tokens from a desktop-gated KusShoes response. */
export async function adoptCloudSession(tokens: {
  accessToken: string;
  refreshToken?: string | null;
  userId?: string | null;
}): Promise<void> {
  storeAccessToken(tokens.accessToken);
  if (!tokens.refreshToken) {
    // An older KusShoes API without the desktop body token: signed in until the access token expires.
    return;
  }
  if (!REFRESH_TOKEN_PATTERN.test(tokens.refreshToken)) {
    throw new Error("KusShoes returned an invalid refresh token.");
  }
  refreshToken = tokens.refreshToken;
  sessionUserId = tokens.userId ?? sessionUserId;
  await persist();
}

/**
 * Restores the session saved by a previous run. "offline" keeps the saved session for later:
 * only a definitive rejection from KusShoes ever deletes it.
 */
export async function restoreCloudSession(): Promise<CloudRefreshResult | "none"> {
  if (!(await loadSavedCloudSession())) {
    return "none";
  }
  if (storedAccessToken()) {
    return "ok";
  }
  return refreshCloudSession();
}

/** Single-flight: concurrent 401s share one refresh, because each refresh token works only once. */
export function refreshCloudSession(): Promise<CloudRefreshResult> {
  if (!refreshInFlight) {
    refreshInFlight = runRefresh().finally(() => {
      refreshInFlight = null;
    });
  }
  return refreshInFlight;
}

/**
 * Full sign-out: revoke the refresh token on KusShoes (best effort), then forget it locally.
 * /logout needs a live access token; after 5 idle minutes it has expired, so renew first —
 * otherwise the refresh token would stay valid on the server for its full 30 days.
 */
export async function signOutCloudSession(): Promise<void> {
  if (refreshToken) {
    try {
      let response = storedAccessToken() ? await postLogout() : null;
      if ((!response || response.status === 401) && (await refreshCloudSession()) === "ok") {
        response = await postLogout();
      }
    } catch {
      // Offline: forgetting it locally is still what the user asked for.
    }
  }
  refreshToken = null;
  sessionUserId = null;
  clearAccessToken();
  await clearPersistedCloudSession().catch(() => undefined);
}

function postLogout(): Promise<Response> {
  return postJson(
    "/api/v1/auth/logout",
    { refresh_token: refreshToken ?? "" },
    { Authorization: `Bearer ${storedAccessToken() ?? ""}` },
  );
}

async function runRefresh(): Promise<CloudRefreshResult> {
  const token = refreshToken;
  if (!token) {
    return "rejected";
  }
  let response: Response;
  try {
    response = await postJson("/api/v1/auth/refresh", { refresh_token: token });
  } catch {
    return "offline";
  }
  if (response.status === 401 || response.status === 403) {
    // Expired, revoked or already used: the saved session can never work again.
    refreshToken = null;
    sessionUserId = null;
    // Only the user token: an open editor session is project-scoped and keeps working.
    clearUserAccessToken();
    await clearPersistedCloudSession().catch(() => undefined);
    return "rejected";
  }
  if (!response.ok) {
    return "offline";
  }
  const payload = (await response.json()) as { access_token?: unknown; refresh_token?: unknown };
  if (typeof payload.access_token !== "string") {
    return "offline";
  }
  storeAccessToken(payload.access_token);
  if (typeof payload.refresh_token === "string" && REFRESH_TOKEN_PATTERN.test(payload.refresh_token)) {
    // The old token is spent the moment KusShoes rotated it: save the new one before anything else.
    refreshToken = payload.refresh_token;
    await persist();
  }
  return "ok";
}

async function persist(): Promise<void> {
  if (!refreshToken) {
    return;
  }
  const value: PersistedSession = { userId: sessionUserId, refreshToken };
  await savePersistedCloudSession(JSON.stringify(value)).catch(() => undefined);
}

async function readPersisted(): Promise<PersistedSession | null> {
  let raw: string | null;
  try {
    raw = await loadPersistedCloudSession();
  } catch {
    return null;
  }
  if (!raw) {
    return null;
  }
  try {
    const parsed = JSON.parse(raw) as Partial<PersistedSession>;
    if (typeof parsed.refreshToken === "string" && REFRESH_TOKEN_PATTERN.test(parsed.refreshToken)) {
      return { refreshToken: parsed.refreshToken, userId: typeof parsed.userId === "string" ? parsed.userId : null };
    }
  } catch {
    // Unreadable entry: treat as absent and let the next sign-in overwrite it.
  }
  return null;
}

async function postJson(path: string, body: Record<string, string>, headers: Record<string, string> = {}): Promise<Response> {
  const controller = new AbortController();
  const timeout = window.setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);
  try {
    return await fetch(`${getKusShoesApiBaseUrl()}${path}`, {
      method: "POST",
      credentials: "omit",
      headers: { "Content-Type": "application/json", ...DESKTOP_CLIENT_HEADERS, ...headers },
      body: JSON.stringify(body),
      signal: controller.signal,
    });
  } finally {
    window.clearTimeout(timeout);
  }
}

export function resetCloudSessionForTesting(): void {
  refreshToken = null;
  sessionUserId = null;
  refreshInFlight = null;
}
