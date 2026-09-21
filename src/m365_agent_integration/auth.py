from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from typing import Any

import httpx

from .config import Settings


class AuthError(RuntimeError):
    """Raised for safe OAuth token acquisition failures."""


@dataclass(frozen=True, repr=False)
class AccessToken:
    value: str
    expires_at: float

    def __repr__(self) -> str:
        return f"AccessToken(value=<redacted>, expires_at={self.expires_at!r})"


class OAuthClientCredentialsProvider:
    """Acquire and cache an app-only Microsoft Graph token."""

    def __init__(
        self,
        settings: Settings,
        *,
        timeout: float = 20.0,
        transport: httpx.AsyncBaseTransport | None = None,
        skew_seconds: int = 120,
    ) -> None:
        self.settings = settings
        self.timeout = timeout
        self.transport = transport
        self.skew_seconds = max(0, int(skew_seconds))
        self._cached: AccessToken | None = None
        self._lock = asyncio.Lock()

    async def get_access_token(self, *, force_refresh: bool = False) -> str:
        if not force_refresh and self._fresh():
            return self._cached.value  # type: ignore[union-attr]
        async with self._lock:
            if not force_refresh and self._fresh():
                return self._cached.value  # type: ignore[union-attr]
            self._cached = await self._fetch()
            return self._cached.value

    def clear_cache(self) -> None:
        self._cached = None

    def _fresh(self) -> bool:
        return (
            self._cached is not None and self._cached.expires_at > time.time() + self.skew_seconds
        )

    async def _fetch(self) -> AccessToken:
        try:
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(self.timeout), transport=self.transport
            ) as client:
                response = await client.post(
                    self.settings.token_url,
                    data={
                        "grant_type": "client_credentials",
                        "client_id": self.settings.client_id,
                        "client_secret": self.settings.client_secret,
                        "scope": self.settings.scope,
                    },
                    headers={"Content-Type": "application/x-www-form-urlencoded"},
                )
        except httpx.RequestError:
            raise AuthError("Microsoft Entra token request failed") from None
        if response.status_code >= 400:
            raise AuthError(
                f"Microsoft Entra token request failed with HTTP {response.status_code}"
            )
        try:
            payload: Any = response.json()
            token = payload["access_token"]
            expires_in = int(payload["expires_in"])
        except (ValueError, KeyError, TypeError):
            raise AuthError("Microsoft Entra token response was malformed") from None
        if not isinstance(token, str) or not token:
            raise AuthError("Microsoft Entra token response did not contain an access token")
        return AccessToken(token, time.time() + max(0, expires_in))
