# Provisioning a private-beta worker

1. Create or approve the organization in the API and record its UUID.
2. Issue a worker identity with only the required organization capabilities.
3. Store the plaintext credential in the organization's worker secret store; it is never stored in PostgreSQL or source control.
4. Render `infra/worker/.env.example` for that organization with `scripts/render_worker_config.py`.
5. Set a fully digest-pinned `SCANNER_IMAGE` and verify `AI_ENABLED=false`.
6. Start the host with `docker compose -f infra/worker/docker-compose.beta.yml up -d`.
7. Confirm the worker readiness log reports the expected organization and consumer, and that queue age alerts are active.
8. Run a test scan and verify the completion, artifact prefix, and audit event.

The worker must not receive `DATABASE_URL`, R2 account credentials, the API pepper, or the scheduler key.
