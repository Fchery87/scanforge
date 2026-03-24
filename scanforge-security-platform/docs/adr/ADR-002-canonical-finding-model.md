# ADR-002: Canonical finding model

## Status
Accepted

## Decision
All scanner output must normalize into one internal finding model.

## Rationale
This allows:
- scanner independence
- historical tracking
- deduplication across scans
- richer dashboards
- easier future scanner expansion

## Implication
Raw tool outputs are never the primary UI contract.
