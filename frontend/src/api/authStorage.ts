const TOKEN_STORAGE_KEY = "shoe-customizer-token";
const ACCESS_TOKEN_PATTERN = /^[A-Za-z0-9._~+/=-]+$/;
const MAX_ACCESS_TOKEN_LENGTH = 4096;
let memoryAccessToken: string | null = null;

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

export function storeEphemeralAccessToken(accessToken: string): void {
  memoryAccessToken = sanitizeAccessToken(accessToken);
  try {
    localStorage.removeItem(TOKEN_STORAGE_KEY);
  } catch {
    // Ignore in environments without localStorage
  }
}

export function hasEphemeralAccessToken(): boolean {
  return memoryAccessToken !== null;
}

export function clearAccessToken(): void {
  memoryAccessToken = null;
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
