import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { CekiToolkit } from "../src/index";

// Mock @ceki/sdk so the toolkit never opens a real WebSocket. We assert
// the toolkit's contract (tool list, routing to Browser methods, default
// rent options), not the SDK's behaviour.
const mockBrowser = {
  sessionId: "sess-test-1",
  navigate: vi.fn(async (url: string) => ({ url })),
  click: vi.fn(async () => undefined),
  type: vi.fn(async () => undefined),
  scroll: vi.fn(async () => undefined),
  screenshot: vi.fn(async () => Buffer.from([0x89, 0x50, 0x4e, 0x47])),
  snapshot: vi.fn(async () => ({ screenshot: "QUJD", chat: [{ from: "p", text: "hi" }] })),
  chat: { send: vi.fn(async () => undefined) },
  close: vi.fn(async () => undefined),
};

const mockClient = {
  rent: vi.fn(async () => mockBrowser),
  disconnect: vi.fn(async () => undefined),
};

vi.mock("@ceki/sdk", () => ({
  Client: { create: vi.fn(async () => mockClient) },
  Browser: class {},
}));

const originalEnv = { ...process.env };

beforeEach(() => {
  process.env.CEKI_API_KEY = "test-key";
  for (const fn of [
    mockBrowser.navigate,
    mockBrowser.click,
    mockBrowser.type,
    mockBrowser.scroll,
    mockBrowser.screenshot,
    mockBrowser.snapshot,
    mockBrowser.chat.send,
    mockBrowser.close,
    mockClient.rent,
    mockClient.disconnect,
  ]) {
    fn.mockClear();
  }
});

afterEach(() => {
  process.env = { ...originalEnv };
});

describe("CekiToolkit construction", () => {
  it("throws when CEKI_API_KEY is missing and no apiKey option is passed", () => {
    delete process.env.CEKI_API_KEY;
    expect(() => new CekiToolkit()).toThrow(/CEKI_API_KEY not set/);
  });

  it("accepts apiKey via option", () => {
    delete process.env.CEKI_API_KEY;
    const tk = new CekiToolkit({ apiKey: "explicit" });
    expect(tk).toBeInstanceOf(CekiToolkit);
  });
});

describe("CekiToolkit.getTools()", () => {
  it("returns the structural toolkit (9 tools)", async () => {
    const tk = new CekiToolkit();
    const tools = await tk.getTools();
    expect(tools.map((t) => t.name).sort()).toEqual(
      [
        "ceki_chat_send",
        "ceki_click",
        "ceki_navigate",
        "ceki_rent_browser",
        "ceki_screenshot",
        "ceki_scroll",
        "ceki_snapshot",
        "ceki_stop",
        "ceki_type",
      ].sort(),
    );
  });

  it("does NOT open a WebSocket — Client.create only runs on first tool call", async () => {
    const tk = new CekiToolkit();
    await tk.getTools();
    const sdk = await import("@ceki/sdk");
    expect((sdk.Client.create as ReturnType<typeof vi.fn>)).not.toHaveBeenCalled();
  });
});

describe("ceki_rent_browser", () => {
  it("rents with the schedule_id the agent passed", async () => {
    const tk = new CekiToolkit();
    const [rent] = await tk.getTools();
    const r = await rent.invoke({ schedule_id: 4242, mode: "main" });
    expect(mockClient.rent).toHaveBeenCalledWith(4242, { mode: "main" });
    const parsed = JSON.parse(r as string);
    expect(parsed.session_id).toBe("sess-test-1");
    expect(parsed.schedule_id).toBe(4242);
    expect(parsed.mode).toBe("main");
  });

  it("falls back to defaultRent.scheduleId when the agent omits it", async () => {
    const tk = new CekiToolkit({ defaultRent: { scheduleId: 9, mode: "incognito" } });
    const [rent] = await tk.getTools();
    await rent.invoke({});
    expect(mockClient.rent).toHaveBeenCalledWith(9, { mode: "incognito" });
  });

  it("throws when no schedule_id is available anywhere", async () => {
    const tk = new CekiToolkit();
    const [rent] = await tk.getTools();
    await expect(rent.invoke({})).rejects.toThrow(/schedule_id is required/);
  });
});

describe("session-bound tools", () => {
  async function rentSession() {
    const tk = new CekiToolkit({ defaultRent: { scheduleId: 1 } });
    const tools = await tk.getTools();
    const rent = tools.find((t) => t.name === "ceki_rent_browser")!;
    await rent.invoke({});
    return { tk, tools };
  }

  it("ceki_navigate forwards url to Browser.navigate", async () => {
    const { tools } = await rentSession();
    const nav = tools.find((t) => t.name === "ceki_navigate")!;
    const r = await nav.invoke({ session_id: "sess-test-1", url: "https://example.com" });
    expect(mockBrowser.navigate).toHaveBeenCalledWith("https://example.com");
    expect(JSON.parse(r as string)).toEqual({ ok: true, url: "https://example.com" });
  });

  it("ceki_click forwards x/y/human to Browser.click", async () => {
    const { tools } = await rentSession();
    const click = tools.find((t) => t.name === "ceki_click")!;
    await click.invoke({ session_id: "sess-test-1", x: 10, y: 20, human: false });
    expect(mockBrowser.click).toHaveBeenCalledWith(10, 20, { human: false });
  });

  it("ceki_type forwards text/human to Browser.type", async () => {
    const { tools } = await rentSession();
    const type = tools.find((t) => t.name === "ceki_type")!;
    await type.invoke({ session_id: "sess-test-1", text: "hello" });
    expect(mockBrowser.type).toHaveBeenCalledWith("hello", { human: undefined });
  });

  it("ceki_scroll forwards delta_y as deltaY to Browser.scroll", async () => {
    const { tools } = await rentSession();
    const scroll = tools.find((t) => t.name === "ceki_scroll")!;
    await scroll.invoke({ session_id: "sess-test-1", delta_y: 200, x: 5, y: 6 });
    expect(mockBrowser.scroll).toHaveBeenCalledWith({
      x: 5,
      y: 6,
      deltaY: 200,
      human: undefined,
    });
  });

  it("ceki_screenshot returns a base64 + byte count", async () => {
    const { tools } = await rentSession();
    const shot = tools.find((t) => t.name === "ceki_screenshot")!;
    const r = JSON.parse((await shot.invoke({ session_id: "sess-test-1" })) as string);
    expect(r.ok).toBe(true);
    expect(r.mime).toBe("image/png");
    expect(typeof r.base64).toBe("string");
    expect(r.bytes).toBeGreaterThan(0);
  });

  it("ceki_snapshot includes both screenshot and chat", async () => {
    const { tools } = await rentSession();
    const snap = tools.find((t) => t.name === "ceki_snapshot")!;
    const r = JSON.parse((await snap.invoke({ session_id: "sess-test-1" })) as string);
    expect(r.screenshot_base64).toBe("QUJD");
    expect(r.chat).toEqual([{ from: "p", text: "hi" }]);
  });

  it("ceki_chat_send forwards to browser.chat.send", async () => {
    const { tools } = await rentSession();
    const chat = tools.find((t) => t.name === "ceki_chat_send")!;
    await chat.invoke({ session_id: "sess-test-1", text: "need OTP" });
    expect(mockBrowser.chat.send).toHaveBeenCalledWith("need OTP");
  });

  it("ceki_stop closes the session and forgets the id", async () => {
    const { tk, tools } = await rentSession();
    const stop = tools.find((t) => t.name === "ceki_stop")!;
    await stop.invoke({ session_id: "sess-test-1" });
    expect(mockBrowser.close).toHaveBeenCalledTimes(1);
    // After stop, navigate must refuse to use the freed id.
    const nav = tools.find((t) => t.name === "ceki_navigate")!;
    await expect(
      nav.invoke({ session_id: "sess-test-1", url: "https://x" }),
    ).rejects.toThrow(/not active/);
    await tk.close();
  });

  it("refuses any session-bound tool when the id was never rented", async () => {
    const tk = new CekiToolkit();
    const [, nav] = await tk.getTools();
    await expect(
      nav.invoke({ session_id: "never-rented", url: "https://x" }),
    ).rejects.toThrow(/not active/);
  });
});

describe("CekiToolkit.close()", () => {
  it("ends all open sessions and disconnects the relay", async () => {
    const tk = new CekiToolkit({ defaultRent: { scheduleId: 1 } });
    const tools = await tk.getTools();
    await tools[0].invoke({});
    await tk.close();
    expect(mockBrowser.close).toHaveBeenCalledTimes(1);
    expect(mockClient.disconnect).toHaveBeenCalledTimes(1);
  });

  it("is idempotent — calling twice does not throw", async () => {
    const tk = new CekiToolkit();
    await tk.close();
    await expect(tk.close()).resolves.not.toThrow();
  });
});
