# Rotate a worker credential

1. Identify the worker identity and organization UUID.
2. Use `apps/api/scripts/manage_worker_identity.py rotate --worker-id <id>` with API database access.
3. Deliver the one-time plaintext replacement through the worker secret manager.
4. Restart only that organization's worker host.
5. Verify the old credential receives 401 and the new credential can read its execution context.
6. Record the rotation in the operator audit log.

Never print credentials in tickets, shell history, logs, or deployment manifests.
