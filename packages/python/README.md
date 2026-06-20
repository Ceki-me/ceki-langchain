# langchain-ceki

LangChain tool for [Ceki](https://ceki.me) — drive a real Chrome browser from your LangChain agent.

## Install

```bash
pip install langchain-ceki
```

## Use

```python
import os
os.environ["CEKI_API_KEY"] = "your_key_here"  # or export it

from langchain_ceki import CekiBrowserTool

tool = CekiBrowserTool()
result = tool.invoke({
    "task": "Navigate to https://my-app.example.com and return the page title."
})
print(result)
```

Get an API key at [ceki.me](https://ceki.me).

## Use responsibly

Use only on sites you own or have authorization to operate on.

## License

MIT.
