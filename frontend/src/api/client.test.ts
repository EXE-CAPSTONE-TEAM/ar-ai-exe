import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { storeEphemeralAccessToken } from "./authStorage";
import { ApiError, fetchStoredFile, isPresignedContentPath } from "./client";

const ASSET_ID = "0b7c7a7e-5f3a-4d8e-9c2a-1f2e3d4c5b6a";
const CONTENT_PATH = `/api/v1/editor/assets/${ASSET_ID}/content`;
const PRESIGNED = "https://acct.r2.cloudflarestorage.com/kusshoes/models/a.glb?X-Amz-Signature=abc";

function jsonResponse(body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status: 200,
    headers: { "Content-Type": "application/json" },
  });
}

beforeEach(() => {
  const store = new Map<string, string>();
  vi.stubGlobal("localStorage", {
    getItem: (key: string) => store.get(key) ?? null,
    setItem: (key: string, value: string) => store.set(key, value),
    removeItem: (key: string) => store.delete(key),
  });
  storeEphemeralAccessToken("editor-session-token");
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("isPresignedContentPath", () => {
  it("matches only KusShoes editor content routes", () => {
    expect(isPresignedContentPath(CONTENT_PATH)).toBe(true);
    expect(isPresignedContentPath(`/api/v1/editor/exports/${ASSET_ID}/content?t=1`)).toBe(true);
    expect(isPresignedContentPath(`/api/design-assets/${ASSET_ID}/download`)).toBe(false);
    expect(isPresignedContentPath(`/api/v1/editor/assets/${ASSET_ID}`)).toBe(false);
  });
});

describe("fetchStoredFile", () => {
  it("follows the presigned URL without cookies or the API bearer token", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        jsonResponse({ url: PRESIGNED, expiresIn: 900, filename: "shoe.glb", contentType: "model/gltf-binary" }),
      )
      .mockResolvedValueOnce(new Response(new Blob(["glTF"]), { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);

    const file = await fetchStoredFile(CONTENT_PATH);

    expect(fetchMock).toHaveBeenCalledTimes(2);
    const [apiCall, storageCall] = fetchMock.mock.calls;
    expect(apiCall[1].headers.Authorization).toBe("Bearer editor-session-token");
    expect(storageCall[0]).toBe(PRESIGNED);
    expect(storageCall[1].credentials).toBe("omit");
    expect(storageCall[1].headers).toBeUndefined();
    expect(file.filename).toBe("shoe.glb");
    expect(await file.blob.text()).toBe("glTF");
  });

  it("reads bytes directly from routes that serve files (local sidecar)", async () => {
    const fetchMock = vi.fn().mockResolvedValueOnce(new Response(new Blob(["bytes"]), { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);

    const file = await fetchStoredFile(`/api/design-assets/${ASSET_ID}/download`);

    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(file.filename).toBeNull();
    expect(await file.blob.text()).toBe("bytes");
  });

  it.each([["javascript:alert(1)"], ["https://user:pass@evil.test/x"], [42]])(
    "rejects an unusable storage URL (%s)",
    async (url) => {
      vi.stubGlobal("fetch", vi.fn().mockResolvedValueOnce(jsonResponse({ url, filename: "x" })));

      await expect(fetchStoredFile(CONTENT_PATH)).rejects.toBeInstanceOf(ApiError);
    },
  );
});
