# ADR-014: Finding identity, scanner provenance, and legacy evidence

## Status

Accepted on 2026-10-16, Round 5 Q24–Q27. Refines ADR-002 and ADR-004.

## Identity and conflicting observations

Version the fingerprint policy. Dependency identity includes repository, ecosystem/package, installed version, and verified advisory identity. Source findings use repository, detector, normalized path, and stable location identity where supported; infrastructure findings add resource identity. Secret identity uses detector/location without credential-derived data, as accepted in Round 2 Q8. License findings use repository, package identity, and license obligation.

Round 9 Q50, accepted on 2026-10-16: preserve exact dependency identity while linking related findings through verified package/advisory lineage. Retain manifest/path occurrences. Show exposure persisting across vulnerable upgrades, even when the old version is no longer observed; another affected version prevents claiming advisory remediation. Human risk/false-positive decisions never transfer automatically to the new finding.

Cross-scanner merging requires explicit tested equivalence, preserves each scanner's evidence/provenance, and never relies on title similarity. Unknown equivalence remains separate. A line-based fallback can create a new finding after movement; expose that limitation and never silently transfer human dispositions.

Retain original severity, confidence, and remediation values. Prioritize using the highest supported normalized severity with its source identified, while exposing conflicts. Confidence alone cannot promote severity to Critical. Remediation versions retain provider provenance; disagreement does not produce a fabricated safe upgrade. Refresh current summaries from new evidence while retaining historical observations.

## Scanner provenance

Trusted image builds pin tools, parsers, rules, and databases and emit a verifiable manifest. Refresh outside customer execution. Database-backed scanners require database age at most seven days for complete coverage or closure; unverifiable or older databases are ineligible. Database-free scanners explicitly record not_applicable. Build cadence must leave freshness margin.

Deploy security updates even when comparison compatibility is unknown, establish a new comparison baseline, and require directional fixtures before granting compatibility. An upgrade removing a detection never proves remediation by itself.

## Legacy migration

Preserve original rows and decisions but label unsupported conclusions legacy/unverified. They grant no automatic-closure credit. Never fabricate provenance, approvals, reasons, risk expiries, or duplicate targets. Unsupported risk/suppression decisions count as unresolved exposure pending review. Reconcile verified human decisions separately from unsupported machine conclusions. Repeatable migrations report preserved, reclassified, and unresolved record counts.

## Rationale

Category-specific identity prevents unsafe merges, provenance permits meaningful comparisons, and explicit legacy uncertainty prevents old records from bypassing new evidence rules. Fingerprint changes, scanner upgrades, and migration require fixtures and reconciled historical counts before rollout.
