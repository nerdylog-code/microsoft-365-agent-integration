from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class AuditEvent:
    status: int | str
    endpoint: str
    duration_ms: int
    quantity: int | None = None
    error_code: str | None = None

    def as_dict(self) -> dict[str, Any]:
        value: dict[str, Any] = {
            "status": self.status,
            "endpoint": self.endpoint,
            "duration_ms": max(0, int(self.duration_ms)),
        }
        if self.quantity is not None:
            value["quantity"] = max(0, int(self.quantity))
        if self.error_code:
            value["error_code"] = self.error_code[:80]
        return value


def serialize_audit_event(event: AuditEvent) -> str:
    """Serialize technical metadata only; never accept arbitrary payload fields."""
    return json.dumps(event.as_dict(), separators=(",", ":"), sort_keys=True)
