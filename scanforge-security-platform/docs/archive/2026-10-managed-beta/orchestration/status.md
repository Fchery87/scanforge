# Orchestrate status

Generated: 2026-10-17T02:59:13.610Z

## Units

States: in-progress=1

| ID | Track | State | Branch | PR | SHA | Brief |
| --- | --- | --- | --- | --- | --- | --- |
| M00 | intake | in-progress | managed-beta/integration |  |  | /home/nochaserz/Documents/Coding Projects/scanforge/orchestrate/managed-beta/briefs/M00-baseline-fixtures.md |

## Verification ledger

Verdicts: none

(none)

## Frontier

Generation: 0
Lowest unmerged: none

(none)

## Gates

| ID | Status | Question | Options | Default | Answer |
| --- | --- | --- | --- | --- | --- |
| docker-runtime | open | Docker is absent and sudo needs a password. M04 containment evidence and M05 image fixtures need a container runtime. | 1 operator installs Docker; 2 accept native pinned scanner binaries and mark image-fixture checks verifier-blocked; 3 point at a remote docker host | Proceed with native pinned binaries; record container-fidelity checks verifier-blocked |  |
| github-app | open | M11 release check needs real non-production GitHub App credentials and delivery. | 1 operator supplies App credentials; 2 build against fixtures and mark live App delivery unverified | Fixtures only; live App delivery recorded unverified |  |
| landing | open | The plan authorizes no merges. Who lands the integration branch, and when should it push to origin? | 1 operator lands locally; 2 operator authorizes push to origin managed-beta/integration; 3 open PRs without merging | Integration branch stays local with recorded SHAs; operator decides push and landing |  |

<!-- orch-summary {"unitStates":{"in-progress":1},"ledgerVerdicts":{},"frontierGeneration":0,"openGateIds":["docker-runtime","github-app","landing"]} -->
