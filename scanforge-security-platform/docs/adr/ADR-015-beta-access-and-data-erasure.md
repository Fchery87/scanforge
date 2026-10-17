# ADR-015: Beta access and data erasure

## Status

Accepted on 2026-10-16, Round 6 Q30–Q33.

## Access

Beta visibility is organization-wide. All five roles read findings, scans, coverage and sanitized evidence. Owners, admins, security reviewers and developers trigger/cancel authorized scans; viewers cannot. Owners/admins/security reviewers mutate finding assignments, dispositions and risk acceptance. Owners/admins manage repositories, GitHub integration and ordinary memberships. Only owners appoint/remove admins, transfer ownership, or request organization erasure. Start with one owner and an atomic ownership transfer. Project-restricted visibility is deferred. Operators manage worker credentials outside ordinary organization administration.

Enforce the matrix at service boundaries, direct calls and bulk operations. Each protected operation checks active-user status and current membership. Internal operations check current worker status and attempt authority. UI capabilities are hints only. Revocation blocks subsequent operations and sends active work through stop/cleanup. Issued artifact URLs have a short explicit lifetime; revocation prevents new issuance but cannot recall downloaded data. Membership addition requires verified identity/email and pending invitation acceptance.

## Repository and organization lifecycle

Disconnect stops new scans and revokes execution access while retaining authorized history. Archive removes active presentation without erasing findings or unresolved exposure. Erasure is explicit owner-authorized work that drains/quarantines queued work, revokes credentials, cleans execution hosts and removes associated data. Disconnect/archive never prove remediation. Audited reviewer reconciliation retires branch obligations without fabricating absence. Rebinding does not transfer historical evidence automatically.

Organization erasure is a durable workflow covering active database/object/queue/log/host stores and backups. Block new work first. A minimal tombstone prevents delayed deliveries from recreating the tenant; it contains no source, findings, credentials or unnecessary personal data. Restores reapply tombstones before serving traffic.

Backups have a maximum 30-day retention policy, conditional on verifying enforcement by the selected infrastructure. Pending-expiration copies are inaccessible to ordinary application use. Expose active-store erasure and backup-expiration completion separately; do not claim complete deletion while copies remain.

## Rationale

Explicit privilege boundaries prevent administrative escalation and revoked-token reuse. Separate lifecycle operations preserve history without confusing retirement with remediation. Erasure accounts for retained copies and delayed events rather than treating database cascades as complete deletion.
