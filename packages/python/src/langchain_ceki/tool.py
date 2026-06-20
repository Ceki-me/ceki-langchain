"""LangChain BaseTool wrapper around the Ceki marketplace API."""
from __future__ import annotations

import os
from typing import Any, Optional

import httpx
from langchain_core.tools import BaseTool
from pydantic import BaseModel, ConfigDict, Field, PrivateAttr


class CekiBrowserInput(BaseModel):
    """Input schema for CekiBrowserTool."""

    task: str = Field(
        ...,
        description=(
            "Natural-language description of the browser task. "
            "Example: 'Navigate to https://my-app.example.com and return the page title.'"
        ),
    )


class CekiBrowserTool(BaseTool):
    """Drive a real Chrome session via the Ceki marketplace.

    Use only on sites you own or have authorization to operate on (your own apps,
    your own dashboards, public data within site Terms of Service, accessibility
    audits you're responsible for).

    Example:
        ```python
        from langchain_ceki import CekiBrowserTool

        tool = CekiBrowserTool()  # reads CEKI_API_KEY from env
        result = tool.invoke({
            "task": "Navigate to https://my-app.example.com and return the page title."
        })
        ```
    """

    name: str = "ceki_browser"
    description: str = (
        "Drive a real Chrome browser via Ceki marketplace. "
        "Input: a single natural-language task describing what to do in the browser. "
        "Returns: task result as text. "
        "Use when target site requires a real browser (JS, residential IP) AND you have "
        "authorization to operate on it. Don't use for sites with restrictive ToS, "
        "third-party account creation, or anything you wouldn't do manually."
    )
    args_schema: type[BaseModel] = CekiBrowserInput

    api_key: Optional[str] = None
    api_url: str = "https://api.ceki.me"
    schedule_id: Optional[int] = None
    timeout_s: float = 120.0

    model_config = ConfigDict(arbitrary_types_allowed=True)

    _resolved_key: str = PrivateAttr(default="")

    def model_post_init(self, _ctx: Any) -> None:
        key = self.api_key or os.environ.get("CEKI_API_KEY", "")
        if not key:
            raise ValueError(
                "CEKI_API_KEY not set. Sign up at https://ceki.me and export the API key."
            )
        self._resolved_key = key

    def _run(self, task: str, **_kwargs: Any) -> str:
        with httpx.Client(timeout=self.timeout_s) as client:
            schedule = self.schedule_id
            if schedule is None:
                r = client.get(
                    f"{self.api_url}/api/browsers/search",
                    headers={"Authorization": f"Bearer {self._resolved_key}"},
                    params={"limit": 5},
                )
                r.raise_for_status()
                data = r.json().get("data", [])
                if not data:
                    return "No Ceki browsers currently available. Try again in a moment."
                schedule = data[0]["schedule_id"]

            tr = client.post(
                f"{self.api_url}/api/agent/tasks",
                headers={"Authorization": f"Bearer {self._resolved_key}"},
                json={"task": task, "schedule_id": schedule},
            )
            tr.raise_for_status()
            return tr.text

    async def _arun(self, task: str, **_kwargs: Any) -> str:
        async with httpx.AsyncClient(timeout=self.timeout_s) as client:
            schedule = self.schedule_id
            if schedule is None:
                r = await client.get(
                    f"{self.api_url}/api/browsers/search",
                    headers={"Authorization": f"Bearer {self._resolved_key}"},
                    params={"limit": 5},
                )
                r.raise_for_status()
                data = r.json().get("data", [])
                if not data:
                    return "No Ceki browsers currently available. Try again in a moment."
                schedule = data[0]["schedule_id"]

            tr = await client.post(
                f"{self.api_url}/api/agent/tasks",
                headers={"Authorization": f"Bearer {self._resolved_key}"},
                json={"task": task, "schedule_id": schedule},
            )
            tr.raise_for_status()
            return tr.text
