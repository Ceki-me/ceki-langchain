/**
 * @langchain/ceki — LangChain toolkit for Ceki.
 *
 * Drive a real Chrome session from your LangChain agent — your own (via the
 * Ceki extension), or rented from the Ceki marketplace.
 *
 * Architecture: this package is a THIN WRAPPER over @ceki/sdk. The agent's
 * own LLM decides which low-level tool to call (rent_browser, navigate,
 * click, type, ...) and in what order. There is no server-side natural
 * language endpoint and no LLM lives inside this package.
 *
 * Use on sites you own or have authorization to operate on.
 */
import { DynamicStructuredTool, type StructuredToolInterface } from "@langchain/core/tools";
import { Browser, Client } from "@ceki/sdk";
import { z } from "zod";

export interface CekiToolkitOptions {
  /** API key from https://ceki.me dashboard. Defaults to CEKI_API_KEY env var. */
  apiKey?: string;
  /** Override API URL. Defaults to https://api.ceki.me (or CEKI_API_URL env). */
  apiUrl?: string;
  /** Override relay URL. Defaults to wss://relay.ceki.me (or CEKI_RELAY_URL env). */
  relayUrl?: string;
  /** Override chat URL. Defaults to https://chat.ceki.me (or CEKI_CHAT_URL env). */
  chatUrl?: string;
  /**
   * Default rent options applied when the agent calls `ceki_rent_browser`
   * without overriding them. Useful for pinning `{ mode: 'main' }` or a
   * specific schedule.
   */
  defaultRent?: {
    scheduleId?: number;
    mode?: "main" | "incognito";
  };
}

function resolveApiKey(opts: CekiToolkitOptions): string {
  const key = opts.apiKey ?? process.env.CEKI_API_KEY ?? "";
  if (!key) {
    throw new Error(
      "CEKI_API_KEY not set. Sign up at https://ceki.me and export the API key.",
    );
  }
  return key;
}

/**
 * Toolkit of structural LangChain tools that drive Ceki via @ceki/sdk.
 *
 * The toolkit owns a single `Client` (WebSocket to the Ceki relay) and a map
 * of active `Browser` sessions keyed by sessionId. Each tool either rents a
 * new session or operates on one the agent already rented in this run.
 *
 * @example
 * ```ts
 * import { CekiToolkit } from "@langchain/ceki";
 *
 * const toolkit = new CekiToolkit();
 * const tools = await toolkit.getTools();
 * // pass `tools` to any LangChain agent (createToolCallingAgent, ...).
 * // ...
 * await toolkit.close(); // shuts down WS + ends all open sessions
 * ```
 */
export class CekiToolkit {
  private readonly _apiKey: string;
  private readonly _connectOpts: {
    apiUrl?: string;
    relayUrl?: string;
    chatUrl?: string;
  };
  private readonly _defaultRent: NonNullable<CekiToolkitOptions["defaultRent"]>;
  private _client: Client | null = null;
  private readonly _sessions: Map<string, Browser> = new Map();

  constructor(opts: CekiToolkitOptions = {}) {
    this._apiKey = resolveApiKey(opts);
    this._connectOpts = {
      apiUrl: opts.apiUrl ?? process.env.CEKI_API_URL,
      relayUrl: opts.relayUrl ?? process.env.CEKI_RELAY_URL,
      chatUrl: opts.chatUrl ?? process.env.CEKI_CHAT_URL,
    };
    this._defaultRent = opts.defaultRent ?? {};
  }

  /** Build the array of LangChain tools backed by this toolkit. */
  async getTools(): Promise<StructuredToolInterface[]> {
    // Defer client creation until first tool invocation — getTools() must
    // not open a WebSocket, since the agent may decide not to use the
    // tools at all.
    return [
      this._rentBrowserTool(),
      this._navigateTool(),
      this._clickTool(),
      this._typeTool(),
      this._scrollTool(),
      this._screenshotTool(),
      this._snapshotTool(),
      this._chatSendTool(),
      this._stopTool(),
    ];
  }

  /**
   * End every open session and close the relay connection. Idempotent.
   * Call this in your agent's `finally` block so a stuck run doesn't leak
   * a rented browser.
   */
  async close(): Promise<void> {
    const sessions = Array.from(this._sessions.values());
    this._sessions.clear();
    await Promise.allSettled(sessions.map((b) => b.close()));
    if (this._client) {
      await this._client.disconnect();
      this._client = null;
    }
  }

  /** @internal — lazily open the relay connection. */
  private async _getClient(): Promise<Client> {
    if (!this._client) {
      this._client = await Client.create(this._apiKey, this._connectOpts);
    }
    return this._client;
  }

  /** @internal — resolve the Browser the agent referenced by sessionId. */
  private _requireSession(sessionId: string): Browser {
    const b = this._sessions.get(sessionId);
    if (!b) {
      throw new Error(
        `session_id=${sessionId} is not active. Call ceki_rent_browser first or pass an id returned by it.`,
      );
    }
    return b;
  }

  // ──────────────────────────────────────────────────────────────────────
  // Tool factories
  // ──────────────────────────────────────────────────────────────────────

  private _rentBrowserTool(): StructuredToolInterface {
    const schema = z.object({
      schedule_id: z
        .number()
        .int()
        .positive()
        .optional()
        .describe("Specific schedule_id to rent. Omit to take the default."),
      mode: z
        .enum(["main", "incognito"])
        .optional()
        .describe("Profile mode. 'main' uses the provider's own profile; 'incognito' is sandboxed."),
    });
    return new DynamicStructuredTool({
      name: "ceki_rent_browser",
      description:
        "Rent a real Chrome session from the Ceki marketplace. Returns a session_id you must pass to every other ceki_* tool. Call this BEFORE navigate/click/type/etc.",
      schema,
      func: async (input) => {
        const client = await this._getClient();
        const scheduleId = input.schedule_id ?? this._defaultRent.scheduleId;
        if (!scheduleId) {
          throw new Error(
            "ceki_rent_browser: schedule_id is required. Pass it explicitly or configure CekiToolkit({ defaultRent: { scheduleId } }).",
          );
        }
        const mode = input.mode ?? this._defaultRent.mode;
        const browser = await client.rent(scheduleId, mode ? { mode } : undefined);
        this._sessions.set(browser.sessionId, browser);
        return JSON.stringify({
          session_id: browser.sessionId,
          schedule_id: scheduleId,
          mode: mode ?? "incognito",
        });
      },
    });
  }

  private _navigateTool(): StructuredToolInterface {
    const schema = z.object({
      session_id: z.string().describe("Session id returned by ceki_rent_browser."),
      url: z.string().describe("Absolute URL (http/https) to open."),
    });
    return new DynamicStructuredTool({
      name: "ceki_navigate",
      description:
        "Open a URL in the rented Chrome session. Waits up to 30s for the navigation to complete.",
      schema,
      func: async (input) => {
        const browser = this._requireSession(input.session_id);
        const res = await browser.navigate(input.url);
        return JSON.stringify({ ok: true, url: res.url });
      },
    });
  }

  private _clickTool(): StructuredToolInterface {
    const schema = z.object({
      session_id: z.string(),
      x: z.number().describe("Viewport x coordinate (CSS pixels)."),
      y: z.number().describe("Viewport y coordinate (CSS pixels)."),
      human: z
        .boolean()
        .optional()
        .describe(
          "Pass false to skip mouse-jitter humanization for this call. Default: humanized.",
        ),
    });
    return new DynamicStructuredTool({
      name: "ceki_click",
      description:
        "Click at viewport coordinates in the rented session. Mouse jitter is ON by default; pass human=false to teleport.",
      schema,
      func: async (input) => {
        const browser = this._requireSession(input.session_id);
        await browser.click(input.x, input.y, { human: input.human });
        return JSON.stringify({ ok: true });
      },
    });
  }

  private _typeTool(): StructuredToolInterface {
    const schema = z.object({
      session_id: z.string(),
      text: z.string().describe("Text to type. The session keeps focus on whatever was last clicked."),
      human: z
        .boolean()
        .optional()
        .describe(
          "Pass false to skip typing humanization (flat keystrokes) for this call.",
        ),
    });
    return new DynamicStructuredTool({
      name: "ceki_type",
      description:
        "Type text into the currently-focused element of the rented session. Click an input first; humanization (cadence + jitter) is ON by default.",
      schema,
      func: async (input) => {
        const browser = this._requireSession(input.session_id);
        await browser.type(input.text, { human: input.human });
        return JSON.stringify({ ok: true });
      },
    });
  }

  private _scrollTool(): StructuredToolInterface {
    const schema = z.object({
      session_id: z.string(),
      delta_y: z.number().describe("Vertical scroll delta in CSS pixels (negative = scroll up)."),
      x: z.number().optional().describe("Origin x (default 0)."),
      y: z.number().optional().describe("Origin y (default 0)."),
      human: z.boolean().optional(),
    });
    return new DynamicStructuredTool({
      name: "ceki_scroll",
      description:
        "Scroll the rented session by delta_y CSS pixels. Easing is ON by default; pass human=false for a raw CDP wheel.",
      schema,
      func: async (input) => {
        const browser = this._requireSession(input.session_id);
        await browser.scroll({
          x: input.x,
          y: input.y,
          deltaY: input.delta_y,
          human: input.human,
        });
        return JSON.stringify({ ok: true });
      },
    });
  }

  private _screenshotTool(): StructuredToolInterface {
    const schema = z.object({
      session_id: z.string(),
    });
    return new DynamicStructuredTool({
      name: "ceki_screenshot",
      description:
        "Take a PNG screenshot of the rented session's current viewport. Returns a base64 data URL.",
      schema,
      func: async (input) => {
        const browser = this._requireSession(input.session_id);
        const shot = await browser.screenshot();
        const base64 = Buffer.isBuffer(shot)
          ? shot.toString("base64")
          : (shot as { data: string }).data;
        return JSON.stringify({
          ok: true,
          mime: "image/png",
          base64,
          bytes: Math.floor((base64.length * 3) / 4),
        });
      },
    });
  }

  private _snapshotTool(): StructuredToolInterface {
    const schema = z.object({
      session_id: z.string(),
    });
    return new DynamicStructuredTool({
      name: "ceki_snapshot",
      description:
        "Take a screenshot AND drain pending chat messages from the provider. Returns a JSON blob with both.",
      schema,
      func: async (input) => {
        const browser = this._requireSession(input.session_id);
        const snap = await browser.snapshot();
        return JSON.stringify({
          ok: true,
          screenshot_base64: typeof snap.screenshot === "string" ? snap.screenshot : undefined,
          chat: snap.chat ?? [],
        });
      },
    });
  }

  private _chatSendTool(): StructuredToolInterface {
    const schema = z.object({
      session_id: z.string(),
      text: z.string().describe("Message to send to the human provider via the in-session chat."),
    });
    return new DynamicStructuredTool({
      name: "ceki_chat_send",
      description:
        "Send a chat message to the human provider of the rented session (e.g. to ask for a captcha or 2FA code).",
      schema,
      func: async (input) => {
        const browser = this._requireSession(input.session_id);
        await browser.chat.send(input.text);
        return JSON.stringify({ ok: true });
      },
    });
  }

  private _stopTool(): StructuredToolInterface {
    const schema = z.object({
      session_id: z.string(),
    });
    return new DynamicStructuredTool({
      name: "ceki_stop",
      description:
        "End the rented Chrome session. Always call this when you're done — leaving sessions open burns the user's credit.",
      schema,
      func: async (input) => {
        const browser = this._requireSession(input.session_id);
        await browser.close();
        this._sessions.delete(input.session_id);
        return JSON.stringify({ ok: true });
      },
    });
  }
}

export default CekiToolkit;
