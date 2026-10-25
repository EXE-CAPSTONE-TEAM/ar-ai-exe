import { afterEach, describe, expect, it } from "vitest";

import {
  accessTokenForPath,
  clearAccessToken,
  clearEditorAccessToken,
  storeAccessToken,
  storeEphemeralAccessToken,
} from "./authStorage";

afterEach(() => clearAccessToken());

describe("token slots", () => {
  it("keeps the user token when an editor session starts and routes by path", () => {
    storeAccessToken("user-token-0123456789");
    storeEphemeralAccessToken("editor-token-0123456789");

    expect(accessTokenForPath("/api/v1/editor/me")).toBe("editor-token-0123456789");
    expect(accessTokenForPath("/api/v1/projects")).toBe("user-token-0123456789");
    expect(accessTokenForPath("/api/v1/auth/editor/launch")).toBe("user-token-0123456789");

    clearEditorAccessToken();
    expect(accessTokenForPath("/api/v1/editor/me")).toBeNull();
    expect(accessTokenForPath("/api/v1/projects")).toBe("user-token-0123456789");
  });

  it("routes absolute editor URLs on the API origin to the editor token", () => {
    storeAccessToken("user-token-0123456789");
    storeEphemeralAccessToken("editor-token-0123456789");

    expect(accessTokenForPath("https://api.example.test/api/v1/editor/assets/a1/content")).toBe(
      "editor-token-0123456789",
    );
    expect(accessTokenForPath("https://api.example.test/api/v1/projects")).toBe("user-token-0123456789");
    expect(accessTokenForPath("/api/v1/editorial")).toBe("user-token-0123456789");
  });

  it("clears both slots on full sign-out", () => {
    storeAccessToken("user-token-0123456789");
    storeEphemeralAccessToken("editor-token-0123456789");
    clearAccessToken();
    expect(accessTokenForPath("/api/v1/editor/me")).toBeNull();
    expect(accessTokenForPath("/api/v1/projects")).toBeNull();
  });
});
