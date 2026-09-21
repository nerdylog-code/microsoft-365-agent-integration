from __future__ import annotations

from m365_agent_integration.redaction import redact_text


def test_redaction_removes_credentials_pii_and_private_paths() -> None:
    jwt = "ey" + "JhbGciOiJIUzI1NiJ9.payload.signature"
    guid = "550e8400" + "-e29b-41d4-a716-446655440000"
    value = (
        "Authorization: Bearer " + jwt + " "
        "operator@"
        + "private.example.org "
        + guid
        + " "
        + "C:/"
        + "Users/"
        + "PrivateUser/.hermes/.env "
        + "https://graph.microsoft.com/v1.0/messages?"
        + "access_token"
        + "=secret-value"
    )

    redacted = redact_text(value)

    assert "eyJhbGci" not in redacted
    assert ("operator@" + "private.example.org") not in redacted
    assert ("550e8400" + "-e29b-41d4-a716-446655440000") not in redacted
    assert "PrivateUser" not in redacted
    assert "secret-value" not in redacted


def test_redaction_preserves_synthetic_fixture_domains() -> None:
    assert "person@example.com" in redact_text("person@example.com")
