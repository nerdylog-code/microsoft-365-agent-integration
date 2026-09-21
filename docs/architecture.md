# Architecture and provenance

## Observed private architecture

The implementation inspected for this portfolio used multiple custom Python MCP servers. Each server exposed a narrow tool surface and used Microsoft Graph directly. Hermes acted as the MCP host/client and injected the discovered tools into the agent.

The observed authentication method was OAuth2 `client_credentials` (app-only). The mailbox or resource identity was configured outside the tool schema. Microsoft Entra application permissions, Exchange Application RBAC, Teams RSC, and fixed SharePoint/Dataverse scopes provided separate authorization boundaries.

## Public clean-room architecture

This repository keeps the behavior contracts but removes private constants and live endpoints from the executable mock path:

1. `config.py` validates environment shape and placeholder safety.
2. `graph_client.py` handles Graph transport, token caching, safe errors, retries, and host allowlisting.
3. `policy.py` defines the public tool allowlist and JSON schemas.
4. `mcp_runtime.py` implements initialize, `tools/list`, and controlled `tools/call` against synthetic fixtures.
5. `stdio_server.py` provides a line-oriented JSON-RPC MCP contract for local demonstrations.
6. `audit.py` emits endpoint classes and counts, never payloads.
7. `scripts/scan_secrets.py` fails closed on likely credentials or private identifiers.

## What is not claimed

- The mock runtime is not evidence that a new tenant grants the required permissions.
- The repository is not the Microsoft Enterprise MCP product.
- A successful local test is not a remote Graph smoke test.
- The private installation's corporate writes are not repeated here.
