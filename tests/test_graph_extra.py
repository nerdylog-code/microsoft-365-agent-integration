from __future__ import annotations

import asyncio

import httpx
import pytest

from m365_agent_integration.graph_client import GraphClient, GraphTransportError


class Provider:
    async def get_access_token(self, *, force_refresh: bool = False) -> str:
        return "synthetic-token"

    def clear_cache(self) -> None:
        return None


def run(coro):
    return asyncio.run(coro)


def test_paginated_graph_reads_next_links_and_limits_items() -> None:
    responses = [
        {"value": [{"id": "a"}], "@odata.nextLink": "https://graph.microsoft.com/v1.0/next"},
        {"value": [{"id": "b"}, {"id": "c"}]},
    ]

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=responses.pop(0), request=request)

    client = GraphClient(Provider(), transport=httpx.MockTransport(handler))
    assert run(client.get_paginated("/items", max_items=2)) == [{"id": "a"}, {"id": "b"}]


def test_pagination_rejects_loops_foreign_links_and_bad_shapes() -> None:
    def loop_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"value": [], "@odata.nextLink": "https://graph.microsoft.com/v1.0/items"},
            request=request,
        )

    client = GraphClient(Provider(), transport=httpx.MockTransport(loop_handler))
    with pytest.raises(GraphTransportError, match="loop"):
        run(client.get_paginated("/items"))

    with pytest.raises(GraphTransportError, match="outside"):
        run(client.get_json("https://evil.example/items"))

    def malformed(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, json={"value": {}, "@odata.nextLink": "https://evil.example/next"}, request=request
        )

    client = GraphClient(Provider(), transport=httpx.MockTransport(malformed))
    with pytest.raises(GraphTransportError, match="malformed"):
        run(client.get_paginated("/items"))


def test_server_error_retries_and_redirect_is_closed() -> None:
    calls = 0
    sleeps: list[float] = []

    def retry_handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            return httpx.Response(503, json={"error": {"code": "Unavailable"}}, request=request)
        return httpx.Response(200, json={"ok": True}, request=request)

    async def fake_sleep(delay: float) -> None:
        sleeps.append(delay)

    client = GraphClient(Provider(), transport=httpx.MockTransport(retry_handler), sleep=fake_sleep)
    assert run(client.get_json("/me")) == {"ok": True}
    assert sleeps == [1]

    def redirect_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(302, headers={"Location": "https://evil.example"}, request=request)

    client = GraphClient(Provider(), transport=httpx.MockTransport(redirect_handler), max_retries=0)
    with pytest.raises(GraphTransportError, match="redirect"):
        run(client.get_json("/me"))
