# Disable a beta organization

1. Confirm the incident or offboarding approval and record the organization UUID.
2. Disable every worker identity for the organization using the management script.
3. Stop the organization's dedicated worker host; leave other tenants running.
4. Confirm new internal requests return 401/403 and queued jobs remain recoverable.
5. Preserve audit records and follow retention requirements for artifacts.
6. Re-enable only after the operator approves a new credential and a clean test scan.
