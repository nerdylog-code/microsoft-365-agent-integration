from __future__ import annotations

import asyncio

import httpx
import pytest

from m365_agent_integration.graph_client import GraphAPIError, GraphClient, GraphTransportError


class StaticTokenProvider:
    def __init__(self) -> None:
        self.calls: list[bool] = []

    async def get_access_token(self, *, force_refresh: bool = False) -> str:
        self.calls.append(force_refresh)
        return "synthetic-token"

    def clear_cache(self) -> None:
        return None


def run(coro):
    return asyncio.run(coro)


def test_401_refreshes_once_then_succeeds() -> None:
    responses = [
        httpx.Response(401, json={"error": {"code": "Unauthorized"}}),
        httpx.Response(200, json={"value": [{"id": "message-1"}]}),
    ]

    def handler(request: httpx.Request) -> httpx.Response:
        response = responses.pop(0)
        response.request = request
        return response

    provider = StaticTokenProvider()
    client = GraphClient(provider, transport=httpx.MockTransport(handler))

    assert run(client.get_json("/me/messages")) == {"value": [{"id": "message-1"}]}
    assert provider.calls == [False, True]


def test_403_is_not_retried_and_has_safe_error() -> None:
    provider = StaticTokenProvider()

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            403, json={"error": {"code": "Forbidden", "message": "private body"}}, request=request
        )

    client = GraphClient(provider, transport=httpx.MockTransport(handler))
    with pytest.raises(GraphAPIError) as caught:
        run(client.get_json("/me/messages"))
    assert caught.value.status_code == 403
    assert "private body" not in str(caught.value)
    assert provider.calls == [False]


def test_429_honors_retry_after_without_sleeping_in_test() -> None:
    calls = 0
    sleeps: list[float] = []

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            return httpx.Response(
                429,
                headers={"Retry-After": "0"},
                json={"error": {"code": "TooManyRequests"}},
                request=request,
            )
        return httpx.Response(200, json={"ok": True}, request=request)

    async def fake_sleep(delay: float) -> None:
        sleeps.append(delay)

    client = GraphClient(
        StaticTokenProvider(),
        transport=httpx.MockTransport(handler),
        sleep=fake_sleep,
        max_retries=2,
    )
    assert run(client.get_json("/me")) == {"ok": True}
    assert calls == 2
    assert sleeps == [0.0]


def test_invalid_json_and_timeout_are_safe_errors() -> None:
    provider = StaticTokenProvider()

    def invalid(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"not-json", request=request)

    client = GraphClient(provider, transport=httpx.MockTransport(invalid))
    with pytest.raises(GraphTransportError, match="valid JSON"):
        run(client.get_json("/me"))

    def timeout(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("private timeout detail", request=request)

    client = GraphClient(provider, transport=httpx.MockTransport(timeout), max_retries=0)
    with pytest.raises(GraphTransportError) as caught:
        run(client.get_json("/me"))
    assert "private timeout detail" not in str(caught.value)
