# @langchain/ceki

LangChain tool for [Ceki](https://ceki.me) — drive a real Chrome browser from your LangChain agent.

## Install

```bash
npm install @langchain/ceki @langchain/core
```

## Use

```ts
import { CekiBrowserTool } from "@langchain/ceki";

const tool = new CekiBrowserTool({
  // apiKey defaults to process.env.CEKI_API_KEY
});

const result = await tool.invoke(
  "Navigate to https://my-app.example.com and return the page title"
);
```

Get an API key at [ceki.me](https://ceki.me).

## Use responsibly

Use only on sites you own or have authorization to operate on (your own apps, your own dashboards, public data within site Terms of Service, accessibility audits you're responsible for).

## License

MIT.
