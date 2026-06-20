/**
 * @langchain/ceki — LangChain tool for Ceki.
 *
 * Drive a real Chrome session from your LangChain agent — your own
 * (via the Ceki extension), or rented from the Ceki marketplace.
 *
 * Use on sites you own or have authorization to operate on.
 */
import { Tool } from "@langchain/core/tools";

export interface CekiBrowserToolOptions {
  /** API key from https://ceki.me dashboard. Defaults to CEKI_API_KEY env var. */
  apiKey?: string;
  /** Override API URL. Defaults to https://api.ceki.me */
  apiUrl?: string;
  /** Override schedule_id to rent. Defaults to first available via search. */
  scheduleId?: number;
  /** Timeout in ms for API calls. Defaults to 120000 (2 min). */
  timeoutMs?: number;
}

/**
 * LangChain tool that drives a real Chrome session via Ceki.
 *
 * @example
 * ```ts
 * import { CekiBrowserTool } from "@langchain/ceki";
 *
 * const tool = new CekiBrowserTool();
 * const result = await tool.invoke({
 *   task: "Navigate to https://my-app.example.com and return the page title",
 * });
 * ```
 */
export class CekiBrowserTool extends Tool {
  name = "ceki_browser";
  description = `Drive a real Chrome browser via Ceki marketplace. Input: a single natural-language task describing what to do in the browser (e.g. "go to URL, click X, return page text"). Returns: task result as text.

Use when:
- The target site requires a real browser (JS execution, full layout, residential network path)
- You're operating on a site you own or have authorization to use
- A headless browser or plain HTTP client would miss something important

Don't use when:
- The target site's Terms of Service prohibit automated access
- You're creating accounts on third-party services
- You're scraping data the site owner hasn't authorized you to collect
- A simple fetch() call would do the job`;

  private apiKey: string;
  private apiUrl: string;
  private scheduleId?: number;
  private timeoutMs: number;

  constructor(opts: CekiBrowserToolOptions = {}) {
    super();
    this.apiKey = opts.apiKey ?? process.env.CEKI_API_KEY ?? "";
    if (!this.apiKey) {
      throw new Error(
        "CEKI_API_KEY not set. Sign up at https://ceki.me and export the API key.",
      );
    }
    this.apiUrl = opts.apiUrl ?? "https://api.ceki.me";
    this.scheduleId = opts.scheduleId;
    this.timeoutMs = opts.timeoutMs ?? 120_000;
  }

  protected async _call(input: string): Promise<string> {
    const controller = new AbortController();
    const t = setTimeout(() => controller.abort(), this.timeoutMs);

    try {
      // Discover schedule_id if not pinned
      let schedule = this.scheduleId;
      if (!schedule) {
        const sr = await fetch(`${this.apiUrl}/api/browsers/search?limit=5`, {
          headers: { Authorization: `Bearer ${this.apiKey}` },
          signal: controller.signal,
        });
        if (!sr.ok) {
          throw new Error(`Ceki search failed: ${sr.status} ${await sr.text()}`);
        }
        const sj = (await sr.json()) as { data?: Array<{ schedule_id: number }> };
        const first = sj.data?.[0];
        if (!first) {
          return "No Ceki browsers currently available. Try again in a moment.";
        }
        schedule = first.schedule_id;
      }

      // Post task
      const tr = await fetch(`${this.apiUrl}/api/agent/tasks`, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${this.apiKey}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ task: input, schedule_id: schedule }),
        signal: controller.signal,
      });

      if (!tr.ok) {
        throw new Error(`Ceki task failed: ${tr.status} ${await tr.text()}`);
      }

      const text = await tr.text();
      return text;
    } finally {
      clearTimeout(t);
    }
  }
}

export default CekiBrowserTool;
