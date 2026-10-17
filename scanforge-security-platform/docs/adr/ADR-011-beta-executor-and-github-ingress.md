# ADR-011: Host coordinator and GitHub App ingress for beta

## Status

Accepted on 2026-10-16, Round 2 Q9 and Q11.

## Decision

Implement ADR-009 with a dedicated Linux VM per organization. The coordinator runs as a supervised host service with Git, a local container runtime, a controlled workspace root, and one concurrent scan. Disposable offline scanner containers receive read-only source and separate writable output directories with compatible ownership. They receive no credentials or container-runtime socket. The coordinator is a privileged component inside its organization's host boundary.

Use one GitHub App webhook entry point. Verify the signature before resolving the installation ID and immutable GitHub repository ID to authorized internal connections. Installation removal and repository-access removal revoke corresponding access. Connecting users must prove access to the selected GitHub installation before binding it.

## Rationale

A host coordinator avoids the daemon connectivity, host-visible bind mounts, and permission ambiguity in the current coordinator-container configuration. A single App ingress provides authoritative event routing without granting tenant authority through caller-selected URL identifiers or mutable repository names.

## Consequences

Provisioning, coordinator upgrades, workspace cleanup, and container execution require tests on this exact topology. VM provider, capacity envelope, runtime privilege configuration, and recovery timings remain open. Repository ownership multiplicity is a separate unresolved decision.
