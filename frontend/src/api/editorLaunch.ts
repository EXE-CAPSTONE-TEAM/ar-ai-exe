import { storeEphemeralAccessToken } from "./authStorage";

const EDITOR_SCHEME = "kusshoes-editor:";
const LAUNCH_HOST = "launch";
const TOKEN_PATTERN = /^[A-Za-z0-9_-]{32,256}$/;
const UUID_PATTERN = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
const REQUEST_TIMEOUT_MS = 15_000;

type ClaimResponse = {
  authorization_code: string;
  expires_in: number;
};

type ExchangeResponse = {
  access_token: string;
  token_type: string;
  expires_in: number;
  user_id: string;
  project_id: string;
  scopes: string[];
};

export type EditorLaunchSession = {
  accessToken: string;
  expiresIn: number;
  userId: string;
  projectId: string;
  scopes: string[];
};

export type ActiveEditorSession = Omit<EditorLaunchSession, "accessToken">;

let activeEditorSession: ActiveEditorSession | null = null;

export async function completeEditorLaunch(deepLinkUrl: string): Promise<EditorLaunchSession> {
  const launchTicket = parseLaunchTicket(deepLinkUrl);
  const codeVerifier = createCodeVerifier();
  const codeChallenge = await createCodeChallenge(codeVerifier);

  const claim = await postJson<ClaimResponse>("/api/v1/auth/editor/launch/claim", {
    launch_ticket: launchTicket,
    code_challenge: codeChallenge,
    code_challenge_method: "S256",
  });
  if (!TOKEN_PATTERN.test(claim.authorization_code) || !isPositiveInteger(claim.expires_in)) {
    throw new Error("KusShoes returned an invalid launch authorization response.");
  }

  const exchange = await postJson<ExchangeResponse>("/api/v1/auth/editor/launch/exchange", {
    authorization_code: claim.authorization_code,
    code_verifier: codeVerifier,
  });
  const session = validateExchange(exchange);
  storeEphemeralAccessToken(session.accessToken);
  activeEditorSession = {
    expiresIn: session.expiresIn,
    userId: session.userId,
    projectId: session.projectId,
    scopes: [...session.scopes],
  };
  return session;
}

export function getActiveEditorSession(): ActiveEditorSession | null {
  return activeEditorSession ? { ...activeEditorSession, scopes: [...activeEditorSession.scopes] } : null;
}

export function clearEditorLaunchSession(): void {
  activeEditorSession = null;
}

export function getKusShoesApiBaseUrl(): string {
  const configured =
    import.meta.env.VITE_KUSSHOES_API_BASE_URL ??
    import.meta.env.VITE_MARKETING_API_BASE_URL ??
    "http://127.0.0.1:8000";
  const value = rejectControlCharacters(configured, "KusShoes API base URL");
  const url = new URL(value);
  if (url.protocol !== "http:" && url.protocol !== "https:") {
    throw new TypeError("KusShoes API base URL must use HTTP or HTTPS.");
  }
  if (!import.meta.env.DEV && url.protocol !== "https:") {
    throw new TypeError("Packaged desktop builds require an HTTPS KusShoes API URL.");
  }
  if (url.username || url.password || url.search || url.hash) {
    throw new TypeError("KusShoes API base URL cannot contain credentials, query, or fragment.");
  }
  if (url.pathname !== "/") {
    throw new TypeError("KusShoes API base URL must not contain a path.");
  }
  return url.origin;
}

export function parseLaunchTicket(value: string): string {
  const deepLinkUrl = rejectControlCharacters(value, "Desktop launch URL");
  const url = new URL(deepLinkUrl);
  if (
    url.protocol !== EDITOR_SCHEME ||
    url.hostname !== LAUNCH_HOST ||
    (url.pathname !== "" && url.pathname !== "/") ||
    url.username ||
    url.password ||
    url.hash
  ) {
    throw new TypeError("Desktop launch URL is invalid.");
  }
  const tickets = url.searchParams.getAll("ticket");
  const parameters = [...url.searchParams.keys()];
  if (tickets.length !== 1 || parameters.length !== 1 || parameters[0] !== "ticket") {
    throw new TypeError("Desktop launch URL must contain one launch ticket.");
  }
  const ticket = tickets[0];
  if (!TOKEN_PATTERN.test(ticket)) {
    throw new TypeError("Desktop launch ticket is invalid.");
  }
  return ticket;
}

function createCodeVerifier(): string {
  return base64Url(crypto.getRandomValues(new Uint8Array(32)));
}

async function createCodeChallenge(codeVerifier: string): Promise<string> {
  const digest = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(codeVerifier));
  return base64Url(new Uint8Array(digest));
}

function base64Url(bytes: Uint8Array): string {
  let binary = "";
  for (const value of bytes) binary += String.fromCharCode(value);
  return btoa(binary).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/u, "");
}

async function postJson<T>(path: string, body: Record<string, string>): Promise<T> {
  const controller = new AbortController();
  const timeout = window.setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);
  try {
    const response = await fetch(`${getKusShoesApiBaseUrl()}${path}`, {
      method: "POST",
      credentials: "omit",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
      signal: controller.signal,
    });
    if (!response.ok) throw new Error(await responseErrorMessage(response));
    return (await response.json()) as T;
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") {
      throw new Error("KusShoes did not complete desktop sign-in in time.");
    }
    throw error;
  } finally {
    window.clearTimeout(timeout);
  }
}

async function responseErrorMessage(response: Response): Promise<string> {
  try {
    const payload = (await response.json()) as Record<string, unknown>;
    if (typeof payload.message === "string") return payload.message;
    if (typeof payload.detail === "string") return payload.detail;
  } catch {
    // Never include the launch ticket or authorization code in an error.
  }
  return response.status === 401
    ? "This desktop launch link is invalid or has expired. Open the project from KusShoes again."
    : `KusShoes desktop sign-in failed (${response.status}).`;
}

function validateExchange(exchange: ExchangeResponse): EditorLaunchSession {
  if (
    exchange.token_type.toLowerCase() !== "bearer" ||
    !isPositiveInteger(exchange.expires_in) ||
    !UUID_PATTERN.test(exchange.user_id) ||
    !UUID_PATTERN.test(exchange.project_id) ||
    !Array.isArray(exchange.scopes) ||
    !exchange.scopes.includes("editor:read") ||
    !exchange.scopes.includes("editor:write")
  ) {
    throw new Error("KusShoes returned an invalid editor session.");
  }
  return {
    accessToken: exchange.access_token,
    expiresIn: exchange.expires_in,
    userId: exchange.user_id,
    projectId: exchange.project_id,
    scopes: [...exchange.scopes],
  };
}

function isPositiveInteger(value: number): boolean {
  return Number.isInteger(value) && value > 0;
}

function rejectControlCharacters(value: string, label: string): string {
  const trimmed = value.trim();
  if (trimmed !== value || /[\u0000-\u001F\u007F]/u.test(value)) {
    throw new TypeError(`${label} contains invalid characters.`);
  }
  return trimmed;
}
