from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from urllib.parse import urlparse


class ConfigurationError(ValueError):
    """Raised when configuration is missing, unsafe, or incomplete."""


_PLACEHOLDER_RE = re.compile(r"^<[^<>]+>$")
_EMAIL_RE = re.compile(r"^[^@\s\r\n]+@[^@\s\r\n]+\.[^@\s\r\n]+$")
_ALLOWED_AUTHORITY_HOST = "login.microsoftonline.com"


def _value(mapping: Mapping[str, str], name: str, default: str | None = None) -> str:
    raw = mapping.get(name, default)
    return (raw or "").strip()


def _is_placeholder(value: str) -> bool:
    return bool(_PLACEHOLDER_RE.fullmatch(value))


def _require(name: str, value: str, *, require_credentials: bool) -> str:
    if not value:
        raise ConfigurationError(f"Missing required configuration: {name}")
    if require_credentials and _is_placeholder(value):
        raise ConfigurationError(f"Placeholder is not valid for live configuration: {name}")
    return value


@dataclass(frozen=True, repr=False)
class Settings:
    """Typed settings with a representation that never includes the client secret."""

    tenant_id: str
    client_id: str
    client_secret: str
    mailbox: str
    scope: str = "https://graph.microsoft.com/.default"
    authority_url: str = "https://login.microsoftonline.com"

    @classmethod
    def from_mapping(
        cls,
        mapping: Mapping[str, str],
        *,
        require_credentials: bool = True,
    ) -> Settings:
        tenant_id = _require(
            "MSGRAPH_TENANT_ID",
            _value(mapping, "MSGRAPH_TENANT_ID"),
            require_credentials=require_credentials,
        )
        client_id = _require(
            "MSGRAPH_CLIENT_ID",
            _value(mapping, "MSGRAPH_CLIENT_ID"),
            require_credentials=require_credentials,
        )
        client_secret = _require(
            "MSGRAPH_CLIENT_SECRET",
            _value(mapping, "MSGRAPH_CLIENT_SECRET"),
            require_credentials=require_credentials,
        )
        mailbox = _require(
            "MSGRAPH_MAILBOX",
            _value(mapping, "MSGRAPH_MAILBOX"),
            require_credentials=require_credentials,
        )
        scope = _value(mapping, "MSGRAPH_SCOPE", "https://graph.microsoft.com/.default")
        authority_url = _value(
            mapping, "MSGRAPH_AUTHORITY_URL", "https://login.microsoftonline.com"
        ).rstrip("/")

        parsed = urlparse(authority_url)
        if (
            parsed.scheme != "https"
            or parsed.hostname != _ALLOWED_AUTHORITY_HOST
            or parsed.port not in (None, 443)
        ):
            raise ConfigurationError("MSGRAPH_AUTHORITY_URL must use the Microsoft login authority")
        if not _is_placeholder(mailbox) and not _EMAIL_RE.fullmatch(mailbox):
            raise ConfigurationError("MSGRAPH_MAILBOX must be a valid mailbox address")
        if not scope or "://" not in scope:
            raise ConfigurationError("MSGRAPH_SCOPE must be an absolute scope")
        return cls(tenant_id, client_id, client_secret, mailbox, scope, authority_url)

    @classmethod
    def from_environment(
        cls,
        *,
        require_credentials: bool = True,
    ) -> Settings:
        import os

        return cls.from_mapping(os.environ, require_credentials=require_credentials)

    @property
    def token_url(self) -> str:
        from urllib.parse import quote

        return f"{self.authority_url}/{quote(self.tenant_id, safe='')}/oauth2/v2.0/token"

    def __repr__(self) -> str:
        return (
            f"Settings(tenant_id={self.tenant_id!r}, client_id={self.client_id!r}, "
            f"mailbox={self.mailbox!r}, scope={self.scope!r}, "
            f"authority_url={self.authority_url!r}, client_secret=<redacted>)"
        )
