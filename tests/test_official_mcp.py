from __future__ import annotations

import asyncio

from mcp import Client

from m365_agent_integration.sdk_server import mcp


def test_official_mcp_sdk_lists_and_calls_synthetic_tools() -> None:
    async def run() -> None:
        async with Client(mcp) as client:
            listed = await client.list_tools()
            names = {tool.name for tool in listed.tools}
            assert {"calendar_agenda", "mail_list_inbox", "powerplatform_list_flows"} <= names
            result = await client.call_tool(
                "calendar_agenda",
                {"start_datetime": "2026-09-21T00:00:00Z", "end_datetime": "2026-09-22T00:00:00Z"},
            )
            assert result.is_error is False
            assert result.content

    asyncio.run(run())
