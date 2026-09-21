from __future__ import annotations

import asyncio

import pytest

from m365_agent_integration.mcp_runtime import MCPRuntime, MockBackend, ToolInputError


def run(coro):
    return asyncio.run(coro)


def test_all_public_mock_tools_execute_without_remote_io() -> None:
    runtime = MCPRuntime(MockBackend())
    common = {
        "start_datetime": "2026-09-21T00:00:00Z",
        "end_datetime": "2026-09-22T00:00:00Z",
        "team_ref": "team-demo",
        "channel_ref": "channel-ops",
    }
    calls = [
        ("mail_list_inbox", {}),
        (
            "mail_prepare_draft",
            {"to": ["person@example.com"], "subject": "Synthetic", "body": "Preview"},
        ),
        ("teams_channel_history", common),
        ("teams_channel_digest", common),
        ("sharepoint_list_folder", {"target": "demo-folder"}),
        ("sharepoint_read_document", {"alias_or_known_item": "demo-folder/report.md"}),
        ("powerplatform_list_flows", {}),
    ]
    for name, args in calls:
        result = run(runtime.call_tool(name, args))
        assert result["isError"] is False
        assert (
            "remote" not in result["structuredContent"]
            or result["structuredContent"].get("remote_write_performed") is False
        )


def test_calendar_and_teams_input_boundaries_are_closed() -> None:
    runtime = MCPRuntime(MockBackend())
    with pytest.raises(ToolInputError, match="after"):
        run(
            runtime.call_tool(
                "calendar_agenda",
                {"start_datetime": "2026-09-22T00:00:00Z", "end_datetime": "2026-09-21T00:00:00Z"},
            )
        )
    with pytest.raises(ToolInputError, match="registered"):
        run(
            runtime.call_tool(
                "teams_channel_history",
                {
                    "team_ref": "unknown",
                    "channel_ref": "channel-ops",
                    "start_datetime": "2026-09-21T00:00:00Z",
                    "end_datetime": "2026-09-22T00:00:00Z",
                },
            )
        )
    with pytest.raises(ToolInputError, match="synthetic email"):
        run(
            runtime.call_tool(
                "mail_prepare_draft", {"to": ["not-an-email"], "subject": "x", "body": "y"}
            )
        )
