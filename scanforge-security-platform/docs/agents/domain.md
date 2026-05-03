# Domain Docs

This repo uses a single-context domain docs layout.

Domain glossary: `CONTEXT.md`

Architecture decisions: `docs/adr/`

Agent skills should read the domain glossary before proposing domain names, seams, or architectural changes. They should read ADRs before proposing changes that may contradict accepted decisions.

If a new durable domain term is introduced, update `CONTEXT.md`. If a hard-to-reverse architectural decision is made, add an ADR under `docs/adr/`.
