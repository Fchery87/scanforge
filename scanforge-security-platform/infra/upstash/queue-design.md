# Upstash Queue Design

Suggested job categories:
- scan.repo.full
- scan.repo.diff
- normalize.results
- generate.export
- send.notification
- scheduled.scan.tick

Redis should not be the source of truth for findings or scan history.
