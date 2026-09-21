from __future__ import annotations

import asyncio

import httpx
import pytest

from m365_agent_integration.audit import AuditEvent, serialize_audit_event
from m365_agent_integration.auth import AuthError, OAuthClientCredentialsProvider
from m365_agent_integration.config import Settings


def run(coro):
    return asyncio.run(coro)


def settings() -> Settings:
    return Settings.from_mapping(
        {
            "MSGRAPH_TENANT_ID": "tenant-synthetic",
            "MSGRAPH_CLIENT_ID": "client-synthetic",
            "MSGRAPH_CLIENT_SECRET": "secret-synthetic",
            "MSGRAPH_MAILBOX": "operator@example.com",
        },
        require_credentials=False,
    )


def test_oauth_provider_caches_and_clears_token() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(
            200, json={"access_token": f"token-{calls}", "expires_in": 3600}, request=request
        )

    provider = OAuthClientCredentialsProvider(settings(), transport=httpx.MockTransport(handler))
    assert run(provider.get_access_token()) == "token-1"
    assert run(provider.get_access_token()) == "token-1"
    provider.clear_cache()
    assert run(provider.get_access_token()) == "token-2"
    assert calls == 2


def test_oauth_provider_rejects_bad_responses_without_secret() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            401, json={"error": "invalid_client", "secret": "private"}, request=request
        )

    provider = OAuthClientCredentialsProvider(settings(), transport=httpx.MockTransport(handler))
    with pytest.raises(AuthError) as caught:
        run(provider.get_access_token())
    assert "private" not in str(caught.value)
    assert "secret-synthetic" not in str(caught.value)


def test_audit_event_is_compact_and_sorted() -> None:
    value = serialize_audit_event(AuditEvent(200, "graph:/v1.0", 4, quantity=2, error_code="ok"))
    assert (
        value
        == '{"duration_ms":4,"endpoint":"graph:/v1.0","error_code":"ok","quantity":2,"status":200}'
    )
    assert "payload" not in value
