import { openInBrowser } from "./desktopRuntime";
import { getKusShoesApiBaseUrl } from "./editorLaunch";
import { storeAccessToken } from "./authStorage";

const PKCE_VERIFIER_KEY = "kusshoes_desktop_pkce_verifier";
const PKCE_EXPIRY_MS = 5 * 60 * 1000;

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

  const baseUrl = getKusShoesApiBaseUrl();
  const authUrl = `${baseUrl}/api/v1/auth/google?client=desktop&code_challenge=${encodeURIComponent(
    challenge
  )}&consent=true`;

  await openInBrowser(authUrl);
}

export function isDesktopAuthDeepLink(urlValue: string): boolean {
  try {
    const url = new URL(urlValue);
    return (
      url.protocol === "kusshoes-editor:" &&
      (url.hostname === "auth" ||
        url.pathname.includes("/auth") ||
        url.searchParams.has("code") ||
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

  const code = url.searchParams.get("code");
  if (!code) {
    throw new Error("Không tìm thấy mã xác thực Google trong liên kết phản hồi.");
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
