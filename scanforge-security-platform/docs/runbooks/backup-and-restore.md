# Backup and restore

1. Use Neon/PostgreSQL point-in-time backup facilities according to the production retention policy.
2. Restore into an isolated database and apply all committed Alembic migrations.
3. Verify scans, findings, scanner runs, occurrences, audit events, and worker identities.
4. Never restore production secrets into a developer environment.
5. Validate R2 artifact references and lifecycle expiration separately; database restore does not restore object bytes.
6. Record the drill result, duration, and operator approval.
