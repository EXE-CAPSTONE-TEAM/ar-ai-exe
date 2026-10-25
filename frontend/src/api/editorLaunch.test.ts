import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { clearAccessToken, storedAccessToken } from "./authStorage";
import { hasCloudSession, resetCloudSessionForTesting } from "./cloudSession";
import { completeEditorLaunch, parseLaunchTicket } from "./editorLaunch";

// A syntactically valid ticket: the pattern accepts 32–256 url-safe characters.
const TICKET = "a".repeat(32);

describe("parseLaunchTicket", () => {
  it("returns the ticket from a well-formed deep link", () => {
    expect(parseLaunchTicket(`kusshoes-editor://launch?ticket=${TICKET}`)).toBe(TICKET);
  });

  it.each([
    ["wrong scheme", `https://launch?ticket=${TICKET}`],
    ["wrong host", `kusshoes-editor://evil?ticket=${TICKET}`],
    ["extra parameter", `kusshoes-editor://launch?ticket=${TICKET}&next=x`],
    ["duplicate ticket", `kusshoes-editor://launch?ticket=${TICKET}&ticket=${TICKET}`],
    ["fragment", `kusshoes-editor://launch?ticket=${TICKET}#x`],
    ["ticket too short", `kusshoes-editor://launch?ticket=${TICKET.slice(1)}`],
  ])("rejects %s", (_label, url) => {
    expect(() => parseLaunchTicket(url)).toThrow(TypeError);
  });
});

describe("completeEditorLaunch user session", () => {
  const USER_A = "11111111-1111-4111-8111-111111111111";
  const USER_B = "33333333-3333-4333-8333-333333333333";
  const PROJECT = "22222222-2222-4222-8222-222222222222";
  let keyring: string | null = null;

  function json(body: unknown): Response {
    return new Response(JSON.stringify(body), { status: 200, headers: { "Content-Type": "application/json" } });
  }

  function stubLaunch(exchangeExtra: Record<string, unknown>, userId = USER_A) {
    const bodies: Array<Record<string, unknown>> = [];
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string, init: RequestInit) => {
        const body = JSON.parse(String(init.body ?? "{}")) as Record<string, unknown>;
        if (url.endsWith("/claim")) return json({ authorization_code: "c".repeat(40), expires_in: 60 });
        if (url.endsWith("/exchange")) {
          bodies.push(body);
          return json({
            access_token: "editor-token-0123456789",
            token_type: "bearer",
            expires_in: 900,
            user_id: userId,
            project_id: PROJECT,
            scopes: ["editor:read", "editor:write"],
            ...exchangeExtra,
          });
        }
        return json({});
      }),
    );
    return bodies;
  }

  beforeEach(() => {
    keyring = null;
    vi.stubGlobal("window", {
      __TAURI__: {
        core: {
          invoke: vi.fn(async (command: string, args?: { value?: string }) => {
            if (command === "load_cloud_session") return keyring;
            if (command === "save_cloud_session") keyring = args?.value ?? null;
            if (command === "clear_cloud_session") keyring = null;
            return null;
          }),
        },
      },
      setTimeout: globalThis.setTimeout,
      clearTimeout: globalThis.clearTimeout,
    });
  });

  afterEach(() => {
    resetCloudSessionForTesting();
    clearAccessToken();
    vi.unstubAllGlobals();
  });

  it("signs the app in from a web launch when it has no session, and not again once it does", async () => {
    const bodies = stubLaunch({ user_access_token: "user-token-0123456789", refresh_token: "refresh-0123456789-abc" });
    await completeEditorLaunch(`kusshoes-editor://launch?ticket=${TICKET}`);
    expect(bodies[0].include_user_session).toBe(true);
    expect(hasCloudSession()).toBe(true);
    expect(storedAccessToken()).toBe("user-token-0123456789");
    expect(JSON.parse(keyring!)).toEqual({ userId: USER_A, refreshToken: "refresh-0123456789-abc" });

    await completeEditorLaunch(`kusshoes-editor://launch?ticket=${TICKET}`);
    expect(bodies[1].include_user_session).toBe(false);
  });

  it("drops the saved session when the website launches as a different user", async () => {
    stubLaunch({ user_access_token: "user-token-0123456789", refresh_token: "refresh-0123456789-abc" });
    await completeEditorLaunch(`kusshoes-editor://launch?ticket=${TICKET}`);

    stubLaunch({}, USER_B);
    await completeEditorLaunch(`kusshoes-editor://launch?ticket=${TICKET}`);
    expect(hasCloudSession()).toBe(false);
    expect(keyring).toBeNull();
  });
});
