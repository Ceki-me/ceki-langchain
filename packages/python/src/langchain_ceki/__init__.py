"""LangChain toolkit for Ceki — drive a real Chrome session from your agent.

Use only on sites you own or have authorization to operate on.
"""
from langchain_ceki.toolkit import CekiToolkit, get_ceki_tools

__all__ = ["CekiToolkit", "get_ceki_tools"]
__version__ = "0.1.0"
