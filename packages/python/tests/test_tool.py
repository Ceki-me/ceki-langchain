"""Test the Ceki LangChain toolkit (Variant C — wrapper-only).

Heavy mocks of the ceki-sdk Client/Browser so the suite never opens a real
WebSocket. We assert the toolkit's contract: tool shape, schemas,
delegation to Browser methods, default-rent fallback, retry/error path,
and session bookkeeping. The async path (`_arun`) gets explicit
coverage alongside the sync path (`_run`).
"""
from __future__ import annotations

import json
import types
from unittest.mock import AsyncMock, MagicMock

import pytest


# ──────────────────────────────────────────────────────────────────────────
# ceki-sdk stub injected BEFORE importing langchain_ceki, so the toolkit
# binds to our mocks. Each test resets the mocks via the `sdk` fixture.
# ──────────────────────────────────────────────────────────────────────────
@pytest.fixture(autouse=True)
def sdk(monkeypatch):
    browser = MagicMock()
    browser.session_id = "sess-test-1"
    browser.navigate = AsyncMock(return_value={"url": "https://example.com"})
    browser.click = AsyncMock(return_value=None)
    browser.type = AsyncMock(return_value=None)
    browser.scroll = AsyncMock(return_value=None)
    browser.screenshot = AsyncMock(return_value=b"\x89PNG\r\n")
    snap = types.SimpleNamespace(
        screenshot=b"\x01\x02\x03", chat=[{"from": "p", "text": "hi"}], ts=None
    )
    browser.snapshot = AsyncMock(return_value=snap)
    browser.chat = MagicMock()
    browser.chat.send = AsyncMock(return_value=None)
    browser.close = AsyncMock(return_value=None)

    client = MagicMock()
    client._connect = AsyncMock(return_value=None)
    client.rent = AsyncMock(return_value=browser)
    client.disconnect = AsyncMock(return_value=None)

    import langchain_ceki.toolkit as toolkit_mod

    monkeypatch.setattr(toolkit_mod, "Client", lambda **_kw: client)
    monkeypatch.setenv("CEKI_API_KEY", "test-key")

    yield types.SimpleNamespace(client=client, browser=browser)


# ──────────────────────────────────────────────────────────────────────────
# Construction
# ──────────────────────────────────────────────────────────────────────────
def test_requires_api_key(monkeypatch):
    monkeypatch.delenv("CEKI_API_KEY", raising=False)
    from langchain_ceki import CekiToolkit

    with pytest.raises(ValueError, match="CEKI_API_KEY"):
        CekiToolkit()


def test_accepts_api_key_param(monkeypatch):
    monkeypatch.delenv("CEKI_API_KEY", raising=False)
    from langchain_ceki import CekiToolkit

    tk = CekiToolkit(api_key="explicit")
    assert tk._api_key == "explicit"


def test_accepts_env_var():
    from langchain_ceki import CekiToolkit

    tk = CekiToolkit()
    assert tk._api_key == "test-key"


# ──────────────────────────────────────────────────────────────────────────
# Toolkit shape
# ──────────────────────────────────────────────────────────────────────────
def test_get_tools_returns_nine_structural_tools():
    from langchain_ceki import CekiToolkit

    tk = CekiToolkit()
    names = sorted(t.name for t in tk.get_tools())
    assert names == [
        "ceki_chat_send",
        "ceki_click",
        "ceki_navigate",
        "ceki_rent_browser",
        "ceki_screenshot",
        "ceki_scroll",
        "ceki_snapshot",
        "ceki_stop",
        "ceki_type",
    ]


def test_get_tools_does_not_open_websocket(sdk):
    from langchain_ceki import CekiToolkit

    tk = CekiToolkit()
    tk.get_tools()
    sdk.client._connect.assert_not_called()


# ──────────────────────────────────────────────────────────────────────────
# ceki_rent_browser
# ──────────────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_arun_rent_with_explicit_args(sdk):
    from langchain_ceki import CekiToolkit

    tk = CekiToolkit()
    tools = {t.name: t for t in tk.get_tools()}
    out = await tools["ceki_rent_browser"]._arun(schedule_id=4242, mode="main")
    sdk.client.rent.assert_awaited_once_with(4242, mode="main")
    parsed = json.loads(out)
    assert parsed["session_id"] == "sess-test-1"
    assert parsed["schedule_id"] == 4242
    assert parsed["mode"] == "main"


@pytest.mark.asyncio
async def test_arun_rent_falls_back_to_default(sdk):
    from langchain_ceki import CekiToolkit

    tk = CekiToolkit(default_rent={"schedule_id": 9, "mode": "incognito"})
    rent = tk.get_tools()[0]
    await rent._arun()
    sdk.client.rent.assert_awaited_once_with(9, mode="incognito")


@pytest.mark.asyncio
async def test_arun_rent_rejects_unknown_mode(sdk):
    from langchain_ceki import CekiToolkit

    tk = CekiToolkit(default_rent={"schedule_id": 1})
    rent = tk.get_tools()[0]
    with pytest.raises(ValueError, match="mode must be"):
        await rent._arun(mode="weird")


@pytest.mark.asyncio
async def test_arun_rent_raises_without_schedule(sdk):
    from langchain_ceki import CekiToolkit

    tk = CekiToolkit()
    rent = tk.get_tools()[0]
    with pytest.raises(ValueError, match="schedule_id is required"):
        await rent._arun()


# ──────────────────────────────────────────────────────────────────────────
# Session-bound tools
# ──────────────────────────────────────────────────────────────────────────
@pytest.fixture
async def rented(sdk):
    from langchain_ceki import CekiToolkit

    tk = CekiToolkit(default_rent={"schedule_id": 1})
    tools = {t.name: t for t in tk.get_tools()}
    await tools["ceki_rent_browser"]._arun()
    return types.SimpleNamespace(tk=tk, tools=tools)


@pytest.mark.asyncio
async def test_arun_navigate(rented, sdk):
    out = await rented.tools["ceki_navigate"]._arun(
        session_id="sess-test-1", url="https://example.com"
    )
    sdk.browser.navigate.assert_awaited_once_with("https://example.com")
    assert json.loads(out)["url"] == "https://example.com"


@pytest.mark.asyncio
async def test_arun_click_forwards_human_flag(rented, sdk):
    await rented.tools["ceki_click"]._arun(session_id="sess-test-1", x=10, y=20, human=False)
    sdk.browser.click.assert_awaited_once_with(10, 20, human=False)


@pytest.mark.asyncio
async def test_arun_type_default_human(rented, sdk):
    await rented.tools["ceki_type"]._arun(session_id="sess-test-1", text="hello")
    sdk.browser.type.assert_awaited_once_with("hello", human=None)


@pytest.mark.asyncio
async def test_arun_scroll_maps_delta_y(rented, sdk):
    await rented.tools["ceki_scroll"]._arun(
        session_id="sess-test-1", delta_y=200, x=5, y=6
    )
    sdk.browser.scroll.assert_awaited_once_with(x=5, y=6, delta_y=200, human=None)


@pytest.mark.asyncio
async def test_arun_screenshot_returns_base64(rented, sdk):
    out = json.loads(await rented.tools["ceki_screenshot"]._arun(session_id="sess-test-1"))
    assert out["mime"] == "image/png"
    assert out["base64"]
    assert out["bytes"] > 0


@pytest.mark.asyncio
async def test_arun_snapshot_drains_chat(rented, sdk):
    out = json.loads(await rented.tools["ceki_snapshot"]._arun(session_id="sess-test-1"))
    assert out["chat"] == [{"from": "p", "text": "hi"}]
    assert out["screenshot_base64"]


@pytest.mark.asyncio
async def test_arun_chat_send_forwards_text(rented, sdk):
    await rented.tools["ceki_chat_send"]._arun(
        session_id="sess-test-1", text="need OTP"
    )
    sdk.browser.chat.send.assert_awaited_once_with("need OTP")


@pytest.mark.asyncio
async def test_arun_stop_closes_and_forgets(rented, sdk):
    await rented.tools["ceki_stop"]._arun(session_id="sess-test-1")
    sdk.browser.close.assert_awaited_once()
    with pytest.raises(ValueError, match="not active"):
        await rented.tools["ceki_navigate"]._arun(
            session_id="sess-test-1", url="https://x"
        )


@pytest.mark.asyncio
async def test_arun_refuses_unknown_session(sdk):
    from langchain_ceki import CekiToolkit

    tk = CekiToolkit()
    tools = {t.name: t for t in tk.get_tools()}
    with pytest.raises(ValueError, match="not active"):
        await tools["ceki_navigate"]._arun(session_id="never-rented", url="https://x")


# ──────────────────────────────────────────────────────────────────────────
# Error / retry surface
# ──────────────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_arun_navigate_propagates_sdk_errors(rented, sdk):
    sdk.browser.navigate.side_effect = RuntimeError("CDP Page.navigate timed out")
    with pytest.raises(RuntimeError, match="timed out"):
        await rented.tools["ceki_navigate"]._arun(
            session_id="sess-test-1", url="https://example.com"
        )


@pytest.mark.asyncio
async def test_arun_rent_4xx_path(sdk):
    from langchain_ceki import CekiToolkit

    sdk.client.rent.side_effect = Exception("auth_failed (HTTP 401)")
    tk = CekiToolkit(default_rent={"schedule_id": 1})
    with pytest.raises(Exception, match="auth_failed"):
        await tk.get_tools()[0]._arun()


@pytest.mark.asyncio
async def test_arun_rent_retry_after_transient_failure(sdk):
    """Agent-side retry: first rent fails, second succeeds. The toolkit
    itself does not retry — that is the agent's responsibility — but it
    must remain usable after a failed call (no half-opened state)."""
    from langchain_ceki import CekiToolkit

    sdk.client.rent.side_effect = [
        RuntimeError("Browser is currently in use"),
        sdk.browser,
    ]
    tk = CekiToolkit(default_rent={"schedule_id": 1})
    rent = tk.get_tools()[0]
    with pytest.raises(RuntimeError, match="currently in use"):
        await rent._arun()
    out = json.loads(await rent._arun())
    assert out["session_id"] == "sess-test-1"


# ──────────────────────────────────────────────────────────────────────────
# Sync path — `_run` reaches `_arun` through the bridge thread
# ──────────────────────────────────────────────────────────────────────────
def test_run_sync_path_uses_bridge(sdk):
    from langchain_ceki import CekiToolkit

    tk = CekiToolkit(default_rent={"schedule_id": 7})
    tools = {t.name: t for t in tk.get_tools()}
    try:
        out = tools["ceki_rent_browser"].invoke({"schedule_id": 7})
        assert json.loads(out)["session_id"] == "sess-test-1"
        sdk.client.rent.assert_awaited_once_with(7, mode="incognito")
    finally:
        tk.close()


@pytest.mark.asyncio
async def test_sync_run_inside_running_loop_raises(sdk):
    """If the caller is already async, `_run` MUST NOT block — instead it
    raises so the agent author switches to `ainvoke`."""
    from langchain_ceki import CekiToolkit

    tk = CekiToolkit(default_rent={"schedule_id": 1})
    tools = {t.name: t for t in tk.get_tools()}
    await tools["ceki_rent_browser"]._arun()
    with pytest.raises(RuntimeError, match="inside a running event loop"):
        tools["ceki_navigate"]._run(session_id="sess-test-1", url="https://example.com")


# ──────────────────────────────────────────────────────────────────────────
# aclose() / close() lifecycle
# ──────────────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_aclose_ends_sessions_and_disconnects(sdk):
    from langchain_ceki import CekiToolkit

    tk = CekiToolkit(default_rent={"schedule_id": 1})
    await tk.get_tools()[0]._arun()
    await tk.aclose()
    sdk.browser.close.assert_awaited_once()
    sdk.client.disconnect.assert_awaited_once()


@pytest.mark.asyncio
async def test_aclose_is_idempotent(sdk):
    from langchain_ceki import CekiToolkit

    tk = CekiToolkit()
    await tk.aclose()
    await tk.aclose()


# ──────────────────────────────────────────────────────────────────────────
# Tool metadata sanity
# ──────────────────────────────────────────────────────────────────────────
def test_tool_metadata_visible_to_llm():
    from langchain_ceki import CekiToolkit

    tk = CekiToolkit()
    for tool in tk.get_tools():
        assert tool.name.startswith("ceki_")
        assert tool.description
        assert tool.args_schema is not None
