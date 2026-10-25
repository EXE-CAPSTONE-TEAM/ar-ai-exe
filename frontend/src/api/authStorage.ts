const TOKEN_STORAGE_KEY = "shoe-customizer-token";
const ACCESS_TOKEN_PATTERN = /^[A-Za-z0-9._~+/=-]+$/;
const MAX_ACCESS_TOKEN_LENGTH = 4096;
let memoryAccessToken: string | null = null;
// Editor-session tokens (15 min, one project, no refresh) live in their own slot so starting an
// editor session never discards the signed-in user's token that the launcher still needs.
let memoryEditorToken: string | null = null;
const EDITOR_API_PATH = /^\/api\/v1\/editor(?:\/|$)/;

/** True for editor endpoints, given as an API path or as an absolute URL on the API origin. */
export function isEditorApiPath(pathOrUrl: string): boolean {
  if (/^https?:\/\//i.test(pathOrUrl)) {
    try {
      return EDITOR_API_PATH.test(new URL(pathOrUrl).pathname);
    } catch {
      return false;
    }
  }
  return EDITOR_API_PATH.test(pathOrUrl);
}

/** Bearer token for `path`: the editor-session token on `/api/v1/editor/*`, the user token elsewhere. */
export function accessTokenForPath(path: string): string | null {
  return isEditorApiPath(path) ? storedEditorAccessToken() : storedAccessToken();
}

export function storedAccessToken(): string | null {
  if (!memoryAccessToken) {
    return null;
  }
  try {
    return sanitizeAccessToken(memoryAccessToken);
  } catch {
    clearAccessToken();
    return null;
  }
}

export function storeAccessToken(accessToken: string): void {
  memoryAccessToken = sanitizeAccessToken(accessToken);
  try {
    localStorage.removeItem(TOKEN_STORAGE_KEY);
  } catch {
    // Ignore in environments without localStorage
  }
}

export function storedEditorAccessToken(): string | null {
  if (!memoryEditorToken) {
    return null;
  }
  try {
    return sanitizeAccessToken(memoryEditorToken);
  } catch {
    memoryEditorToken = null;
    return null;
  }
}

export function storeEphemeralAccessToken(accessToken: string): void {
  memoryEditorToken = sanitizeAccessToken(accessToken);
  try {
    localStorage.removeItem(TOKEN_STORAGE_KEY);
  } catch {
    // Ignore in environments without localStorage
  }
}

export function hasEphemeralAccessToken(): boolean {
  return memoryEditorToken !== null;
}

export function clearEditorAccessToken(): void {
  memoryEditorToken = null;
}

/** Drops only the signed-in user's token; an open editor session keeps working. */
export function clearUserAccessToken(): void {
  memoryAccessToken = null;
  try {
    localStorage.removeItem(TOKEN_STORAGE_KEY);
  } catch {
    // Ignore in environments without localStorage
  }
}

/** Full sign-out: drops the user token and any editor-session token. */
export function clearAccessToken(): void {
  memoryAccessToken = null;
  memoryEditorToken = null;
  try {
    localStorage.removeItem(TOKEN_STORAGE_KEY);
  } catch {
    // Ignore in environments without localStorage
  }
}

function sanitizeAccessToken(accessToken: string): string {
  const token = accessToken.trim();
  if (
    token !== accessToken ||
    token.length < 16 ||
    token.length > MAX_ACCESS_TOKEN_LENGTH ||
    !ACCESS_TOKEN_PATTERN.test(token)
  ) {
    throw new TypeError("Invalid access token.");
  }
  return token;
}
