"""Secret and private-identifier scanner for the public repository."""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass(frozen=True)
class Finding:
    path: str
    line: int
    kind: str


JWT_RE = re.compile(r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\b")
BEARER_RE = re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/=-]{16,}")
GUID_RE = re.compile(
    r"\b[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}\b", re.I
)
PRIVATE_KEY_RE = re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----")
EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+\b")
SECRET_ASSIGNMENT_RE = re.compile(
    r"(?i)\b(?:MSGRAPH_CLIENT_SECRET|MSTEAMS_CLIENT_SECRET|POWERPLATFORM_CLIENT_SECRET)\s*=\s*(?!<)[^\s#]+"
)
SENSITIVE_QUERY_RE = re.compile(
    r"(?i)[?&](?:access_token|refresh_token|client_secret|code|state|sig|signature)=[^&\s]+"
)
_PERSONAL_PATH_RE = re.compile(r"(?:[A-Z]:[/\\]Users[/\\][^\s/\\]+|/(?:home|Users)/[^\s]+)")
INTERNAL_DOMAIN_RE = re.compile(r"\b[a-z0-9.-]+\.(?:local|internal|corp|lan)\b", re.I)
PUBLIC_DOMAINS = {"example.com", "example.org", "example.net"}
SKIP_PARTS = {
    ".git",
    ".venv",
    "venv",
    "__pycache__",
    ".pytest_cache",
    ".ruff_cache",
    "htmlcov",
    "dist",
    "build",
}


def _iter_text_files(root: Path):
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        ignored = path.name in {"PRIVATE_INVENTORY.md", "coverage.json", "pytest.xml"}
        if ignored or any(part in SKIP_PARTS for part in path.parts):
            continue
        if path.suffix.lower() in {".png", ".jpg", ".jpeg", ".gif", ".pdf", ".pyc", ".whl", ".zip"}:
            continue
        yield path


def _find_line(
    text: str, pattern: re.Pattern[str], kind: str, path: Path, findings: list[Finding]
) -> None:
    for line_number, line in enumerate(text.splitlines(), start=1):
        if pattern.search(line):
            findings.append(Finding(str(path), line_number, kind))


def scan_tree(root: Path) -> list[Finding]:
    findings: list[Finding] = []
    for path in _iter_text_files(root):
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        _find_line(text, JWT_RE, "jwt", path, findings)
        _find_line(text, BEARER_RE, "bearer_token", path, findings)
        _find_line(text, GUID_RE, "guid", path, findings)
        _find_line(text, PRIVATE_KEY_RE, "private_key", path, findings)
        _find_line(text, SECRET_ASSIGNMENT_RE, "client_secret", path, findings)
        _find_line(text, SENSITIVE_QUERY_RE, "sensitive_query", path, findings)
        _find_line(text, _PERSONAL_PATH_RE, "personal_path", path, findings)
        _find_line(text, INTERNAL_DOMAIN_RE, "internal_domain", path, findings)
        for line_number, line in enumerate(text.splitlines(), start=1):
            for match in EMAIL_RE.finditer(line):
                if match.group(0).startswith("@"):
                    continue
                domain = match.group(0).rsplit("@", 1)[-1].lower()
                if domain not in PUBLIC_DOMAINS:
                    findings.append(Finding(str(path), line_number, "private_email"))
    return findings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Fail-closed public repository secret scan")
    parser.add_argument("root", nargs="?", default=".")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    findings = scan_tree(Path(args.root).resolve())
    payload = {
        "status": "PASS" if not findings else "FAIL",
        "findings": [asdict(item) for item in findings],
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if not findings else 1


if __name__ == "__main__":
    raise SystemExit(main())
