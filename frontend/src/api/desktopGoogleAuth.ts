import { openInBrowser } from "./desktopRuntime";
import { getKusShoesApiBaseUrl } from "./editorLaunch";
import { storeAccessToken } from "./authStorage";

const PKCE_VERIFIER_KEY = "kusshoes_desktop_pkce_verifier";
const PKCE_EXPIRY_MS = 5 * 60 * 1000;
const MARKETING_LOGIN_URL =
  import.meta.env.VITE_MARKETING_LOGIN_URL ?? "https://kusshoes.vercel.app/login";

function createCodeVerifier(): string {
  const bytes = crypto.getRandomValues(new Uint8Array(32));
  let binary = "";
  for (const byte of bytes) binary += String.fromCharCode(byte);
  return btoa(binary).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/u, "");
}

async function createCodeChallenge(codeVerifier: string): Promise<string> {
  const digest = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(codeVerifier));
  const bytes = new Uint8Array(digest);
  let binary = "";
  for (const byte of bytes) binary += String.fromCharCode(byte);
  return btoa(binary).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/u, "");
}

export async function startDesktopGoogleLogin(): Promise<void> {
  const verifier = createCodeVerifier();
  const challenge = await createCodeChallenge(verifier);

  try {
    sessionStorage.setItem(
      PKCE_VERIFIER_KEY,
      JSON.stringify({ verifier, created: Date.now() })
    );
  } catch {
    // If sessionStorage is disabled or restricted, continue best-effort
  }

  // Open web login with from=desktop flag so Google login hand-off works seamlessly across both:
  // 1. Direct Web-to-Desktop protocol bridge (kusshoes-editor://auth/callback?access_token=...)
  // 2. Or direct PKCE flow when backend is redeployed with client=desktop
  const separator = MARKETING_LOGIN_URL.includes("?") ? "&" : "?";
  const loginUrl = `${MARKETING_LOGIN_URL}${separator}from=desktop&code_challenge=${encodeURIComponent(
    challenge
  )}`;

  await openInBrowser(loginUrl);
}

export function isDesktopAuthDeepLink(urlValue: string): boolean {
  try {
    const url = new URL(urlValue);
    return (
      url.protocol === "kusshoes-editor:" &&
      (url.hostname === "auth" ||
        url.pathname.includes("/auth") ||
        url.searchParams.has("code") ||
        url.searchParams.has("access_token") ||
        url.searchParams.has("token") ||
        url.searchParams.has("error"))
    );
  } catch {
    return false;
  }
}

export async function completeDesktopGoogleAuth(
  urlValue: string
): Promise<{ accessToken: string; tokenType: string }> {
  const url = new URL(urlValue);
  const error = url.searchParams.get("error");
  if (error) {
    throw new Error(`Đăng nhập Google không thành công: ${error}`);
  }

  // 1. Dual-mode support: Direct Access Token from Web Bridge
  const directToken = url.searchParams.get("access_token") || url.searchParams.get("token");
  if (directToken) {
    const tokenType = url.searchParams.get("token_type") || "bearer";
    storeAccessToken(directToken);
    return { accessToken: directToken, tokenType };
  }

  // 2. PKCE code exchange with backend
  const code = url.searchParams.get("code");
  if (!code) {
    throw new Error("Không tìm thấy thông tin xác thực Google trong liên kết phản hồi.");
  }

  let rawVerifier: string | null = null;
  try {
    rawVerifier = sessionStorage.getItem(PKCE_VERIFIER_KEY);
    sessionStorage.removeItem(PKCE_VERIFIER_KEY);
  } catch {
    // Session storage read failure
  }

  if (!rawVerifier) {
    throw new Error(
      "Phiên đăng nhập đã hết hạn hoặc không tìm thấy mã kiểm tra PKCE. Vui lòng bấm Đăng nhập lại."
    );
  }

  let verifier = "";
  try {
    const parsed = JSON.parse(rawVerifier) as { verifier: string; created: number };
    if (Date.now() - parsed.created > PKCE_EXPIRY_MS) {
      throw new Error("Phiên đăng nhập Google đã quá thời gian 5 phút. Vui lòng thử lại.");
    }
    verifier = parsed.verifier;
  } catch (caught) {
    if (caught instanceof Error && caught.message.includes("5 phút")) throw caught;
    throw new Error("Dữ liệu xác thực bảo mật không hợp lệ. Vui lòng thử lại.");
  }

  const baseUrl = getKusShoesApiBaseUrl();
  const response = await fetch(`${baseUrl}/api/v1/auth/google/desktop/exchange`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      code,
      code_verifier: verifier,
    }),
  });

  if (!response.ok) {
    const errorText = await response.text();
    let errorMsg = `Xác thực với máy chủ thất bại (${response.status})`;
    try {
      const errorJson = JSON.parse(errorText) as { detail?: string; message?: string };
      errorMsg = errorJson.message || errorJson.detail || errorMsg;
    } catch {
      // Ignore JSON parse failure on error body
    }
    throw new Error(errorMsg);
  }

  const data = (await response.json()) as { access_token: string; token_type: string };
  storeAccessToken(data.access_token);
  return { accessToken: data.access_token, tokenType: data.token_type };
}
