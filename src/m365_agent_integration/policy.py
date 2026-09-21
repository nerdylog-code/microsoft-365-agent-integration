from __future__ import annotations

from copy import deepcopy
from typing import Any


class ToolNotAllowed(PermissionError):
    """Raised when a tool is outside the public allowlist."""


_READ_ONLY = {"readOnlyHint": True, "destructiveHint": False, "openWorldHint": False}


def _schema(
    name: str, description: str, properties: dict[str, Any], required: list[str] | None = None
) -> dict[str, Any]:
    return {
        "name": name,
        "description": description,
        "inputSchema": {
            "type": "object",
            "properties": properties,
            "required": required or [],
            "additionalProperties": False,
        },
        "annotations": deepcopy(_READ_ONLY),
    }


_TOOL_SCHEMAS = [
    _schema(
        "calendar_agenda",
        "Read a bounded synthetic calendar agenda for the configured identity.",
        {
            "start_datetime": {"type": "string", "description": "ISO-8601 start timestamp"},
            "end_datetime": {"type": "string", "description": "ISO-8601 end timestamp"},
            "timezone": {
                "type": ["string", "null"],
                "description": "IANA timezone for offset-free input",
            },
        },
        ["start_datetime", "end_datetime"],
    ),
    _schema(
        "mail_list_inbox",
        "Read synthetic inbox metadata for the configured identity.",
        {"limit": {"type": "integer", "minimum": 1, "maximum": 100, "default": 20}},
    ),
    _schema(
        "mail_prepare_draft",
        "Prepare a local draft preview; this tool never writes or sends mail.",
        {
            "to": {"type": "array", "items": {"type": "string"}},
            "subject": {"type": "string"},
            "body": {"type": "string"},
            "cc": {"type": "array", "items": {"type": "string"}},
        },
        ["to", "subject", "body"],
    ),
    _schema(
        "teams_channel_history",
        "Read bounded history for an operator-registered synthetic channel alias.",
        {
            "team_ref": {"type": "string"},
            "channel_ref": {"type": "string"},
            "start_datetime": {"type": "string"},
            "end_datetime": {"type": "string"},
            "timezone": {"type": ["string", "null"]},
            "limit": {"type": "integer", "minimum": 1, "maximum": 100, "default": 50},
        },
        ["team_ref", "channel_ref", "start_datetime", "end_datetime"],
    ),
    _schema(
        "teams_channel_digest",
        "Classify only explicit decision, task, plan, status, blocker, and question markers.",
        {
            "team_ref": {"type": "string"},
            "channel_ref": {"type": "string"},
            "start_datetime": {"type": "string"},
            "end_datetime": {"type": "string"},
            "timezone": {"type": ["string", "null"]},
            "limit": {"type": "integer", "minimum": 1, "maximum": 100, "default": 50},
        },
        ["team_ref", "channel_ref", "start_datetime", "end_datetime"],
    ),
    _schema(
        "sharepoint_list_folder",
        "List synthetic SharePoint metadata for an allowlisted logical folder.",
        {"target": {"type": "string", "enum": ["demo-folder"]}},
    ),
    _schema(
        "sharepoint_read_document",
        "Read one bounded synthetic UTF-8 document by logical alias.",
        {"alias_or_known_item": {"type": "string", "enum": ["demo-folder/report.md"]}},
        ["alias_or_known_item"],
    ),
    _schema(
        "powerplatform_list_flows",
        "List synthetic flow metadata from a pinned development scope.",
        {},
    ),
]

_ALLOWED_TOOLS = {schema["name"] for schema in _TOOL_SCHEMAS}


def public_tool_schemas() -> list[dict[str, Any]]:
    return deepcopy(_TOOL_SCHEMAS)


def assert_tool_allowed(name: str) -> None:
    if name not in _ALLOWED_TOOLS:
        raise ToolNotAllowed(f"Tool is not allowlisted: {name}")
