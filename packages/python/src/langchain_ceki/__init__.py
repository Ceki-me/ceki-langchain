"""LangChain tool for Ceki — drive a real Chrome session from your agent.

Use only on sites you own or have authorization to operate on.
"""
from langchain_ceki.tool import CekiBrowserTool

__all__ = ["CekiBrowserTool"]
__version__ = "0.1.0"
