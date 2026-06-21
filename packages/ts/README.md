# @ceki/langchain-ceki

LangChain toolkit for [Ceki](https://ceki.me) — drive a real Chrome session from your LangChain agent. Structural tools that wrap [`@ceki/sdk`](https://www.npmjs.com/package/@ceki/sdk).

## Install

```bash
npm install @ceki/langchain-ceki @langchain/core
```

## Use

```ts
import { CekiToolkit } from "@ceki/langchain-ceki";
import { createToolCallingAgent, AgentExecutor } from "langchain/agents";

const toolkit = new CekiToolkit({
  // apiKey defaults to process.env.CEKI_API_KEY
  defaultRent: { scheduleId: 4242, mode: "main" },
});

const tools = await toolkit.getTools();
const agent = createToolCallingAgent({ llm, tools, prompt });
const executor = new AgentExecutor({ agent, tools });

try {
  const result = await executor.invoke({
    input:
      "Open https://my-app.example.com, log in with the saved profile, and " +
      "return the dashboard's headline number.",
  });
  console.log(result.output);
} finally {
  await toolkit.close(); // ALWAYS — leaving sessions open burns credit
}
```

## Tools

| Tool | What it does |
|---|---|
| `ceki_rent_browser` | Rent a real Chrome session and return its `session_id`. Pass it to every other tool. |
| `ceki_navigate` | Open a URL. |
| `ceki_click` | Click at viewport coordinates. Mouse jitter ON by default; `human: false` to teleport. |
| `ceki_type` | Type text into the focused element. Cadence + jitter ON by default. |
| `ceki_scroll` | Scroll by `delta_y` pixels with easing. |
| `ceki_screenshot` | PNG of the current viewport as base64. |
| `ceki_snapshot` | Screenshot + drained chat messages from the provider. |
| `ceki_chat_send` | Send a chat message to the human provider (e.g. ask for a captcha code). |
| `ceki_stop` | End the session. Always call when done. |

Get an API key at [ceki.me](https://ceki.me).

## Use responsibly

Use only on sites you own or have authorization to operate on (your own apps, your own dashboards, public data within site Terms of Service, accessibility audits you're responsible for).

## License

MIT.
