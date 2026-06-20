const DEFAULT_API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000";

let apiBaseUrl = DEFAULT_API_BASE_URL;

export function getApiBaseUrl(): string {
  return apiBaseUrl;
}

export function setApiBaseUrl(nextBaseUrl: string): void {
  apiBaseUrl = nextBaseUrl.replace(/\/+$/, "");
}

export function apiUrl(pathOrUrl: string): string {
  if (/^https?:\/\//i.test(pathOrUrl)) {
    return pathOrUrl;
  }
  return `${apiBaseUrl}${pathOrUrl}`;
}
