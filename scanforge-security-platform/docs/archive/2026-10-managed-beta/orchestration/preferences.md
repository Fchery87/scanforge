1. Authority is scanforge-security-platform/docs/plans/2026-10-16-managed-beta-implementation-plan.md; its Baseline and execution rules bind every unit.
2. No merges, no git push, no external messages, no production deploys, no infrastructure purchases, no destructive drills. Deliver local commits on the integration branch only.
3. The shared tree at scanforge/ is read-only for all workers. Never reset, clean, checkout, or edit it. All edits happen in the implementation worktree.
4. Preserve the operator's untracked planning docs and unrelated changes. Never stage them.
5. Regression-first per slice: add the named failing test, capture the pre-fix failure, make the smallest coherent fix, run focused checks, inspect the diff, commit only the enumerated paths.
6. One writer per track. apps/api edits serialize through the API track. One Alembic migration writer at a time; inspect current heads before adding revisions.
7. A missing required service is unverified, never a pass. Record verifier-blocked with the missing dependency. No mocks for PostgreSQL locking, real scanner execution, provider integration, or browser scenarios.
8. Fixtures are disposable and isolated: PostgreSQL 5433, Redis 6399, MinIO 9002, dedicated credentials, no production secrets in fixtures, commands, or receipts.
9. Never invent SHAs, counts, or evidence. Record actual commands and identities.
10. Cap concurrent workers at 3. Disjoint scopes only; contested files serialize.
11. Operator-only calls go to gates.md. Never block waiting on them; proceed with the stated default and record it.
12. Extend existing modules before creating parallel authorities. The lifecycle service owns scan creation, dispatch and retry meaning; services enforce access; adapters normalize scanner output; the API owns durable evidence.
13. No credential-looking literals in any committed file. Fixtures derive credentials from env or a gitignored runtime file; scripts print resolved values at start.
14. Capture SHAs with git rev-parse, never by retyping from prose.
15. Commit each invariant as soon as its tests pass. Never hold a large uncommitted tree; interruption then costs salvage, not work.
