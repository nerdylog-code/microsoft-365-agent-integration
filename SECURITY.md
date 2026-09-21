# Security Policy

## Supported versions

Only the latest `main` branch is supported in this portfolio repository.

## Reporting a vulnerability

Do not open a public issue containing a secret, access token, mailbox address, tenant ID, private Graph ID, or corporate payload. Report security problems privately to the repository owner through GitHub's private vulnerability reporting flow when enabled.

## Non-negotiable rules

- Never commit `.env`, client secrets, access tokens, refresh tokens, cookies, private keys, or credential-manager exports.
- Never use a real mailbox, message body, document, Team, channel, site, drive, or Dataverse record as a public fixture.
- Keep identities outside MCP tool arguments.
- Use an allowlist for every remote operation and resource.
- Deny remote writes in the public mock runtime.
- Redact logs before persistence or publication.
- Treat synthetic fixtures as non-production data.

## Before publishing a change

```bash
uv run pytest --cov
uv run python scripts/scan_secrets.py
```

Also inspect `git diff --cached`, `git ls-files`, and the generated evidence files. The secrets scan is a gate, not a substitute for human review.
