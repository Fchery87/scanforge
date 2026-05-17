# ADR-006: Renovate for npm/pip dependency management

## Status
Accepted

## Decision
Use Renovate (`.github/renovate.json`) for npm and pip dependency updates with `minimumReleaseAge: "7 days"`. Use Dependabot (`.github/dependabot.yml`) for GitHub Actions only.

## Rationale
The xz-utils supply-chain attack (2024) demonstrated that malicious commits can appear in popular packages and be consumed within hours by automerge bots. A 7-day age gate on all non-security releases ensures that community detection has time to surface attacks before the package reaches the codebase.

Renovate was chosen over Dependabot for npm/pip because:
- Renovate supports `minimumReleaseAge` natively
- Renovate groups related updates (e.g., all eslint packages) into single PRs
- Dependabot does not support `minimumReleaseAge` on npm/pip as of 2025

Dependabot is retained for GitHub Actions because Renovate's GitHub Actions support is less battle-tested and the `minimumReleaseAge` rationale applies less forcefully to pinned SHA references.

Security vulnerability PRs bypass the age gate via `vulnerabilityAlerts.minimumReleaseAge: "0 days"`.

## Consequences
New packages appear in PRs ~7 days after their release date. For zero-day security patches, the vulnerability alert path bypasses this delay.
