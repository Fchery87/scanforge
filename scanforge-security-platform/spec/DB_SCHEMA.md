# Database Schema Summary

## Core domains
- users
- organizations
- organization_members
- projects
- repositories
- repository_integrations
- scans
- scanner_runs
- findings
- finding_instances
- finding_references
- finding_events
- suppression_rules
- finding_suppressions
- scan_artifacts
- exports
- audit_logs

## Important modeling rule
- `finding` = logical issue over time
- `finding_instance` = occurrence of that issue in a particular scan

## High-priority indexes
- findings by `(project_id, status, severity)`
- scans by `(repository_id, created_at desc)`
- scanner_runs by `(scan_id)`
- audit_logs by `(organization_id, created_at desc)`
