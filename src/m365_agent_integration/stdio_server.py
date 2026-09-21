from __future__ import annotations

import argparse
import asyncio
import json
import sys
from typing import Any

from .mcp_runtime import MCPRuntime, MockBackend


def _response(request_id: Any, result: Any) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": request_id, "result": result}


def _error(request_id: Any, code: int, message: str) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}}


async def _dispatch(runtime: MCPRuntime, request: dict[str, Any]) -> dict[str, Any] | None:
    method = request.get("method")
    request_id = request.get("id")
    if method == "notifications/initialized":
        return None
    if method == "initialize":
        return _response(
            request_id, runtime.initialize(request.get("params", {}).get("clientInfo"))
        )
    if method == "tools/list":
        return _response(request_id, runtime.tools_list())
    if method == "tools/call":
        params = request.get("params") or {}
        try:
            result = await runtime.call_tool(params.get("name"), params.get("arguments", {}))
        except ValueError as exc:
            return _error(request_id, -32602, str(exc))
        return _response(request_id, result)
    return _error(request_id, -32601, "Method not found")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Sanitized MCP stdio server")
    parser.add_argument(
        "--mock", action="store_true", help="Use synthetic fixtures; this is the safe default"
    )
    parser.parse_args(argv)
    runtime = MCPRuntime(MockBackend())
    for raw in sys.stdin:
        if not raw.strip():
            continue
        try:
            request = json.loads(raw)
            if not isinstance(request, dict):
                raise ValueError("request must be an object")
            result = asyncio.run(_dispatch(runtime, request))
        except (json.JSONDecodeError, ValueError) as exc:
            result = _error(None, -32700, str(exc))
        if result is not None:
            sys.stdout.write(json.dumps(result, ensure_ascii=False, separators=(",", ":")) + "\n")
            sys.stdout.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
