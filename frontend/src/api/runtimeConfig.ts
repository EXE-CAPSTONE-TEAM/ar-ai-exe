const DEFAULT_API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000";
const API_PATH_PREFIX = "/api";

let apiBaseUrl = DEFAULT_API_BASE_URL;

export function getApiBaseUrl(): string {
  return apiBaseUrl;
}

export function setApiBaseUrl(nextBaseUrl: string): void {
  apiBaseUrl = normalizeApiBaseUrl(nextBaseUrl);
}

export function apiUrl(pathOrUrl: string): string {
  const baseUrl = new URL(apiBaseUrl);
  const value = rejectControlCharacters(pathOrUrl, "API URL");
  const url = /^https?:\/\//i.test(value) ? new URL(value) : new URL(value, baseUrl);
  if (url.protocol !== "http:" && url.protocol !== "https:") {
    throw new TypeError("API URL must use HTTP or HTTPS.");
  }
  if (url.origin !== baseUrl.origin) {
    throw new TypeError("API URL must stay on the configured API origin.");
  }
  if (url.username || url.password) {
    throw new TypeError("API URL credentials are not allowed.");
  }
  if (!isApiPath(url.pathname)) {
    throw new TypeError("API URL path must start with /api.");
  }
  if (url.pathname.split("/").includes("..")) {
    throw new TypeError("API URL path traversal is not allowed.");
  }
  return url.toString();
}

function normalizeApiBaseUrl(nextBaseUrl: string): string {
  const value = rejectControlCharacters(nextBaseUrl, "API base URL");
  const url = new URL(value);
  if (url.protocol !== "http:" && url.protocol !== "https:") {
    throw new TypeError("API base URL must use HTTP or HTTPS.");
  }
  if (url.username || url.password) {
    throw new TypeError("API base URL credentials are not allowed.");
  }
  url.pathname = url.pathname.replace(/\/+$/, "");
  url.search = "";
  url.hash = "";
  return url.toString().replace(/\/+$/, "");
}

function rejectControlCharacters(value: string, label: string): string {
  const trimmed = value.trim();
  if (trimmed !== value || /[\u0000-\u001F\u007F]/u.test(value)) {
    throw new TypeError(`${label} contains invalid characters.`);
  }
  return trimmed;
}

function isApiPath(pathname: string): boolean {
  return pathname === API_PATH_PREFIX || pathname.startsWith(`${API_PATH_PREFIX}/`);
}
