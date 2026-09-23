import { describe, expect, it } from "vitest";

import { parseLaunchTicket } from "./editorLaunch";

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
