from __future__ import annotations

from pathlib import Path

from scripts.scan_secrets import scan_tree


def test_scanner_accepts_public_placeholders_and_synthetic_domains(tmp_path: Path) -> None:
    (tmp_path / "README.md").write_text(
        "Use <AZURE_TENANT_ID> and person@example.com with https://graph.microsoft.com.",
        encoding="utf-8",
    )
    assert scan_tree(tmp_path) == []


def test_scanner_rejects_bearer_tokens_and_private_guids(tmp_path: Path) -> None:
    jwt = "ey" + "JhbGciOiJIUzI1NiJ9.payloadx.signature"
    guid = "550e8400" + "-e29b-41d4-a716-446655440000"
    (tmp_path / "bad.txt").write_text("Bearer " + jwt + " " + guid, encoding="utf-8")
    findings = scan_tree(tmp_path)
    assert {finding.kind for finding in findings} >= {"jwt", "guid"}
