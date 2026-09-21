# Permissions and scopes

The public repository does not contain tenant IDs, app registrations, site IDs, drive IDs, Team IDs, channel IDs, or consent records. The following matrix describes the observed categories and the boundary a consumer must verify in its own tenant.

| Service | Read category | Required boundary | Public status |
|---|---|---|---|
| Outlook mail | Graph application mail read | Mailbox restriction such as Exchange Application RBAC | Synthetic only |
| Calendar | Graph application calendar read | Mailbox restriction and least-privilege calendar role | Synthetic only |
| Teams channel | Graph application read for the approved resource | Teams Resource-Specific Consent and local alias registry | Synthetic only |
| SharePoint | Graph site/drive read | Fixed site/drive allowlist and Graph host validation | Synthetic only |
| Power Platform | Dataverse/Power Platform development reads | Pinned DEV environment and explicit production deny | Documented only |

## Rules

1. Never accept a mailbox, UPN, user ID, Team ID, channel ID, site ID, drive ID, tenant ID, token, URL, or HTTP method as an arbitrary tool argument.
2. Do not add tenant-wide permissions merely to bypass an RSC or RBAC failure.
3. Keep read-only and action servers separate.
4. Return a closed, sanitized error for `401`, `403`, `404`, `429`, timeout, and malformed responses.
5. Verify the effective permission set in Entra/Exchange/Teams before making a public claim.
6. Treat delegated OAuth as a separate architecture. It is not silently substituted for the observed app-only flow.

See the Microsoft documentation links in the README before configuring a live consumer.
