# Evidence generation

Evidence is generated locally after the clean-room tests pass:

```bash
uv run pytest --cov=m365_agent_integration --cov-report=json:evidence/coverage.json --junitxml=evidence/pytest.xml
uv run python scripts/generate_evidence.py .
```

Only sanitized protocol metadata, counts, statuses, endpoint classes, and synthetic tool names belong in this directory. Never copy raw HTTP responses, message bodies, document text, IDs, or credential material into evidence.
