# Scan Pipeline Wiring — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Wire the scan pipeline end-to-end so that clicking "Run Scan" in the UI creates a scan, enqueues a job to Redis, the worker picks it up, clones the repo, runs scanner binaries, normalizes findings, and persists them back via the internal API.

**Architecture:** The API route creates a Scan record then enqueues a job to Upstash Redis. A separate worker process polls the queue, clones the repository using a GitHub installation token, shells out to scanner binaries (trivy, gitleaks, osv-scanner), normalizes results, uploads artifacts to R2, and calls internal API endpoints (authenticated via `X-Service-Key` header) to persist findings and update scan status.

**Tech Stack:** FastAPI + asyncpg (API), Upstash Redis REST API (queue), httpx (GitHub API + internal calls), subprocess (scanner binaries), boto3/S3 (Cloudflare R2), Python 3.12+

---

## Task 1: Add Queue Enqueue to the Scan Creation Route

The scan creation endpoint creates a DB record with status=QUEUED but never pushes a job to the Redis queue. The worker never learns about new scans.

**Files:**
- Modify: `apps/api/app/api/v1/routes/scans.py:22-47`
- Modify: `apps/api/app/core/config.py` (already has UPSTASH settings — no change needed)

**Step 1: Add queue enqueue after scan creation**

In `apps/api/app/api/v1/routes/scans.py`, add an import for `QueueClient` and enqueue after the scan is created:

```python
# At top of file, add:
import logging
from app.core.config import settings

logger = logging.getLogger(__name__)
```

Then replace the `create_scan` function body (lines 22-47) with:

```python
@router.post("/", response_model=ScanResponse, status_code=status.HTTP_201_CREATED)
async def create_scan(
    project_id: UUID,
    data: ScanCreate,
    current_user: UserContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    project_service = ProjectService(db)
    has_access = await project_service.user_has_access(project_id, current_user.user_id)
    if not has_access:
        raise HTTPException(status_code=403, detail="No access to this project")

    repo_service = RepositoryService(db)
    repo = await repo_service.get_by_id(data.repository_id, current_user.user_id)
    if not repo or repo.project_id != project_id:
        raise HTTPException(status_code=404, detail="Repository not found in this project")

    scan_service = ScanService(db)
    try:
        scan, _, _ = await scan_service.create(
            data.repository_id, data, current_user.user_id
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    # ── Enqueue to Redis so the worker picks up this scan ──
    scan_type_map = {
        "full": "scan.repo.full",
        "diff": "scan.repo.diff",
        "dependencies": "scan.dependencies",
        "secrets": "scan.secrets",
    }
    job_type = scan_type_map.get(data.scan_type, "scan.repo.full")

    try:
        from app.clients.queue import QueueClient

        queue = QueueClient(
            redis_url=settings.UPSTASH_REDIS_REST_URL,
            redis_token=settings.UPSTASH_REDIS_REST_TOKEN,
        )
        job_id = await queue.enqueue(job_type, {
            "scan_id": str(scan.id),
            "repository_id": str(scan.repository_id),
            "project_id": str(scan.project_id),
            "branch": scan.branch_name,
            "commit_sha": scan.commit_sha,
            "user_id": str(current_user.user_id),
        })
        logger.info("Enqueued scan %s as job %s (%s)", scan.id, job_id, job_type)
    except Exception as e:
        logger.error("Failed to enqueue scan %s: %s", scan.id, e)
        # Update scan to failed so UI shows the error
        scan.status = "failed"
        scan.error_message = f"Failed to enqueue: {e}"
        await db.commit()
        await db.refresh(scan)

    return scan
```

**Step 2: Copy `queue.py` client to API app**

The `QueueClient` lives in `apps/worker/app/clients/queue.py`. The API needs access to it too. Copy the file:

```bash
mkdir -p apps/api/app/clients
cp apps/worker/app/clients/queue.py apps/api/app/clients/queue.py
touch apps/api/app/clients/__init__.py
```

**Step 3: Verify the change works**

Start the API server and create a scan via the UI or curl:
```bash
curl -X POST http://localhost:8000/api/v1/organizations/{org_id}/projects/{project_id}/scans/ \
  -H "Content-Type: application/json" \
  -d '{"repository_id": "<repo-uuid>", "scan_type": "full"}'
```

Expected: 201 response with `"status": "queued"`. Server logs show `Enqueued scan ... as job ...`. If Redis isn't configured, scan status = `failed` with error message.

**Step 4: Commit**

```bash
git add apps/api/app/api/v1/routes/scans.py apps/api/app/clients/queue.py apps/api/app/clients/__init__.py
git commit -m "feat: enqueue scan jobs to Redis after creation"
```

---

## Task 2: Implement `_prepare_repository` — Clone via GitHub Installation Token

The orchestrator's `_prepare_repository` creates an empty temp directory. It needs to actually clone the repo using a GitHub App installation token.

**Files:**
- Modify: `apps/worker/app/services/scan_orchestrator.py:146-148`
- Modify: `apps/worker/app/services/scan_orchestrator.py` (top-level imports)

**Step 1: Add a GitHub clone helper to the orchestrator**

Replace the stub `_prepare_repository` method (line 146-148) and add supporting methods:

```python
async def _prepare_repository(self, context: ScanContext) -> Path:
    """Clone the repository using a GitHub App installation token."""
    repo_dir = Path(mkdtemp(prefix="scan_repo_"))

    # Fetch the installation token from the API
    clone_url = await self._get_clone_url(context)

    try:
        result = await asyncio.to_thread(
            subprocess.run,
            [
                "git", "clone",
                "--depth", "1",
                "--single-branch",
                *(["--branch", context.branch] if context.branch else []),
                clone_url,
                str(repo_dir),
            ],
            capture_output=True,
            text=True,
            timeout=300,
        )
        if result.returncode != 0:
            raise RuntimeError(f"git clone failed: {result.stderr.strip()}")
    except subprocess.TimeoutExpired:
        raise RuntimeError("git clone timed out after 5 minutes")

    return repo_dir

async def _get_clone_url(self, context: ScanContext) -> str:
    """Build an authenticated clone URL via the internal API."""
    import os
    internal_key = os.environ.get("INTERNAL_API_KEY", "")

    async with httpx.AsyncClient() as client:
        # Ask the API for repo details + installation token
        resp = await client.get(
            f"{self.api_base_url}/api/v1/internal/repositories/{context.repository_id}/clone-url",
            headers={"X-Service-Key": internal_key},
            timeout=30.0,
        )
        resp.raise_for_status()
        data = resp.json()
        return data["clone_url"]
```

Also add `import subprocess` to the top-level imports (it's not currently imported in the orchestrator).

**Step 2: Add the internal clone-url endpoint to the API**

Add to `apps/api/app/api/v1/routes/internal.py`:

```python
@router.get("/repositories/{repo_id}/clone-url")
async def get_repository_clone_url(
    repo_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Return an authenticated clone URL for the worker to use."""
    repo = await db.get(Repository, repo_id)
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")

    # Get the org's GitHub integration
    project = await db.get(Project, repo.project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    result = await db.execute(
        select(OrganizationIntegration).where(
            OrganizationIntegration.organization_id == project.organization_id
        )
    )
    integration = result.scalar_one_or_none()
    if not integration:
        raise HTTPException(status_code=404, detail="No GitHub integration for this org")

    # Get an installation access token
    from app.services.github import GitHubService
    gh = GitHubService(db)
    token = await gh._get_installation_token(integration.installation_id)

    # Build authenticated clone URL: https://x-access-token:<token>@github.com/owner/repo.git
    clone_url = repo.clone_url or f"https://github.com/{repo.full_name}.git"
    authed_url = clone_url.replace("https://", f"https://x-access-token:{token}@")

    return {"clone_url": authed_url}
```

**Step 3: Verify**

Start the API. Test the internal endpoint:
```bash
curl -H "X-Service-Key: scanforge-internal-dev-key" \
  http://localhost:8000/api/v1/internal/repositories/{repo-uuid}/clone-url
```

Expected: `{"clone_url": "https://x-access-token:ghs_...@github.com/owner/repo.git"}`

**Step 4: Commit**

```bash
git add apps/worker/app/services/scan_orchestrator.py apps/api/app/api/v1/routes/internal.py
git commit -m "feat: implement repo cloning via GitHub installation token"
```

---

## Task 3: Add `INTERNAL_API_KEY` Header to Orchestrator HTTP Calls

The orchestrator's `_persist_findings` and `_update_scan_status` call the internal API without the required `X-Service-Key` header. The internal router requires it via `require_service_auth`.

**Files:**
- Modify: `apps/worker/app/services/scan_orchestrator.py:278-291` (`_persist_findings`)
- Modify: `apps/worker/app/services/scan_orchestrator.py:341-360` (`_update_scan_status`)

**Step 1: Add an `internal_api_key` property to the orchestrator**

In `ScanOrchestrator.__init__`, read the key from env:

```python
def __init__(
    self,
    queue: QueueClient,
    r2: R2Client,
    api_base_url: str = "http://localhost:8000",
):
    self.queue = queue
    self.r2 = r2
    self.api_base_url = api_base_url
    self._notifier: NotificationDispatcher | None = None
    self._internal_api_key = os.environ.get("INTERNAL_API_KEY", "")
```

Add `import os` to the top-level imports.

**Step 2: Add the header to `_persist_findings`**

Replace lines 278-291:

```python
async def _persist_findings(self, context: ScanContext):
    if not context.findings:
        return

    async with httpx.AsyncClient() as client:
        try:
            await client.post(
                f"{self.api_base_url}/api/v1/internal/scans/{context.scan_id}/findings",
                json={"findings": context.findings},
                headers={"X-Service-Key": self._internal_api_key},
                timeout=60.0,
            )
        except Exception as e:
            print(f"[orchestrator] Failed to persist findings: {e}")
```

**Step 3: Add the header to `_update_scan_status`**

Replace lines 341-360:

```python
async def _update_scan_status(
    self,
    context: ScanContext,
    status: str,
    error: str | None = None,
    summary: dict | None = None,
):
    async with httpx.AsyncClient() as client:
        try:
            await client.patch(
                f"{self.api_base_url}/api/v1/internal/scans/{context.scan_id}/status",
                json={
                    "status": status,
                    "error_message": error,
                    "summary_json": summary,
                },
                headers={"X-Service-Key": self._internal_api_key},
                timeout=30.0,
            )
        except Exception as e:
            print(f"[orchestrator] Failed to update scan status: {e}")
```

**Step 4: Verify**

The `INTERNAL_API_KEY=scanforge-internal-dev-key` is already set in `.env`. The worker reads `.env` via `_load_env()` in `main.py`. No additional config needed.

**Step 5: Commit**

```bash
git add apps/worker/app/services/scan_orchestrator.py
git commit -m "fix: add INTERNAL_API_KEY header to orchestrator HTTP calls"
```

---

## Task 4: Set Up Upstash Redis with Real Credentials

The `.env` has placeholder values for Redis. You need a real Upstash Redis instance.

**Files:**
- Modify: `.env` (lines 28-29)

**Step 1: Create an Upstash Redis database**

1. Go to [https://console.upstash.com](https://console.upstash.com)
2. Sign up / log in
3. Click **Create Database**
4. Name: `scanforge-dev`
5. Region: **US-East-1** (closest to Neon Postgres)
6. Type: **Regional** (free tier is fine for dev)
7. Click **Create**

**Step 2: Copy the REST credentials**

On the database details page, find:
- **REST URL** — looks like `https://usw1-something.upstash.io`
- **REST Token** — a long base64 string

**Step 3: Update `.env`**

Replace lines 28-29:
```
UPSTASH_REDIS_REST_URL=https://<your-instance>.upstash.io
UPSTASH_REDIS_REST_TOKEN=<your-token>
```

**Step 4: Verify connection**

Test from the worker:
```bash
cd apps/worker
python -c "
import asyncio, os
from dotenv import load_dotenv
load_dotenv('../../.env')
from app.clients.queue import QueueClient
q = QueueClient(os.environ['UPSTASH_REDIS_REST_URL'], os.environ['UPSTASH_REDIS_REST_TOKEN'])
print('Queue length:', asyncio.run(q.get_queue_length()))
"
```

Expected: `Queue length: 0` (or whatever is in the queue). If credentials are wrong, you'll see an HTTP 401 error.

**Step 5: Restart the API server** (required due to `@lru_cache` on settings)

```bash
# Stop and restart the API server so it picks up the new Redis credentials
```

**Do not commit** — `.env` is gitignored. No commit needed.

---

## Task 5: Install Scanner Binaries

The scanner adapters shell out to `trivy`, `gitleaks`, and `osv-scanner`. These must be installed on your system.

**Step 1: Install Trivy**

```bash
# Ubuntu/Debian:
sudo apt-get install wget apt-transport-https gnupg lsb-release -y
wget -qO - https://aquasecurity.github.io/trivy-repo/deb/public.key | gpg --dearmor | sudo tee /usr/share/keyrings/trivy.gpg > /dev/null
echo "deb [signed-by=/usr/share/keyrings/trivy.gpg] https://aquasecurity.github.io/trivy-repo/deb $(lsb_release -sc) main" | sudo tee /etc/apt/sources.list.d/trivy.list
sudo apt-get update && sudo apt-get install trivy -y
```

Verify: `trivy --version` → should print version info

**Step 2: Install Gitleaks**

```bash
# Via Go install (if Go is installed):
go install github.com/gitleaks/gitleaks/v8@latest

# Or download binary:
GITLEAKS_VERSION=8.18.4
wget https://github.com/gitleaks/gitleaks/releases/download/v${GITLEAKS_VERSION}/gitleaks_${GITLEAKS_VERSION}_linux_x64.tar.gz
tar -xzf gitleaks_${GITLEAKS_VERSION}_linux_x64.tar.gz
sudo mv gitleaks /usr/local/bin/
```

Verify: `gitleaks version` → should print version info

**Step 3: Install OSV-Scanner**

```bash
# Via Go install:
go install github.com/google/osv-scanner/cmd/osv-scanner@latest

# Or download binary:
OSV_VERSION=1.9.1
wget https://github.com/google/osv-scanner/releases/download/v${OSV_VERSION}/osv-scanner_linux_amd64
chmod +x osv-scanner_linux_amd64
sudo mv osv-scanner_linux_amd64 /usr/local/bin/osv-scanner
```

Verify: `osv-scanner --version` → should print version info

**Step 4: Verify all scanners**

```bash
trivy --version && gitleaks version && osv-scanner --version
```

Expected: Three version strings printed without errors.

**Do not commit** — system-level installs, nothing to commit.

---

## Task 6: Start the Worker Process

The worker is a standalone Python process that polls the Redis queue.

**Files:**
- Reference: `apps/worker/app/worker/main.py`

**Step 1: Install worker dependencies**

```bash
cd apps/worker
pip install -r requirements.txt
# Or if using a venv:
# python -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt
```

Check that the worker's dependencies are satisfied. Key packages:
- `httpx` (HTTP client for Redis REST + internal API)
- `boto3` (R2/S3 uploads)
- `pydantic` (job serialization)
- `python-dotenv` (loading .env)
- `PyJWT` (not needed in worker, but in API)

**Step 2: Start the worker**

```bash
cd apps/worker
python -m app.worker.main
```

Expected output:
```
[worker] Starting worker with concurrency=2
[worker] Queue length: 0
[worker] status: queue=0 active=0 workers=2
```

If you see `WARNING: Could not connect to Redis queue`, check that Task 4 (Upstash credentials) is done.

**Step 3: Test the full pipeline**

1. Start the API: `cd apps/api && uvicorn app.main:app --reload --port 8000`
2. Start the worker: `cd apps/worker && python -m app.worker.main`
3. Start the frontend: `cd apps/web && npm run dev`
4. Navigate to a project → repository → click "Run Scan"
5. Watch the worker terminal — you should see:
   ```
   [worker] Processing job <uuid> (scan.repo.full)
   ```
6. The scan status in the UI should progress: queued → running → completed (or failed with a meaningful error)

**Step 4: Troubleshooting**

If the scan fails, check:
- **"Failed to enqueue"** → Redis credentials wrong (Task 4)
- **"git clone failed"** → GitHub token issue. Test the clone-url endpoint manually (Task 2)
- **"Scanner timed out" / "No such file or directory"** → Scanner binary not installed (Task 5)
- **"Failed to update scan status: 401"** → INTERNAL_API_KEY mismatch (Task 3)
- **R2 upload fails** → R2 credentials are still placeholder. This is non-blocking — findings will still persist, just no raw artifact uploads. Set up R2 later if needed.

**Do not commit** — this is a runtime step.

---

## Dependency Order

```
Task 4 (Redis setup) ─┐
                       ├─► Task 1 (enqueue in API) ─┐
Task 5 (install bins) ─┘                            │
                                                     ├─► Task 6 (start worker, test)
Task 3 (add auth header) ───────────────────────────┤
Task 2 (clone implementation) ──────────────────────┘
```

Tasks 2, 3, 4, 5 can be done in parallel. Task 1 requires Task 4. Task 6 requires all others.

---

## Summary of Code Changes

| # | File | Change |
|---|------|--------|
| 1 | `apps/api/app/api/v1/routes/scans.py` | Add queue enqueue after scan creation |
| 1 | `apps/api/app/clients/queue.py` (new) | Copy QueueClient from worker |
| 2 | `apps/worker/app/services/scan_orchestrator.py` | Implement `_prepare_repository` with git clone |
| 2 | `apps/api/app/api/v1/routes/internal.py` | Add `/internal/repositories/{id}/clone-url` endpoint |
| 3 | `apps/worker/app/services/scan_orchestrator.py` | Add `X-Service-Key` header to HTTP calls |
| 4 | `.env` | Real Upstash Redis credentials |
| 5 | System | Install trivy, gitleaks, osv-scanner |
| 6 | Terminal | Start worker process |
