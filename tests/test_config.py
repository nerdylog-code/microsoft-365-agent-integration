from __future__ import annotations

import pytest

from m365_agent_integration.config import ConfigurationError, Settings


def test_placeholder_configuration_is_accepted_only_for_mock_mode() -> None:
    values = {
        "MSGRAPH_TENANT_ID": "<AZURE_TENANT_ID>",
        "MSGRAPH_CLIENT_ID": "<AZURE_CLIENT_ID>",
        "MSGRAPH_CLIENT_SECRET": "<CLIENT_SECRET_NOT_INCLUDED>",
        "MSGRAPH_MAILBOX": "<TEST_USER_EMAIL>",
    }

    settings = Settings.from_mapping(values, require_credentials=False)

    assert settings.tenant_id == "<AZURE_TENANT_ID>"
    assert settings.mailbox == "<TEST_USER_EMAIL>"
    with pytest.raises(ConfigurationError):
        Settings.from_mapping(values, require_credentials=True)


def test_incomplete_configuration_is_rejected() -> None:
    with pytest.raises(ConfigurationError, match="MSGRAPH_CLIENT_ID"):
        Settings.from_mapping({"MSGRAPH_TENANT_ID": "tenant"}, require_credentials=False)


def test_settings_never_expose_secret_in_repr() -> None:
    settings = Settings.from_mapping(
        {
            "MSGRAPH_TENANT_ID": "tenant",
            "MSGRAPH_CLIENT_ID": "client",
            "MSGRAPH_CLIENT_SECRET": "super-secret",
            "MSGRAPH_MAILBOX": "operator@example.com",
        },
        require_credentials=False,
    )

    assert "super-secret" not in repr(settings)
    assert "client" in repr(settings)
