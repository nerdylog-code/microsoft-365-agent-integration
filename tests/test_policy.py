from __future__ import annotations

import pytest

from m365_agent_integration.policy import (
    ToolNotAllowed,
    assert_tool_allowed,
    public_tool_schemas,
)


def test_public_schemas_do_not_accept_identity_or_transport_selection() -> None:
    schemas = public_tool_schemas()
    assert schemas
    for schema in schemas:
        properties = schema["inputSchema"]["properties"]
        assert not {"mailbox", "user", "userPrincipalName", "tenant_id", "token"} & set(properties)
        assert not {"url", "method", "headers"} & set(properties)


def test_unknown_or_mutating_tools_are_denied() -> None:
    with pytest.raises(ToolNotAllowed):
        assert_tool_allowed("graph_generic_call")
    with pytest.raises(ToolNotAllowed):
        assert_tool_allowed("mail_send")


def test_read_tools_are_allowlisted() -> None:
    assert_tool_allowed("calendar_agenda")
    assert_tool_allowed("teams_channel_digest")
    assert_tool_allowed("sharepoint_list_folder")
