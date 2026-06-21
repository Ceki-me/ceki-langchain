"""LangChain toolkit for Ceki — structural tools backed by the async ceki-sdk.

Architecture (Variant C, fixed with the Ceki backend team):

  This package is a THIN WRAPPER. The agent's own LLM decides which low-level
  tool to call (rent_browser, navigate, click, type, ...) and in what order.
  There is no server-side natural-language endpoint and no LLM lives here.

Every tool exposes both `_run` (sync) and `_arun` (async). `_run` reuses the
toolkit's own asyncio loop when one is already running; otherwise it spins
up a private loop. This means the toolkit is safe to use from a synchronous
LangChain runnable AND inside an async agent.

Use only on sites you own or have authorization to operate on.
"""
from __future__ import annotations

import asyncio
import base64
import json
import os
import threading
from typing import Any, ClassVar, Optional

from ceki_sdk import Client
from ceki_sdk._browser import Browser
from langchain_core.tools import BaseTool
from pydantic import BaseModel, ConfigDict, Field, PrivateAttr


DEFAULT_API_URL = "https://api.ceki.me"
DEFAULT_RELAY_URL = "wss://relay.ceki.me"
DEFAULT_CHAT_URL = "https://chat.ceki.me"


# ──────────────────────────────────────────────────────────────────────────
# Async-bridge — lets sync `_run` reach the toolkit's coroutines without
# blocking an enclosing event loop. If the caller is sync (no running loop),
# we spin up a dedicated background loop in a daemon thread and reuse it.
# ──────────────────────────────────────────────────────────────────────────
class _AsyncBridge:
    def __init__(self) -> None:
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()

    def _ensure(self) -> asyncio.AbstractEventLoop:
        with self._lock:
            if self._loop is None or not self._loop.is_running():
                self._loop = asyncio.new_event_loop()
                self._thread = threading.Thread(
                    target=self._loop.run_forever, daemon=True, name="ceki-toolkit-loop"
                )
                self._thread.start()
            return self._loop

    def run(self, coro: Any) -> Any:
        # If we're already inside a running event loop, the caller is async
        # and should have hit `_arun` directly. Falling through to sync is
        # almost always a bug; raise so the agent author notices.
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            pass
        else:
            raise RuntimeError(
                "CekiToolkit sync tool was invoked from inside a running event loop. "
                "Use the async LangChain runnable path (`ainvoke`) so the tool's "
                "_arun() is called instead."
            )
        loop = self._ensure()
        return asyncio.run_coroutine_threadsafe(coro, loop).result()

    def close(self) -> None:
        with self._lock:
            loop = self._loop
            self._loop = None
            self._thread = None
        if loop and loop.is_running():
            loop.call_soon_threadsafe(loop.stop)


# ──────────────────────────────────────────────────────────────────────────
# Toolkit
# ──────────────────────────────────────────────────────────────────────────
class CekiToolkit:
    """Container that owns the Ceki Client + active Browser sessions.

    Build it once per agent run, call :meth:`get_tools` to get the structural
    toolkit, and remember to ``await toolkit.aclose()`` (or ``toolkit.close()``)
    in a ``finally`` block.

    Example::

        from langchain_ceki import CekiToolkit

        toolkit = CekiToolkit(default_rent={"schedule_id": 4242})
        tools = toolkit.get_tools()
        # pass `tools` to any LangChain agent
        # ...
        await toolkit.aclose()
    """

    def __init__(
        self,
        *,
        api_key: Optional[str] = None,
        api_url: Optional[str] = None,
        relay_url: Optional[str] = None,
        chat_url: Optional[str] = None,
        basic_auth: Optional[tuple[str, str]] = None,
        default_rent: Optional[dict[str, Any]] = None,
    ) -> None:
        key = api_key or os.environ.get("CEKI_API_KEY", "")
        if not key:
            raise ValueError(
                "CEKI_API_KEY not set. Sign up at https://ceki.me and export the API key."
            )
        self._api_key = key
        self._api_url = api_url or os.environ.get("CEKI_API_URL") or DEFAULT_API_URL
        self._relay_url = relay_url or os.environ.get("CEKI_RELAY_URL") or DEFAULT_RELAY_URL
        self._chat_url = chat_url or os.environ.get("CEKI_CHAT_URL") or DEFAULT_CHAT_URL
        self._basic_auth = basic_auth
        self._default_rent: dict[str, Any] = dict(default_rent or {})
        self._client: Optional[Client] = None
        self._sessions: dict[str, Browser] = {}
        self._bridge = _AsyncBridge()
        self._connect_lock = asyncio.Lock()

    # ─── lifecycle ────────────────────────────────────────────────────
    async def _aget_client(self) -> Client:
        if self._client is not None:
            return self._client
        async with self._connect_lock:
            if self._client is None:
                client = Client(
                    api_key=self._api_key,
                    relay_url=self._relay_url,
                    api_url=self._api_url,
                    chat_url=self._chat_url,
                    basic_auth=self._basic_auth,
                )
                await client._connect()  # type: ignore[attr-defined]
                self._client = client
            return self._client

    async def aclose(self) -> None:
        """Close every open session and disconnect from the relay."""
        sessions = list(self._sessions.values())
        self._sessions.clear()
        for s in sessions:
            try:
                await s.close()
            except Exception:
                pass
        if self._client is not None:
            try:
                await self._client.disconnect()
            except Exception:
                pass
            self._client = None
        self._bridge.close()

    def close(self) -> None:
        """Sync variant of :meth:`aclose` for non-async agents."""
        self._bridge.run(self.aclose())

    # ─── session bookkeeping ──────────────────────────────────────────
    def _require_session(self, session_id: str) -> Browser:
        b = self._sessions.get(session_id)
        if b is None:
            raise ValueError(
                f"session_id={session_id!r} is not active. "
                "Call ceki_rent_browser first or pass an id returned by it."
            )
        return b

    # ─── public API ───────────────────────────────────────────────────
    def get_tools(self) -> list[BaseTool]:
        return [
            CekiRentBrowserTool(toolkit=self),
            CekiNavigateTool(toolkit=self),
            CekiClickTool(toolkit=self),
            CekiTypeTool(toolkit=self),
            CekiScrollTool(toolkit=self),
            CekiScreenshotTool(toolkit=self),
            CekiSnapshotTool(toolkit=self),
            CekiChatSendTool(toolkit=self),
            CekiStopTool(toolkit=self),
        ]


def get_ceki_tools(**kwargs: Any) -> list[BaseTool]:
    """Convenience: build a toolkit and return its tools in one line.

    The caller owns the toolkit and is responsible for closing it. To close,
    grab it off any tool: ``tools[0].toolkit.close()``.
    """
    tk = CekiToolkit(**kwargs)
    return tk.get_tools()


# ──────────────────────────────────────────────────────────────────────────
# Tool base
# ──────────────────────────────────────────────────────────────────────────
class _CekiToolBase(BaseTool):
    """Shared plumbing: ``_run`` defers to ``_arun`` through the bridge."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    toolkit: CekiToolkit = Field(..., exclude=True)

    def _run(self, *args: Any, **kwargs: Any) -> Any:
        return self.toolkit._bridge.run(self._arun(*args, **kwargs))


# ──────────────────────────────────────────────────────────────────────────
# Tool input schemas
# ──────────────────────────────────────────────────────────────────────────
class _RentInput(BaseModel):
    schedule_id: Optional[int] = Field(
        default=None,
        description="Specific schedule_id to rent. Omit to take the toolkit default.",
    )
    mode: Optional[str] = Field(
        default=None,
        description="Profile mode: 'main' or 'incognito'.",
    )


class _SessionOnly(BaseModel):
    session_id: str = Field(..., description="Session id returned by ceki_rent_browser.")


class _NavigateInput(_SessionOnly):
    url: str = Field(..., description="Absolute http/https URL to open.")


class _ClickInput(_SessionOnly):
    x: float
    y: float
    human: Optional[bool] = Field(
        default=None,
        description="Pass false to skip mouse-jitter humanization for this call.",
    )


class _TypeInput(_SessionOnly):
    text: str
    human: Optional[bool] = None


class _ScrollInput(_SessionOnly):
    delta_y: float = Field(..., description="Vertical scroll delta in CSS pixels (negative = up).")
    x: Optional[int] = 0
    y: Optional[int] = 0
    human: Optional[bool] = None


class _ChatSendInput(_SessionOnly):
    text: str = Field(..., description="Message to send to the human provider via chat.")


# ──────────────────────────────────────────────────────────────────────────
# Tools
# ──────────────────────────────────────────────────────────────────────────
class CekiRentBrowserTool(_CekiToolBase):
    name: ClassVar[str] = "ceki_rent_browser"
    description: ClassVar[str] = (
        "Rent a real Chrome session from the Ceki marketplace. Returns a session_id "
        "you must pass to every other ceki_* tool. Call this BEFORE navigate/click/type/etc."
    )
    args_schema: ClassVar[type[BaseModel]] = _RentInput

    async def _arun(
        self,
        schedule_id: Optional[int] = None,
        mode: Optional[str] = None,
        **_: Any,
    ) -> str:
        client = await self.toolkit._aget_client()
        sid = schedule_id or self.toolkit._default_rent.get("schedule_id")
        if sid is None:
            raise ValueError(
                "ceki_rent_browser: schedule_id is required. Pass it explicitly or "
                "configure CekiToolkit(default_rent={'schedule_id': ...})."
            )
        m = mode or self.toolkit._default_rent.get("mode") or "incognito"
        if m not in ("incognito", "main"):
            raise ValueError(f"mode must be 'main' or 'incognito', got {m!r}")
        browser = await client.rent(sid, mode=m)
        self.toolkit._sessions[browser.session_id] = browser
        return json.dumps(
            {"session_id": browser.session_id, "schedule_id": sid, "mode": m}
        )


class CekiNavigateTool(_CekiToolBase):
    name: ClassVar[str] = "ceki_navigate"
    description: ClassVar[str] = (
        "Open a URL in the rented Chrome session. Waits up to 30s for navigation."
    )
    args_schema: ClassVar[type[BaseModel]] = _NavigateInput

    async def _arun(self, session_id: str, url: str, **_: Any) -> str:
        b = self.toolkit._require_session(session_id)
        res = await b.navigate(url)
        return json.dumps({"ok": True, "url": res.get("url") if isinstance(res, dict) else url})


class CekiClickTool(_CekiToolBase):
    name: ClassVar[str] = "ceki_click"
    description: ClassVar[str] = (
        "Click at viewport coordinates in the rented session. Mouse jitter is ON by default; "
        "pass human=false to teleport."
    )
    args_schema: ClassVar[type[BaseModel]] = _ClickInput

    async def _arun(
        self, session_id: str, x: float, y: float, human: Optional[bool] = None, **_: Any
    ) -> str:
        b = self.toolkit._require_session(session_id)
        await b.click(x, y, human=human)
        return json.dumps({"ok": True})


class CekiTypeTool(_CekiToolBase):
    name: ClassVar[str] = "ceki_type"
    description: ClassVar[str] = (
        "Type text into the currently-focused element of the rented session. "
        "Click an input first; humanization (cadence + jitter) is ON by default."
    )
    args_schema: ClassVar[type[BaseModel]] = _TypeInput

    async def _arun(
        self, session_id: str, text: str, human: Optional[bool] = None, **_: Any
    ) -> str:
        b = self.toolkit._require_session(session_id)
        await b.type(text, human=human)
        return json.dumps({"ok": True})


class CekiScrollTool(_CekiToolBase):
    name: ClassVar[str] = "ceki_scroll"
    description: ClassVar[str] = (
        "Scroll the rented session by delta_y CSS pixels. Easing is ON by default; "
        "pass human=false for a raw CDP wheel."
    )
    args_schema: ClassVar[type[BaseModel]] = _ScrollInput

    async def _arun(
        self,
        session_id: str,
        delta_y: float,
        x: Optional[int] = 0,
        y: Optional[int] = 0,
        human: Optional[bool] = None,
        **_: Any,
    ) -> str:
        b = self.toolkit._require_session(session_id)
        await b.scroll(x=int(x or 0), y=int(y or 0), delta_y=int(delta_y), human=human)
        return json.dumps({"ok": True})


class CekiScreenshotTool(_CekiToolBase):
    name: ClassVar[str] = "ceki_screenshot"
    description: ClassVar[str] = (
        "Take a PNG screenshot of the rented session's current viewport. Returns base64."
    )
    args_schema: ClassVar[type[BaseModel]] = _SessionOnly

    async def _arun(self, session_id: str, **_: Any) -> str:
        b = self.toolkit._require_session(session_id)
        shot = await b.screenshot()
        if isinstance(shot, bytes):
            b64 = base64.b64encode(shot).decode("ascii")
        elif isinstance(shot, dict) and "data" in shot:
            b64 = shot["data"]
        else:
            raise RuntimeError(f"unexpected screenshot shape: {type(shot).__name__}")
        return json.dumps(
            {"ok": True, "mime": "image/png", "base64": b64, "bytes": (len(b64) * 3) // 4}
        )


class CekiSnapshotTool(_CekiToolBase):
    name: ClassVar[str] = "ceki_snapshot"
    description: ClassVar[str] = (
        "Take a screenshot AND drain pending chat messages from the provider. "
        "Returns a JSON blob with both."
    )
    args_schema: ClassVar[type[BaseModel]] = _SessionOnly

    async def _arun(self, session_id: str, **_: Any) -> str:
        b = self.toolkit._require_session(session_id)
        snap = await b.snapshot()
        screenshot = getattr(snap, "screenshot", None)
        if isinstance(screenshot, bytes):
            screenshot = base64.b64encode(screenshot).decode("ascii")
        return json.dumps(
            {
                "ok": True,
                "screenshot_base64": screenshot,
                "chat": getattr(snap, "chat", None) or [],
            },
            default=str,
        )


class CekiChatSendTool(_CekiToolBase):
    name: ClassVar[str] = "ceki_chat_send"
    description: ClassVar[str] = (
        "Send a chat message to the human provider of the rented session "
        "(e.g. to ask for a captcha code or 2FA)."
    )
    args_schema: ClassVar[type[BaseModel]] = _ChatSendInput

    async def _arun(self, session_id: str, text: str, **_: Any) -> str:
        b = self.toolkit._require_session(session_id)
        await b.chat.send(text)
        return json.dumps({"ok": True})


class CekiStopTool(_CekiToolBase):
    name: ClassVar[str] = "ceki_stop"
    description: ClassVar[str] = (
        "End the rented Chrome session. Always call this when you're done — leaving "
        "sessions open burns the user's credit."
    )
    args_schema: ClassVar[type[BaseModel]] = _SessionOnly

    async def _arun(self, session_id: str, **_: Any) -> str:
        b = self.toolkit._require_session(session_id)
        await b.close()
        self.toolkit._sessions.pop(session_id, None)
        return json.dumps({"ok": True})


__all__ = [
    "CekiToolkit",
    "get_ceki_tools",
    "CekiRentBrowserTool",
    "CekiNavigateTool",
    "CekiClickTool",
    "CekiTypeTool",
    "CekiScrollTool",
    "CekiScreenshotTool",
    "CekiSnapshotTool",
    "CekiChatSendTool",
    "CekiStopTool",
]
