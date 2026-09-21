from __future__ import annotations

import json
import re
from collections import Counter
from datetime import UTC, datetime, timedelta, timezone
from typing import Any

from .policy import ToolNotAllowed, assert_tool_allowed, public_tool_schemas


class ToolInputError(ValueError):
    """Raised when a public tool receives invalid bounded input."""


_SYNTHETIC_EVENTS = [
    {
        "event_id": "event-alpha",
        "subject": "Synthetic planning session",
        "body_preview": "Action: review the fixture",
        "start": "2026-09-21T09:00:00Z",
        "end": "2026-09-21T10:00:00Z",
        "organizer": "person@example.com",
        "is_cancelled": False,
    },
    {
        "event_id": "event-beta",
        "subject": "Synthetic overlap check",
        "body_preview": "",
        "start": "2026-09-21T09:30:00Z",
        "end": "2026-09-21T11:00:00Z",
        "organizer": "person@example.com",
        "is_cancelled": False,
    },
]
_SYNTHETIC_MESSAGES = [
    {
        "message_id": "message-alpha",
        "subject": "Synthetic request",
        "sender": "person@example.com",
        "received": "2026-09-21T08:00:00Z",
        "body_text": "Please review the synthetic fixture.",
        "has_attachments": False,
    },
    {
        "message_id": "message-beta",
        "subject": "Synthetic status",
        "sender": "other@example.com",
        "received": "2026-09-21T07:00:00Z",
        "body_text": "Status: fixture is ready.",
        "has_attachments": True,
    },
]
_SYNTHETIC_TEAMS = [
    {
        "message_id": "teams-message-alpha",
        "team_ref": "team-demo",
        "channel_ref": "channel-ops",
        "created": "2026-09-21T08:00:00Z",
        "author": "person@example.com",
        "body_text": "Decisão: keep the synthetic boundary",
        "web_url": "https://teams.microsoft.com/l/message/synthetic",
    },
    {
        "message_id": "teams-message-beta",
        "team_ref": "team-demo",
        "channel_ref": "channel-ops",
        "created": "2026-09-21T09:00:00Z",
        "author": "other@example.com",
        "body_text": "Tarefa: review the mock report",
        "web_url": "https://teams.microsoft.com/l/message/synthetic-2",
    },
    {
        "message_id": "teams-message-gamma",
        "team_ref": "team-demo",
        "channel_ref": "channel-ops",
        "created": "2026-09-21T10:00:00Z",
        "author": "person@example.com",
        "body_text": "Conversation without a leading marker.",
        "web_url": "https://teams.microsoft.com/l/message/synthetic-3",
    },
]


def _parse_datetime(value: Any, label: str, timezone_name: Any = None) -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise ToolInputError(f"{label} must be an ISO-8601 timestamp")
    candidate = value.strip()
    if candidate.endswith("Z"):
        candidate = candidate[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(candidate)
    except ValueError as exc:
        raise ToolInputError(f"{label} must be an ISO-8601 timestamp") from exc
    if parsed.tzinfo is None:
        if not isinstance(timezone_name, str) or not timezone_name:
            raise ToolInputError(f"{label} without an offset requires timezone")
        offsets = {
            "UTC": UTC,
            "Etc/UTC": UTC,
            "America/Sao_Paulo": timezone(timedelta(hours=-3)),
        }
        if timezone_name not in offsets:
            raise ToolInputError("timezone must be UTC, Etc/UTC, or America/Sao_Paulo in mock mode")
        parsed = parsed.replace(tzinfo=offsets[timezone_name])
    return parsed.astimezone(UTC)


def _window(args: dict[str, Any], label: str) -> tuple[datetime, datetime]:
    start = _parse_datetime(args.get("start_datetime"), "start_datetime", args.get("timezone"))
    end = _parse_datetime(args.get("end_datetime"), "end_datetime", args.get("timezone"))
    if end <= start:
        raise ToolInputError("end_datetime must be after start_datetime")
    if end - start > timedelta(days=31):
        raise ToolInputError(f"{label} window cannot exceed 31 days")
    return start, end


def _bounded_limit(value: Any, default: int = 50) -> int:
    if value is None:
        return default
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ToolInputError("limit must be a positive integer")
    return min(value, 100)


def _iso(value: datetime) -> str:
    return value.astimezone(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def _event_datetime(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _calendar_result(args: dict[str, Any]) -> dict[str, Any]:
    start, end = _window(args, "calendar")
    events = []
    for item in _SYNTHETIC_EVENTS:
        event_start = _event_datetime(item["start"])
        if start <= event_start < end:
            event = dict(item)
            event["explicit_actions"] = ["review the fixture"] if item["body_preview"] else []
            events.append(event)
    conflicts = []
    for index, current in enumerate(events):
        for other in events[index + 1 :]:
            if _event_datetime(other["start"]) < _event_datetime(current["end"]):
                conflicts.append({"event_ids": [current["event_id"], other["event_id"]]})
    return {
        "scope": "synthetic fixture calendar",
        "period": {
            "start": _iso(start),
            "end": _iso(end),
            "timezone": args.get("timezone") or "UTC",
        },
        "events": events,
        "events_returned": len(events),
        "has_more": False,
        "conflicts": conflicts,
        "summary": {
            "events_returned": len(events),
            "cancelled_events": sum(item["is_cancelled"] for item in events),
            "explicit_action_events": sum(bool(item["explicit_actions"]) for item in events),
            "conflicts_detected": len(conflicts),
            "truncated_by_limit": False,
        },
    }


def _mail_list(args: dict[str, Any]) -> dict[str, Any]:
    limit = _bounded_limit(args.get("limit"), default=20)
    messages = [dict(item) for item in _SYNTHETIC_MESSAGES[:limit]]
    return {
        "scope": "synthetic fixture mailbox",
        "messages": messages,
        "messages_returned": len(messages),
    }


def _draft_preview(args: dict[str, Any]) -> dict[str, Any]:
    recipients = args.get("to")
    if (
        not isinstance(recipients, list)
        or not recipients
        or any(not isinstance(item, str) or "@" not in item for item in recipients)
    ):
        raise ToolInputError("to must contain synthetic email addresses")
    subject = args.get("subject")
    body = args.get("body")
    if (
        not isinstance(subject, str)
        or not subject.strip()
        or not isinstance(body, str)
        or not body.strip()
    ):
        raise ToolInputError("subject and body are required")
    cc = args.get("cc") or []
    if not isinstance(cc, list) or any(not isinstance(item, str) or "@" not in item for item in cc):
        raise ToolInputError("cc must contain synthetic email addresses")
    return {
        "preview": {
            "to": recipients,
            "cc": cc,
            "subject": subject,
            "body_preview": body[:2_000],
            "send_enabled": False,
        },
        "approval_required": True,
        "remote_write_performed": False,
    }


def _teams_history(args: dict[str, Any]) -> dict[str, Any]:
    start, end = _window(args, "Teams")
    if args.get("team_ref") != "team-demo" or args.get("channel_ref") != "channel-ops":
        raise ToolInputError("team_ref/channel_ref are not registered synthetic aliases")
    limit = _bounded_limit(args.get("limit"), default=50)
    messages = [
        dict(item) for item in _SYNTHETIC_TEAMS if start <= _event_datetime(item["created"]) < end
    ][:limit]
    return {
        "scope": "synthetic RSC-authorized Teams channel",
        "resource": {"team_ref": "team-demo", "channel_ref": "channel-ops"},
        "period": {
            "start": _iso(start),
            "end": _iso(end),
            "timezone": args.get("timezone") or "UTC",
        },
        "messages": messages,
        "messages_returned": len(messages),
        "has_more": False,
    }


def _teams_digest(args: dict[str, Any]) -> dict[str, Any]:
    history = _teams_history(args)
    patterns = (
        ("decision", re.compile(r"^(?:Decisão|Decisao|Decision)\s*[:\-]\s*(.+)$", re.I)),
        ("assignment", re.compile(r"^(?:Tarefa|Task|Ação|Acao|Action)\s*[:\-]\s*(.+)$", re.I)),
        ("plan", re.compile(r"^(?:Plano|Plan|Próximo passo|Proximo passo)\s*[:\-]\s*(.+)$", re.I)),
        ("status", re.compile(r"^(?:Status|Andamento)\s*[:\-]\s*(.+)$", re.I)),
        ("blocker", re.compile(r"^(?:Bloqueio|Blocker)\s*[:\-]\s*(.+)$", re.I)),
        ("question", re.compile(r"^(?:Pergunta|Question|Dúvida|Duvida)\s*[:\-]\s*(.+)$", re.I)),
    )
    items = []
    for message in history["messages"]:
        for line in message["body_text"].splitlines():
            for kind, pattern in patterns:
                match = pattern.match(line.strip())
                if match:
                    items.append(
                        {
                            "classification": kind,
                            "text": match.group(1),
                            "source_message_id": message["message_id"],
                            "author": message["author"],
                            "created": message["created"],
                        }
                    )
                    break
    counts = Counter(item["classification"] for item in items)
    return {
        **history,
        "items": items,
        "summary": {
            "messages_returned": history["messages_returned"],
            "classified_items": len(items),
            "unclassified_messages": history["messages_returned"]
            - len({item["source_message_id"] for item in items}),
            "classification_counts": dict(sorted(counts.items())),
            "has_more": False,
        },
        "classification_policy": (
            "Only explicit leading markers are classified; unmarked text is not a confirmed fact."
        ),
    }


class MockBackend:
    """Synthetic backend used by default; it never performs network I/O."""

    async def execute(self, name: str, args: dict[str, Any]) -> dict[str, Any]:
        if name == "calendar_agenda":
            return _calendar_result(args)
        if name == "mail_list_inbox":
            return _mail_list(args)
        if name == "mail_prepare_draft":
            return _draft_preview(args)
        if name == "teams_channel_history":
            return _teams_history(args)
        if name == "teams_channel_digest":
            return _teams_digest(args)
        if name == "sharepoint_list_folder":
            if args.get("target") != "demo-folder":
                raise ToolInputError("target is not an allowlisted synthetic folder")
            return {
                "scope": "synthetic SharePoint drive",
                "target": "demo-folder",
                "items": [{"name": "report.md", "type": "file", "size": 42}],
                "count": 1,
            }
        if name == "sharepoint_read_document":
            if args.get("alias_or_known_item") != "demo-folder/report.md":
                raise ToolInputError("document alias is not allowlisted")
            return {
                "scope": "synthetic SharePoint drive",
                "name": "report.md",
                "text": "# Synthetic report\n",
                "size": 19,
            }
        if name == "powerplatform_list_flows":
            return {
                "scope": "synthetic development environment",
                "flows": [{"name": "synthetic-smoke-flow", "state": "draft"}],
                "count": 1,
            }
        raise ToolNotAllowed(f"Tool is not allowlisted: {name}")


class MCPRuntime:
    """Small MCP contract implementation for deterministic local execution."""

    protocol_version = "2025-06-18"

    def __init__(self, backend: MockBackend) -> None:
        self.backend = backend

    def initialize(self, client_info: dict[str, Any] | None = None) -> dict[str, Any]:
        return {
            "protocolVersion": self.protocol_version,
            "capabilities": {"tools": {}},
            "serverInfo": {"name": "sanitized-microsoft-365-integration", "version": "0.1.0"},
        }

    def tools_list(self) -> dict[str, Any]:
        return {"tools": public_tool_schemas()}

    async def call_tool(self, name: str, arguments: dict[str, Any] | None) -> dict[str, Any]:
        try:
            assert_tool_allowed(name)
        except ToolNotAllowed as exc:
            return {"isError": True, "content": [{"type": "text", "text": str(exc)}]}
        if not isinstance(arguments, dict):
            raise ToolInputError("arguments must be an object")
        result = await self.backend.execute(name, arguments)
        return {
            "isError": False,
            "content": [
                {"type": "text", "text": json.dumps(result, ensure_ascii=False, sort_keys=True)}
            ],
            "structuredContent": result,
        }
