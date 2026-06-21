/**
 * Quickstart — drive a real Chrome session via Ceki from a tool-calling agent.
 *
 *   CEKI_API_KEY=... OPENAI_API_KEY=... npx ts-node examples/quickstart.ts
 */
import { ChatOpenAI } from "@langchain/openai";
import { AgentExecutor, createToolCallingAgent } from "langchain/agents";
import { ChatPromptTemplate } from "@langchain/core/prompts";
import { CekiToolkit } from "@ceki/langchain-ceki";

async function main() {
  const toolkit = new CekiToolkit({
    // apiKey defaults to CEKI_API_KEY env var
    defaultRent: { mode: "incognito" /* pass scheduleId if you have one pinned */ },
  });

  const tools = await toolkit.getTools();
  const llm = new ChatOpenAI({ model: "gpt-4o-mini", temperature: 0 });
  const prompt = ChatPromptTemplate.fromMessages([
    ["system", "You drive a real Chrome browser via the ceki_* tools. Always end with ceki_stop."],
    ["human", "{input}"],
    ["placeholder", "{agent_scratchpad}"],
  ]);

  const agent = createToolCallingAgent({ llm, tools, prompt });
  const executor = new AgentExecutor({ agent, tools });

  try {
    const result = await executor.invoke({
      input:
        "Rent a browser (schedule_id 1), navigate to https://example.com, take a snapshot, " +
        "then stop the session and tell me the headline you saw.",
    });
    console.log(result.output);
  } finally {
    await toolkit.close();
  }
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
