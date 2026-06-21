# ceki-langchain

LangChain integrations for [Ceki](https://ceki.me) — drive a real Chrome browser from your LangChain or LangGraph agent.

This monorepo ships two packages:

| Package | Lang | Path | Status |
|---|---|---|---|
| [`@langchain/ceki`](./packages/ts) | TypeScript / JS | `packages/ts` | v0.1.0 (pre-publish) |
| [`langchain-ceki`](./packages/python) | Python | `packages/python` | v0.1.0 (pre-publish) |

Both packages are a thin wrapper over [ceki-sdk](https://pypi.org/project/ceki-sdk/) / [`@ceki/sdk`](https://www.npmjs.com/package/@ceki/sdk). They expose Ceki as a **toolkit** of structural LangChain tools — `ceki_rent_browser`, `ceki_navigate`, `ceki_click`, `ceki_type`, `ceki_scroll`, `ceki_screenshot`, `ceki_snapshot`, `ceki_chat_send`, `ceki_stop` — and let the agent's own LLM plan the sequence. No server-side natural-language endpoint, no LLM inside the wrapper.

## Install

```bash
# TypeScript / Node
npm install @langchain/ceki @langchain/core

# Python
pip install langchain-ceki
```

## Use

```python
from langchain_ceki import CekiToolkit

toolkit = CekiToolkit(default_rent={"schedule_id": 4242})
tools = toolkit.get_tools()
# pass `tools` to any LangChain agent (create_tool_calling_agent, ...).
# When the run finishes:
await toolkit.aclose()
```

```ts
import { CekiToolkit } from "@langchain/ceki";

const toolkit = new CekiToolkit({ defaultRent: { scheduleId: 4242 } });
const tools = await toolkit.getTools();
// pass `tools` to any LangChain agent.
await toolkit.close();
```

Get an API key at [ceki.me](https://ceki.me).

## Use responsibly

Use only on sites you own or have authorization to operate on — your own apps, your own dashboards, public data within site Terms of Service, accessibility audits you're responsible for.

## Related

- [Ceki marketplace](https://ceki.me)
- [`ceki-sdk` on PyPI](https://pypi.org/project/ceki-sdk/) and [`@ceki/sdk` on npm](https://www.npmjs.com/package/@ceki/sdk) — low-level CLI + SDK

## License

MIT.
