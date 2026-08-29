# ADR-009: Dedicated workers for the secure private beta

## Status

Accepted

## Context

ScanForge processes private source code with native security scanners. The current deployment declares one worker for every organization. That worker consumes one global queue and holds credentials that can reach the shared API and object-storage bucket.

The production-readiness audit found that this design gives a compromised scanner process too much authority. It also makes one customer's resource exhaustion or worker failure affect every customer.

The private beta contains three design-partner organizations and may expand to five. This limited cohort permits a simpler isolation model than a public multi-tenant service.

## Decision

Give each beta organization one dedicated worker host.

The worker host has an immutable organization identity, an organization-specific queue namespace, an organization-scoped service credential, and one concurrent scan. The shared API verifies the worker identity on every internal request.

The worker host coordinates a disposable scanner container for each scan. The scanner container receives the repository source through a read-only mount and writes to a separate output directory. It receives no GitHub token, worker credential, database credential, object-storage credential, or Docker socket. It has no outbound network during scanner execution.

The worker communicates with PostgreSQL and object storage only through the shared API. The API issues exact-key presigned artifact uploads after it verifies the worker, scan, organization, and object key.

Use Redis Streams and consumer groups for organization-specific scan queues. The worker continuously reclaims stale pending messages. A weekly task is not part of crash recovery.

Treat the dedicated worker as an organization boundary. Treat the disposable scanner container as a scan boundary.

## Alternatives considered

### One shared worker with per-scan containers

This model uses compute more efficiently. It leaves more routing, credential, and scheduler code in the shared failure boundary. ScanForge will reconsider it after the beta proves the queue, service identity, and scan-containment contracts.

### Customer-hosted runners

This model keeps source code in the customer's environment. It adds installation, upgrade, support, network, and compatibility work that would distract from validating the evidence workflow.

### One dedicated worker without scanner containers

This model separates customers but leaves worker credentials available to compromised scanner processes. It does not meet the beta's scan-containment requirement.

### Cloud-hosted sandbox service

A managed sandbox can provide disposable execution and resource controls. Adopting one now would add another control plane and require a large worker rewrite. The beta will first use disposable containers on dedicated worker hosts behind a `ScanRuntime` interface.

## Consequences

- A worker compromise is limited to one organization unless the shared API has an authorization defect.
- A scanner compromise does not receive the worker or GitHub credential.
- Operators can disable, inspect, replace, or rotate one organization's worker independently.
- Each beta organization consumes its own worker capacity, including idle capacity.
- Provisioning and upgrades require per-organization automation and runbooks.
- This model is suitable for three to five organizations. It is not the final public multi-tenant architecture.
- Public launch requires a new capacity and isolation review.

## Required invariants

- The API derives worker organization access from the verified worker identity.
- A worker cannot select another queue namespace at runtime.
- A worker cannot obtain clone or artifact authority for another organization.
- A scanner container receives no service credential.
- A scan message is acknowledged only after atomic completion succeeds.
- Disabling a worker identity takes effect on the next internal API request.

## Related decisions

- ADR-002 defines the canonical finding model.
- ADR-003 makes scan lifecycle the owner of scan creation and queueing.
- ADR-004 defines evidence requirements for finding lifecycle changes.
- ADR-005 keeps execution, normalization, AI investigation, and persistence as separate stages.

## External references

- [Upstash `XAUTOCLAIM` documentation](https://upstash.com/docs/redis/sdks/ts/commands/stream/xautoclaim) describes how a consumer takes ownership of pending Redis Stream messages.
- [Render's Blueprint specification](https://render.com/docs/blueprint-spec) defines background workers, service fields, and environment isolation.
