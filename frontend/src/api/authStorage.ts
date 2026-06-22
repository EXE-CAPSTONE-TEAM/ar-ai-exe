const TOKEN_STORAGE_KEY = "shoe-customizer-token";
const ACCESS_TOKEN_PATTERN = /^[A-Za-z0-9._~+/=-]+$/;
const MAX_ACCESS_TOKEN_LENGTH = 4096;

export function storedAccessToken(): string | null {
  const token = localStorage.getItem(TOKEN_STORAGE_KEY);
  if (!token) {
    return null;
  }
  try {
    return sanitizeAccessToken(token);
  } catch {
    clearAccessToken();
    return null;
  }
}

export function storeAccessToken(accessToken: string): void {
  localStorage.setItem(TOKEN_STORAGE_KEY, sanitizeAccessToken(accessToken));
}

export function clearAccessToken(): void {
  localStorage.removeItem(TOKEN_STORAGE_KEY);
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
