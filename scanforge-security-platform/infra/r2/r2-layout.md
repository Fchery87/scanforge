# Cloudflare R2 Layout

## Bucket Prefixes

- `scan-artifacts/{organization_id}/{scan_id}/{scanner_name}/{filename}`: sanitized scanner artifacts. Keys are issued by the API ([internal routes](../../apps/api/app/api/v1/routes/internal.py)) and checked by the worker ([r2 client](../../apps/worker/app/clients/r2.py)).
- `exports/` and `sboms/` are reserved by the lifecycle rule for the disabled export capability and possible future SBOM output; no current code writes to them.

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
