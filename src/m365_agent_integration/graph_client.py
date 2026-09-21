from __future__ import annotations

import time
from collections.abc import Awaitable, Callable
from typing import Any, Protocol
from urllib.parse import urlparse

import httpx

from .redaction import redact_text


class TokenProvider(Protocol):
    async def get_access_token(self, *, force_refresh: bool = False) -> str: ...

    def clear_cache(self) -> None: ...


class GraphClientError(RuntimeError):
    """Base class for safe Graph client errors."""


class GraphTransportError(GraphClientError):
    """Raised for timeout, network, redirect, and malformed response failures."""


class GraphAPIError(GraphClientError):
    """Raised for a non-success Graph response without exposing its body."""

    def __init__(self, status_code: int, endpoint: str, error_code: str | None = None) -> None:
        self.status_code = status_code
        self.endpoint = endpoint
        self.error_code = error_code
        suffix = f" ({error_code})" if error_code else ""
        super().__init__(f"Microsoft Graph returned HTTP {status_code} for {endpoint}{suffix}")


AuditCallback = Callable[[dict[str, Any]], None]


def _endpoint_label(url: str) -> str:
    path = urlparse(url).path
    if "/calendarView" in path:
        return "graph:/users/{fixed}/calendarView"
    if "/mailFolders/" in path and "/messages" in path:
        return "graph:/users/{fixed}/mailFolders/{folder}/messages"
    if "/teams/" in path and "/channels/" in path:
        return "graph:/teams/{team}/channels/{channel}"
    if "/drives/" in path:
        return "graph:/drives/{fixed}"
    return "graph:/v1.0"


def _retry_after(response: httpx.Response, attempt: int) -> float:
    raw = response.headers.get("Retry-After", "").strip()
    try:
        return max(0.0, min(float(raw), 30.0)) if raw else min(2**attempt, 30.0)
    except ValueError:
        return min(2**attempt, 30.0)


def _error_code(response: httpx.Response) -> str | None:
    try:
        payload = response.json()
    except ValueError:
        return None
    candidate = payload.get("error", {}).get("code") if isinstance(payload, dict) else None
    return candidate if isinstance(candidate, str) and len(candidate) <= 80 else None


class GraphClient:
    """Async Graph client with host validation, bounded retries, and safe errors."""

    def __init__(
        self,
        token_provider: TokenProvider,
        *,
        base_url: str = "https://graph.microsoft.com/v1.0",
        timeout: float = 30.0,
        max_retries: int = 3,
        transport: httpx.AsyncBaseTransport | None = None,
        sleep: Callable[[float], Awaitable[None]] | None = None,
        audit: AuditCallback | None = None,
    ) -> None:
        parsed = urlparse(base_url.rstrip("/"))
        if parsed.scheme != "https" or parsed.hostname != "graph.microsoft.com":
            raise ValueError("Graph base URL must be the Microsoft Graph host")
        self.token_provider = token_provider
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.max_retries = max(0, int(max_retries))
        self.transport = transport
        self.sleep = sleep or _async_sleep
        self.audit = audit

    async def get_json(self, path_or_url: str, *, params: dict[str, Any] | None = None) -> Any:
        response = await self._request("GET", path_or_url, params=params)
        try:
            return response.json()
        except ValueError as exc:
            raise GraphTransportError("Microsoft Graph response was not valid JSON") from exc

    async def get_paginated(
        self,
        path_or_url: str,
        *,
        params: dict[str, Any] | None = None,
        max_items: int = 100,
    ) -> list[Any]:
        if max_items < 1:
            raise ValueError("max_items must be positive")
        next_url = self._resolve(path_or_url)
        next_params = params
        values: list[Any] = []
        seen: set[str] = set()
        while next_url and len(values) < max_items:
            if next_url in seen:
                raise GraphTransportError("Microsoft Graph pagination loop detected")
            seen.add(next_url)
            payload = await self.get_json(next_url, params=next_params)
            if not isinstance(payload, dict) or not isinstance(payload.get("value"), list):
                raise GraphTransportError("Microsoft Graph pagination response was malformed")
            values.extend(payload["value"][: max_items - len(values)])
            candidate = payload.get("@odata.nextLink")
            if candidate is not None and not isinstance(candidate, str):
                raise GraphTransportError("Microsoft Graph pagination link was malformed")
            if candidate:
                self._resolve(candidate)
            next_url, next_params = candidate, None
        return values

    async def _request(
        self,
        method: str,
        path_or_url: str,
        *,
        params: dict[str, Any] | None = None,
        json_body: Any | None = None,
    ) -> httpx.Response:
        url = self._resolve(path_or_url)
        endpoint = _endpoint_label(url)
        refreshed = False
        for attempt in range(self.max_retries + 1):
            token = await self.token_provider.get_access_token(force_refresh=refreshed)
            started = time.perf_counter()
            try:
                async with httpx.AsyncClient(
                    timeout=httpx.Timeout(self.timeout),
                    transport=self.transport,
                    follow_redirects=False,
                ) as client:
                    response = await client.request(
                        method,
                        url,
                        params=params,
                        json=json_body,
                        headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
                    )
            except httpx.TimeoutException:
                if attempt < self.max_retries:
                    await self.sleep(min(2**attempt, 30.0))
                    continue
                self._audit("timeout", endpoint, started)
                raise GraphTransportError("Microsoft Graph request timed out") from None
            except httpx.RequestError as exc:
                if attempt < self.max_retries:
                    await self.sleep(min(2**attempt, 30.0))
                    continue
                self._audit("network_error", endpoint, started, type(exc).__name__)
                raise GraphTransportError("Microsoft Graph network request failed") from None

            if response.status_code == 401 and not refreshed:
                refreshed = True
                self.token_provider.clear_cache()
                continue
            if response.status_code in {429, 500, 502, 503, 504} and attempt < self.max_retries:
                await self.sleep(_retry_after(response, attempt))
                continue
            if response.status_code >= 400:
                code = _error_code(response)
                self._audit(response.status_code, endpoint, started, code)
                raise GraphAPIError(response.status_code, endpoint, code)
            if 300 <= response.status_code < 400:
                self._audit(response.status_code, endpoint, started, "unexpected_redirect")
                raise GraphTransportError("Microsoft Graph returned an unexpected redirect")
            self._audit(response.status_code, endpoint, started)
            return response
        raise GraphTransportError("Microsoft Graph retry budget exhausted")

    def _resolve(self, path_or_url: str) -> str:
        if path_or_url.startswith(("http://", "https://")):
            url = path_or_url
        else:
            suffix = path_or_url if path_or_url.startswith("/") else "/" + path_or_url
            url = f"{self.base_url}{suffix}"
        parsed = urlparse(url)
        if (
            parsed.scheme != "https"
            or parsed.hostname != "graph.microsoft.com"
            or parsed.port not in (None, 443)
        ):
            raise GraphTransportError("Microsoft Graph URL is outside the allowlist")
        return url

    def _audit(
        self, status: int | str, endpoint: str, started: float, error_code: str | None = None
    ) -> None:
        if self.audit is None:
            return
        record: dict[str, Any] = {
            "status": status,
            "endpoint": endpoint,
            "duration_ms": int((time.perf_counter() - started) * 1000),
        }
        if error_code:
            record["error_code"] = redact_text(error_code)[:80]
        self.audit(record)


async def _async_sleep(delay: float) -> None:
    import asyncio

    await asyncio.sleep(delay)
