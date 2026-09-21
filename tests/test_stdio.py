from __future__ import annotations

import io
import json
import sys

from m365_agent_integration.stdio_server import main


def test_stdio_main_handles_handshake_list_call_and_unknown_method(monkeypatch, capsys) -> None:
    requests = "\n".join(
        [
            json.dumps(
                {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "initialize",
                    "params": {"clientInfo": {"name": "test"}},
                }
            ),
            json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}}),
            json.dumps({"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}}),
            json.dumps(
                {
                    "jsonrpc": "2.0",
                    "id": 3,
                    "method": "tools/call",
                    "params": {"name": "powerplatform_list_flows", "arguments": {}},
                }
            ),
            json.dumps({"jsonrpc": "2.0", "id": 4, "method": "unknown", "params": {}}),
        ]
    )
    monkeypatch.setattr(sys, "stdin", io.StringIO(requests))
    assert main(["--mock"]) == 0
    lines = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
    assert [line["id"] for line in lines] == [1, 2, 3, 4]
    assert lines[0]["result"]["capabilities"]["tools"] == {}
    assert lines[1]["result"]["tools"]
    assert lines[2]["result"]["isError"] is False
    assert lines[3]["error"]["code"] == -32601


def test_stdio_main_returns_parse_error(monkeypatch, capsys) -> None:
    monkeypatch.setattr(sys, "stdin", io.StringIO("not-json\n"))
    assert main(["--mock"]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["error"]["code"] == -32700
