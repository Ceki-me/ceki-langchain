"""Smoke tests — verify the tool can be instantiated and respects API key."""
import os
import pytest


def test_requires_api_key(monkeypatch):
    monkeypatch.delenv("CEKI_API_KEY", raising=False)
    from langchain_ceki import CekiBrowserTool

    with pytest.raises(ValueError, match="CEKI_API_KEY"):
        CekiBrowserTool()


def test_accepts_api_key_param():
    from langchain_ceki import CekiBrowserTool

    tool = CekiBrowserTool(api_key="test_key_value")
    assert tool._resolved_key == "test_key_value"


def test_accepts_env_var(monkeypatch):
    monkeypatch.setenv("CEKI_API_KEY", "from_env")
    from langchain_ceki import CekiBrowserTool

    tool = CekiBrowserTool()
    assert tool._resolved_key == "from_env"


def test_tool_metadata():
    from langchain_ceki import CekiBrowserTool

    tool = CekiBrowserTool(api_key="x")
    assert tool.name == "ceki_browser"
    assert "real Chrome" in tool.description.lower()
