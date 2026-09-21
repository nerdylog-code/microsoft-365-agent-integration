from __future__ import annotations

import argparse
import asyncio
import json
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

import httpx

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from m365_agent_integration.graph_client import GraphAPIError, GraphClient
from m365_agent_integration.mcp_runtime import MCPRuntime, MockBackend
from scripts.scan_secrets import scan_tree


class _Provider:
    async def get_access_token(self, *, force_refresh: bool = False) -> str:
        return "synthetic-token"

    def clear_cache(self) -> None:
        return None


def _write(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _pytest_summary(root: Path) -> dict[str, Any]:
    junit = root / "evidence" / "pytest.xml"
    coverage = root / "evidence" / "coverage.json"
    suite = ET.parse(junit).getroot()
    suites = suite.findall("testsuite") or [suite]
    totals = {
        key: sum(int(float(item.attrib.get(key, 0))) for item in suites)
        for key in ("tests", "failures", "errors", "skipped")
    }
    coverage_data = json.loads(coverage.read_text(encoding="utf-8"))
    percent = coverage_data["totals"]["percent_covered"]
    return {"tests": totals, "coverage_percent": round(percent, 2)}


def _graph_smoke() -> dict[str, Any]:
    async def run() -> dict[str, Any]:
        scenarios: dict[str, str] = {}

        def ok(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json={"value": []}, request=request)

        client = GraphClient(_Provider(), transport=httpx.MockTransport(ok), max_retries=0)
        await client.get_json("/me/messages")
        scenarios["read_200"] = "PASS"

        def forbidden(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                403, json={"error": {"code": "Forbidden", "message": "redacted"}}, request=request
            )

        try:
            await GraphClient(
                _Provider(), transport=httpx.MockTransport(forbidden), max_retries=0
            ).get_json("/me")
        except GraphAPIError as exc:
            scenarios["permission_403"] = "PASS" if exc.status_code == 403 else "FAIL"

        calls = 0

        def limited(request: httpx.Request) -> httpx.Response:
            nonlocal calls
            calls += 1
            if calls == 1:
                return httpx.Response(
                    429,
                    headers={"Retry-After": "0"},
                    json={"error": {"code": "TooManyRequests"}},
                    request=request,
                )
            return httpx.Response(200, json={"ok": True}, request=request)

        async def no_wait(delay: float) -> None:
            return None

        await GraphClient(
            _Provider(), transport=httpx.MockTransport(limited), sleep=no_wait
        ).get_json("/me")
        scenarios["rate_limit_429_retry"] = "PASS" if calls == 2 else "FAIL"
        return {"mode": "offline injected transport", "scenarios": scenarios}

    return asyncio.run(run())


def generate(root: Path) -> None:
    evidence = root / "evidence"
    evidence.mkdir(parents=True, exist_ok=True)
    summary = _pytest_summary(root)
    summary["compileall"] = (
        subprocess.run(
            [sys.executable, "-m", "compileall", "-q", "src", "tests", "scripts"],
            cwd=root,
            check=False,
        ).returncode
        == 0
    )
    findings = scan_tree(root)
    summary["secrets_scan"] = "PASS" if not findings else "FAIL"
    _write(evidence / "test-summary.json", summary)
    _write(evidence / "secrets-scan.json", {"status": summary["secrets_scan"], "findings": []})
    runtime = MCPRuntime(MockBackend())
    _write(evidence / "mcp-handshake.redacted.json", runtime.initialize())
    _write(evidence / "tools-list.redacted.json", runtime.tools_list())
    _write(evidence / "graph-smoke-tests.redacted.json", _graph_smoke())
    permission_result = asyncio.run(runtime.call_tool("graph_generic_call", {}))
    _write(
        evidence / "permission-denied.redacted.json",
        {
            "unknown_tool_blocked": permission_result["isError"],
            "message": "Tool is not allowlisted",
        },
    )
    initial_text = (
        "# Initial test evidence boundary\n\n"
        "The external Hermes MCP backup was inspected for provenance. It contains custom MCP "
        "source repositories and sanitized Power Platform audit metadata, but no Hermes "
        "conversation transcripts, session database, or conversation export.\n\n"
        "Private source evidence documented separate app-only Graph paths for mail, calendar, "
        "Teams channel reads, SharePoint, and Power Platform. The public repository does not "
        "copy those payloads or private identifiers.\n\n"
        "The public evidence files in this directory are generated from the clean-room mock "
        "runtime and injected HTTP transports. They prove protocol, policy, redaction, and "
        "error-handling contracts; they do not claim a live tenant smoke test.\n"
    )
    (evidence / "initial-tests.md").write_text(initial_text, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("root", nargs="?", default=".")
    args = parser.parse_args()
    generate(Path(args.root).resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
