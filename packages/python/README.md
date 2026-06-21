# langchain-ceki

LangChain toolkit for [Ceki](https://ceki.me) — drive a real Chrome session from your LangChain agent. Structural tools that wrap [`ceki-sdk`](https://pypi.org/project/ceki-sdk/).

## Install

```bash
pip install langchain-ceki
```

## Use

```python
import os
os.environ["CEKI_API_KEY"] = "your_key_here"  # or export it

from langchain_ceki import CekiToolkit
from langchain.agents import AgentExecutor, create_tool_calling_agent

toolkit = CekiToolkit(default_rent={"schedule_id": 4242, "mode": "main"})
tools = toolkit.get_tools()

agent = create_tool_calling_agent(llm, tools, prompt)
executor = AgentExecutor(agent=agent, tools=tools)

try:
    result = await executor.ainvoke({
        "input": (
            "Open https://my-app.example.com, log in with the saved profile, "
            "and return the dashboard's headline number."
        ),
    })
    print(result["output"])
finally:
    await toolkit.aclose()  # ALWAYS — leaving sessions open burns credit
```

## Tools

| Tool | What it does |
|---|---|
| `ceki_rent_browser` | Rent a real Chrome session and return its `session_id`. Pass it to every other tool. |
| `ceki_navigate` | Open a URL. |
| `ceki_click` | Click at viewport coordinates. Mouse jitter ON by default; `human=False` to teleport. |
| `ceki_type` | Type text into the focused element. Cadence + jitter ON by default. |
| `ceki_scroll` | Scroll by `delta_y` pixels with easing. |
| `ceki_screenshot` | PNG of the current viewport as base64. |
| `ceki_snapshot` | Screenshot + drained chat messages from the provider. |
| `ceki_chat_send` | Send a chat message to the human provider (e.g. ask for a captcha code). |
| `ceki_stop` | End the session. Always call when done. |

Both sync (`tool._run` / `tool.invoke`) and async (`tool._arun` / `tool.ainvoke`) paths are supported. The sync path is safe to call from a synchronous LangChain runnable; calling it from inside an already-running event loop raises with a clear hint to switch to `ainvoke`.

Get an API key at [ceki.me](https://ceki.me).

## Use responsibly

Use only on sites you own or have authorization to operate on.

## License

MIT.
