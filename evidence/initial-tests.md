# Initial test evidence boundary

The external Hermes MCP backup was inspected for provenance. It contains custom MCP source repositories and sanitized Power Platform audit metadata, but no Hermes conversation transcripts, session database, or conversation export.

Private source evidence documented separate app-only Graph paths for mail, calendar, Teams channel reads, SharePoint, and Power Platform. The public repository does not copy those payloads or private identifiers.

The public evidence files in this directory are generated from the clean-room mock runtime and injected HTTP transports. They prove protocol, policy, redaction, and error-handling contracts; they do not claim a live tenant smoke test.
