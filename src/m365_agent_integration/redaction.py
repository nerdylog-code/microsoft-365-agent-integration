from __future__ import annotations

import re
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

_JWT_RE = re.compile(r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\b")
_BEARER_RE = re.compile(r"(?i)(\bBearer\s+)[A-Za-z0-9._~+/=-]{16,}")
_GUID_RE = re.compile(
    r"\b[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}\b",
    re.IGNORECASE,
)
_EMAIL_RE = re.compile(r"\b[^\s@<>]+@[^\s@<>]+\.[A-Za-z]{2,}\b")
_WINDOWS_PATH_RE = re.compile(r"(?i)\b[A-Z]:[/\\]Users[/\\][^\s/\\]+(?:[/\\][^\s]+)*")
_POSIX_PATH_RE = re.compile(r"(?<![A-Za-z0-9_])/(?:home|Users)/[^\s]+")
_SECRET_ASSIGNMENT_RE = re.compile(
    r"(?i)\b(client_secret|access_token|refresh_token|api[_-]?key|password)\s*[:=]\s*([^\s,;]+)"
)
_SENSITIVE_QUERY_KEYS = {
    "access_token",
    "refresh_token",
    "client_secret",
    "code",
    "state",
    "sig",
    "signature",
}
_PUBLIC_DOMAINS = {"example.com", "example.org", "example.net"}


def _redact_url_query(value: str) -> str:
    try:
        parts = urlsplit(value)
    except ValueError:
        return value
    if not parts.query:
        return value
    pairs = []
    changed = False
    for key, item in parse_qsl(parts.query, keep_blank_values=True):
        if key.lower() in _SENSITIVE_QUERY_KEYS:
            item = "<REDACTED>"
            changed = True
        pairs.append((key, item))
    if not changed:
        return value
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(pairs), parts.fragment))


def redact_text(value: str) -> str:
    """Redact credentials, private identifiers, PII, and personal paths."""
    result = value
    result = _JWT_RE.sub("<JWT_REDACTED>", result)
    result = _BEARER_RE.sub(r"\1<BEARER_REDACTED>", result)
    result = _GUID_RE.sub("<GUID_REDACTED>", result)
    result = _WINDOWS_PATH_RE.sub("<PERSONAL_PATH_REDACTED>", result)
    result = _POSIX_PATH_RE.sub("<PERSONAL_PATH_REDACTED>", result)

    def redact_email(match: re.Match[str]) -> str:
        address = match.group(0)
        domain = address.rsplit("@", 1)[-1].lower()
        return address if domain in _PUBLIC_DOMAINS else "<EMAIL_REDACTED>"

    result = _EMAIL_RE.sub(redact_email, result)
    result = _SECRET_ASSIGNMENT_RE.sub(r"\1=<SECRET_REDACTED>", result)
    result = _redact_url_query(result)
    return result
