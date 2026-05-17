# Cloudflare R2 Layout

## Bucket Prefixes

- `scan-artifacts/{project_id}/{scan_id}/raw/`
- `scan-artifacts/{project_id}/{scan_id}/logs/`
- `exports/{organization_id}/{export_id}/`
- `sboms/{project_id}/{scan_id}/`

## Artifact Retention

All objects expire after **90 days** via S3-compatible lifecycle rules defined in `lifecycle-rule.json`.
The default applies to `scan-artifacts/`, `sboms/`, and `exports/` prefixes.

### Applying the lifecycle rule

R2 uses the S3-compatible API. Apply `lifecycle-rule.json` using the AWS CLI pointed at your R2 endpoint:

```sh
aws s3api put-bucket-lifecycle-configuration \
  --endpoint-url https://<ACCOUNT_ID>.r2.cloudflarestorage.com \
  --bucket scanforge-artifacts \
  --lifecycle-configuration file://infra/r2/lifecycle-rule.json
```

Replace `<ACCOUNT_ID>` with your Cloudflare account ID. Credentials must be an R2 API token
with `Object Read & Write` and `Bucket Metadata Read` permissions.

Alternatively, apply through the Cloudflare dashboard: R2 → bucket → Settings → Object lifecycle rules.

### Verifying the rule

```sh
aws s3api get-bucket-lifecycle-configuration \
  --endpoint-url https://<ACCOUNT_ID>.r2.cloudflarestorage.com \
  --bucket scanforge-artifacts
```
