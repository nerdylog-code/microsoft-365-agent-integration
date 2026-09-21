from __future__ import annotations

import asyncio
import json

import pytest

from m365_agent_integration.mcp_runtime import MCPRuntime, MockBackend


def run(coro):
    return asyncio.run(coro)


def test_initialize_and_tools_list_expose_the_sanitized_contract() -> None:
    runtime = MCPRuntime(MockBackend())
    initialized = runtime.initialize()
    listed = runtime.tools_list()

    assert initialized["protocolVersion"]
    assert initialized["capabilities"]["tools"] == {}
    names = {tool["name"] for tool in listed["tools"]}
    assert "calendar_agenda" in names
    assert "teams_channel_digest" in names
    assert "mail_send" not in names
    assert all("mailbox" not in tool["inputSchema"]["properties"] for tool in listed["tools"])


def test_mock_tool_execution_is_synthetic_and_read_only() -> None:
    runtime = MCPRuntime(MockBackend())
    result = run(
        runtime.call_tool(
            "calendar_agenda",
            {
                "start_datetime": "2026-09-21T00:00:00Z",
                "end_datetime": "2026-09-22T00:00:00Z",
            },
        )
    )

    assert result["isError"] is False
    payload = result["structuredContent"]
    assert payload["scope"] == "synthetic fixture calendar"
    assert payload["events_returned"] == 2
    assert payload["summary"]["conflicts_detected"] == 1
    assert "@" not in json.dumps(payload) or "example.com" in json.dumps(payload)


def test_tool_errors_are_structured_and_unknown_tools_are_blocked() -> None:
    runtime = MCPRuntime(MockBackend())
    result = run(runtime.call_tool("graph_generic_call", {}))
    assert result["isError"] is True
    assert "not allowlisted" in result["content"][0]["text"]

    with pytest.raises(ValueError, match="start_datetime"):
        run(runtime.call_tool("calendar_agenda", {"end_datetime": "2026-09-22T00:00:00Z"}))
