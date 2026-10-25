import { adoptCloudSession, DESKTOP_CLIENT_HEADERS } from "./cloudSession";
import { openInBrowser } from "./desktopRuntime";
import { getKusShoesApiBaseUrl } from "./editorLaunch";

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

  // KusShoes' desktop PKCE flow: Google sign-in in the system browser, then KusShoes redirects to
  // kusshoes-editor://auth/google/callback?code=<one-time code> and the app exchanges it with the
  // verifier only it holds. No token ever travels in a URL.
  const params = new URLSearchParams({ client: "desktop", code_challenge: challenge });
  await openInBrowser(`${getKusShoesApiBaseUrl()}/api/v1/auth/google?${params.toString()}`);
}

export function isDesktopAuthDeepLink(urlValue: string): boolean {
  try {
    const url = new URL(urlValue);
    return (
      url.protocol === "kusshoes-editor:" &&
      url.hostname === "auth" &&
      (url.searchParams.has("code") || url.searchParams.has("error"))
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
  if (error === "AUTH_CONSENT_REQUIRED") {
    throw new Error(
      "Tài khoản Google này chưa có trên KusShoes. Hãy đăng ký trên website (đồng ý điều khoản) rồi đăng nhập lại trong app."
    );
  }
  if (error) {
    throw new Error(`Đăng nhập Google không thành công: ${error}`);
  }

  // Tokens in a deep link are never accepted: any website could otherwise push a session into
  // the app. Only the PKCE code this app started can be exchanged.
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
    credentials: "omit",
    headers: { "Content-Type": "application/json", ...DESKTOP_CLIENT_HEADERS },
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

  const data = (await response.json()) as { access_token: string; token_type: string; refresh_token?: string };
  await adoptCloudSession({ accessToken: data.access_token, refreshToken: data.refresh_token });
  return { accessToken: data.access_token, tokenType: data.token_type };
}
