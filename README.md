# ceki-langchain

LangChain integrations for [Ceki](https://ceki.me) — drive a real Chrome browser from your LangChain or LangGraph agent.

This monorepo ships two packages:

| Package | Lang | Path | Status |
|---|---|---|---|
| [`@langchain/ceki`](./packages/ts) | TypeScript / JS | `packages/ts` | v0.1.0 (pre-publish) |
| [`langchain-ceki`](./packages/python) | Python | `packages/python` | v0.1.0 (pre-publish) |

Both wrap the [ceki-sdk](https://pypi.org/project/ceki-sdk/) and the Ceki marketplace API. They give your agent a `ceki_browser` tool that takes a natural-language task and returns the result.

## Install

```bash
# TypeScript / Node
npm install @langchain/ceki @langchain/core

# Python
pip install langchain-ceki
```

## Use

```python
from langchain_ceki import CekiBrowserTool

tool = CekiBrowserTool()  # reads CEKI_API_KEY env var
result = tool.invoke({"task": "Navigate to https://my-app.example.com and return the page title."})
```

```ts
import { CekiBrowserTool } from "@langchain/ceki";

const tool = new CekiBrowserTool();
const result = await tool.invoke("Navigate to https://my-app.example.com and return the page title.");
```

Get an API key at [ceki.me](https://ceki.me).

## Use responsibly

Use only on sites you own or have authorization to operate on — your own apps, your own dashboards, public data within site Terms of Service, accessibility audits you're responsible for. See the upstream [SKILL.md](https://github.com/Ceki-me/realbrowser-skill/blob/main/SKILL.md) for appropriate and inappropriate use cases.

## Related

- [Ceki marketplace](https://ceki.me)
- [RealBrowser ClawHub skill](https://clawhub.ai/skills/realbrowser) (for OpenClaw users)
- [ceki-sdk on PyPI](https://pypi.org/project/ceki-sdk/) (low-level CLI + Python SDK)

## License

MIT.
