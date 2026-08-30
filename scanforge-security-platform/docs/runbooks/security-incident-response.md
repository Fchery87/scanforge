# Security incident response

1. Stop the affected organization's worker and disable its worker identities immediately.
2. Rotate GitHub installation credentials and worker credentials if exposure is suspected.
3. Preserve redacted logs, audit events, queue metadata, and deployment identifiers.
4. Do not copy source code or secret values into the incident record.
5. Inspect PostgreSQL, object storage, notification deliveries, and external request telemetry for prohibited secret evidence.
6. Remove exposed artifacts according to the retention and legal-hold policy.
7. Restore service only after containment, credential rotation, and a canary-secret verification pass.
8. Document scope, timeline, customer notification, remediation, and operator sign-off.
