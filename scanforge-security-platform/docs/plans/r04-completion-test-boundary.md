# R04 completion test boundary

This slice adds no runtime schema or service code. The PostgreSQL harness must run an isolated PostgreSQL 16 cluster created under `/tmp`, with a per-run database and no project credentials. Each test uses two async SQLAlchemy sessions and the supported completion/cancellation service boundary.

The immutable completion request is identified by `(scan_id, winning_attempt_id, execution_revision, evidence_digest)`. The API-owned receipt stores the canonical sanitized evidence digest, accepted scanner outcomes, inserted/updated counts, scanner completeness, terminal status, and winning attempt/revision. The business response is read from that receipt on replay.

Required red tests: (1) same attempt replay with a changed valid payload must return `completion_payload_conflict` and leave all rows unchanged; (2) an injected failure after scanner/finding writes must roll back every authoritative row; (3) completion and cancellation in concurrent PostgreSQL transactions must have one terminal winner under the Scan row lock, with the loser returning the policy conflict. Existing code has no attempt/receipt identity and cancellation does not share the completion transaction, so these tests should fail as product assertions once fixtures are wired.

Docker is unavailable in this environment. Native PostgreSQL 16 binaries are installed and are suitable for the disposable test server; CI should additionally run the required container/Redis/REST acceptance suite.
