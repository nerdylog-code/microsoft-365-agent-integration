"""Official MCP Python SDK adapter for the same synthetic backend.

The stdio harness in ``stdio_server.py`` is deliberately dependency-light and
useful for protocol tests. This module proves that the public tool contract can
also be exposed through the MCP Python SDK used by the observed private
integration.
"""

from __future__ import annotations

from mcp.server.mcpserver import MCPServer
from mcp.types import ToolAnnotations

from .mcp_runtime import MockBackend

mcp = MCPServer(
    "Sanitized Microsoft 365 Agent Integration",
    instructions="Synthetic read-only MCP tools. No Microsoft tenant is contacted.",
)
_READ_ONLY = ToolAnnotations(read_only_hint=True, destructive_hint=False, open_world_hint=False)
_backend = MockBackend()


@mcp.tool(annotations=_READ_ONLY)
async def calendar_agenda(
    start_datetime: str, end_datetime: str, timezone: str | None = None
) -> dict:
    """Return a bounded synthetic calendar agenda."""
    return await _backend.execute(
        "calendar_agenda",
        {"start_datetime": start_datetime, "end_datetime": end_datetime, "timezone": timezone},
    )


@mcp.tool(annotations=_READ_ONLY)
async def mail_list_inbox(limit: int = 20) -> dict:
    """Return synthetic inbox metadata."""
    return await _backend.execute("mail_list_inbox", {"limit": limit})


@mcp.tool(annotations=_READ_ONLY)
async def mail_prepare_draft(
    to: list[str], subject: str, body: str, cc: list[str] | None = None
) -> dict:
    """Prepare a local draft preview without a remote write."""
    return await _backend.execute(
        "mail_prepare_draft", {"to": to, "subject": subject, "body": body, "cc": cc}
    )


@mcp.tool(annotations=_READ_ONLY)
async def teams_channel_history(
    team_ref: str,
    channel_ref: str,
    start_datetime: str,
    end_datetime: str,
    timezone: str | None = None,
    limit: int = 50,
) -> dict:
    """Return bounded synthetic Teams channel history."""
    return await _backend.execute("teams_channel_history", locals())


@mcp.tool(annotations=_READ_ONLY)
async def teams_channel_digest(
    team_ref: str,
    channel_ref: str,
    start_datetime: str,
    end_datetime: str,
    timezone: str | None = None,
    limit: int = 50,
) -> dict:
    """Classify only explicit leading markers in synthetic Teams history."""
    return await _backend.execute("teams_channel_digest", locals())


@mcp.tool(annotations=_READ_ONLY)
async def sharepoint_list_folder(target: str = "demo-folder") -> dict:
    """List synthetic SharePoint metadata for an allowlisted target."""
    return await _backend.execute("sharepoint_list_folder", {"target": target})


@mcp.tool(annotations=_READ_ONLY)
async def sharepoint_read_document(alias_or_known_item: str) -> dict:
    """Read one bounded synthetic SharePoint document."""
    return await _backend.execute(
        "sharepoint_read_document", {"alias_or_known_item": alias_or_known_item}
    )


@mcp.tool(annotations=_READ_ONLY)
async def powerplatform_list_flows() -> dict:
    """List synthetic flow metadata from a pinned development scope."""
    return await _backend.execute("powerplatform_list_flows", {})


def main() -> None:
    mcp.run("stdio")


if __name__ == "__main__":
    main()
