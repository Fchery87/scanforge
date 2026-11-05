# Domain Docs

This repo uses a single-context domain docs layout.

Product direction: `docs/PRODUCT_CHARTER.md`

Domain glossary: `CONTEXT.md`

Architecture decisions: `docs/adr/`

Current architecture and known gaps: `docs/SYSTEM_OVERVIEW.md`

Agent skills should read the charter and the domain glossary before proposing domain names, seams, or architectural changes. They should read ADRs before proposing changes that may contradict accepted decisions. `docs/archive/` is non-authoritative history and must not be treated as guidance.

If a new durable domain term is introduced, update `CONTEXT.md`. If a hard-to-reverse architectural decision is made, add an ADR under `docs/adr/`.
