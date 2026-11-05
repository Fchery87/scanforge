# Gates

## docker-runtime

- Status: open
- Question: Docker is absent and sudo needs a password. M04 containment evidence and M05 image fixtures need a container runtime.
- Options: 1 operator installs Docker; 2 accept native pinned scanner binaries and mark image-fixture checks verifier-blocked; 3 point at a remote docker host
- Default: Proceed with native pinned binaries; record container-fidelity checks verifier-blocked

## github-app

- Status: open
- Question: M11 release check needs real non-production GitHub App credentials and delivery.
- Options: 1 operator supplies App credentials; 2 build against fixtures and mark live App delivery unverified
- Default: Fixtures only; live App delivery recorded unverified

## landing

- Status: open
- Question: The plan authorizes no merges. Who lands the integration branch, and when should it push to origin?
- Options: 1 operator lands locally; 2 operator authorizes push to origin managed-beta/integration; 3 open PRs without merging
- Default: Integration branch stays local with recorded SHAs; operator decides push and landing

## shield-fixture-commit

- Status: open
- Question: Droid-Shield blocks every Droid-side commit of the M00 fixture tooling because its redacted view of scripts/dev_fixtures.sh line 46 (a runtime password generator, no literal) looks like a hardcoded secret. The file is literal-free (grep clean). The shield names the operator as the resolver for false positives.
- Options: 1 run the staged commit outside Droid; 2 edit the line so the shield stops matching (would need a rename away from PASSWORD-style expansion); 3 disable the shield rule (not recommended)
- Default: Program proceeds on parallel branches; commit (a) lands whenever the operator runs it; integration merge follows
