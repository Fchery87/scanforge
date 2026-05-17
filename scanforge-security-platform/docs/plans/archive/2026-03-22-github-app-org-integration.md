# GitHub App Org-Level Integration Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace the manual repository-connect form with a GitHub App OAuth flow where users install the App once at the org level, then pick repos from a list for any project.

**Architecture:** A new `organization_integrations` table stores the GitHub App `installation_id` at the org level. Three new backend endpoints handle the install URL, callback save, and repo listing (via GitHub API). The frontend onboarding flow gains a "Connect GitHub" step, and the repositories page replaces its manual form modal with a searchable repo picker populated from the org's installation.

**Tech Stack:** FastAPI (Python 3.12), SQLAlchemy 2 async, Alembic, `httpx` (already in venv) for GitHub API calls, Next.js 15 App Router, TypeScript

---

## Task 1: Add `GITHUB_APP_SLUG` to config

**Files:**
- Modify: `apps/api/app/core/config.py`

The GitHub App install URL requires the App's slug (e.g. `scanforge`), which is different from the numeric `GITHUB_APP_ID`. We need to expose it.

**Step 1: Add the field**

In `apps/api/app/core/config.py`, add after `GITHUB_APP_ID`:

```python
GITHUB_APP_SLUG: str = ""
```

**Step 2: Verify app starts**

```bash
cd apps/api && python -c "from app.core.config import settings; print(settings.GITHUB_APP_SLUG)"
```
Expected: prints empty string (no crash).

**Step 3: Commit**

```bash
git add apps/api/app/core/config.py
git commit -m "feat: add GITHUB_APP_SLUG to settings"
```

---

## Task 2: DB migration — `organization_integrations` table

**Files:**
- Create: `apps/api/alembic/versions/0007_org_github_integration.py`

**Step 1: Create the migration file**

```python
"""org github integration

Revision ID: 0007_org_github_integration
Revises: 0006_operational_support
Create Date: 2026-03-22
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy import func

revision = "0007_org_github_integration"
down_revision = "0006_operational_support"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "organization_integrations",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=func.gen_random_uuid(),
        ),
        sa.Column(
            "organization_id",
            UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("provider", sa.String(50), nullable=False, server_default="github"),
        sa.Column("installation_id", sa.String(255), nullable=False),
        sa.Column("account_login", sa.String(255), nullable=True),
        sa.Column("account_type", sa.String(50), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=func.now(),
            onupdate=func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_org_integrations_org_id", "organization_integrations", ["organization_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_org_integrations_org_id", "organization_integrations")
    op.drop_table("organization_integrations")
```

**Step 2: Run the migration**

```bash
cd apps/api && python -m alembic upgrade head
```
Expected: `Running upgrade 0006_operational_support -> 0007_org_github_integration`

**Step 3: Commit**

```bash
git add apps/api/alembic/versions/0007_org_github_integration.py
git commit -m "feat: add organization_integrations migration"
```

---

## Task 3: SQLAlchemy model — `OrganizationIntegration`

**Files:**
- Modify: `apps/api/app/db/models/organization.py`
- Modify: `apps/api/app/db/models/__init__.py`

**Step 1: Add the model to `organization.py`**

Append after the `OrganizationMember` class:

```python
class OrganizationIntegration(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "organization_integrations"
    organization_id: Mapped[str] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    provider: Mapped[str] = mapped_column(String(50), nullable=False, default="github")
    installation_id: Mapped[str] = mapped_column(String(255), nullable=False)
    account_login: Mapped[str | None] = mapped_column(String(255))
    account_type: Mapped[str | None] = mapped_column(String(50))
```

**Step 2: Export from `__init__.py`**

In `apps/api/app/db/models/__init__.py`:
- Add to imports: `from app.db.models.organization import Organization, OrganizationIntegration, OrganizationMember`
- Add `"OrganizationIntegration"` to `__all__`

**Step 3: Verify import**

```bash
cd apps/api && python -c "from app.db.models import OrganizationIntegration; print('ok')"
```
Expected: `ok`

**Step 4: Commit**

```bash
git add apps/api/app/db/models/organization.py apps/api/app/db/models/__init__.py
git commit -m "feat: add OrganizationIntegration SQLAlchemy model"
```

---

## Task 4: Pydantic schemas for GitHub integration

**Files:**
- Create: `apps/api/app/schemas/github.py`

**Step 1: Create the schema file**

```python
from pydantic import BaseModel


class GitHubInstallUrlResponse(BaseModel):
    url: str


class GitHubConnectRequest(BaseModel):
    installation_id: str
    account_login: str | None = None
    account_type: str | None = None


class GitHubIntegrationResponse(BaseModel):
    id: str
    organization_id: str
    provider: str
    installation_id: str
    account_login: str | None
    account_type: str | None

    model_config = {"from_attributes": True}


class GitHubRepoItem(BaseModel):
    external_repo_id: str
    owner_name: str
    repo_name: str
    full_name: str
    default_branch: str | None
    clone_url: str | None
    html_url: str | None
    private: bool


class GitHubRepoListResponse(BaseModel):
    items: list[GitHubRepoItem]
    total: int
```

**Step 2: Verify import**

```bash
cd apps/api && python -c "from app.schemas.github import GitHubRepoListResponse; print('ok')"
```
Expected: `ok`

**Step 3: Commit**

```bash
git add apps/api/app/schemas/github.py
git commit -m "feat: add GitHub integration Pydantic schemas"
```

---

## Task 5: `GitHubService` — install URL, save integration, list repos

**Files:**
- Create: `apps/api/app/services/github.py`

This service handles all GitHub App API calls. It uses `httpx.AsyncClient` (already installed) to call GitHub's REST API authenticated as the App using a JWT, then as the installation using an installation access token.

**Step 1: Create the service**

```python
import time
from uuid import UUID

import httpx
import jwt  # PyJWT — already in venv via python-jose or install separately
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.models.organization import OrganizationIntegration
from app.schemas.github import GitHubConnectRequest, GitHubRepoItem


def _make_app_jwt() -> str:
    """Create a signed JWT to authenticate as the GitHub App."""
    now = int(time.time())
    payload = {
        "iat": now - 60,
        "exp": now + (10 * 60),
        "iss": settings.GITHUB_APP_ID,
    }
    private_key = settings.GITHUB_PRIVATE_KEY.replace("\\n", "\n")
    return jwt.encode(payload, private_key, algorithm="RS256")


class GitHubService:
    def __init__(self, db: AsyncSession):
        self.db = db

    def get_install_url(self, org_id: str) -> str:
        state = org_id  # state param carries org_id back through OAuth redirect
        return (
            f"https://github.com/apps/{settings.GITHUB_APP_SLUG}/installations/new"
            f"?state={state}"
        )

    async def save_integration(
        self,
        org_id: UUID,
        data: GitHubConnectRequest,
    ) -> OrganizationIntegration:
        # Upsert: replace if already exists for this org
        result = await self.db.execute(
            select(OrganizationIntegration).where(
                OrganizationIntegration.organization_id == str(org_id)
            )
        )
        integration = result.scalar_one_or_none()

        if integration:
            integration.installation_id = data.installation_id
            integration.account_login = data.account_login
            integration.account_type = data.account_type
        else:
            integration = OrganizationIntegration(
                organization_id=str(org_id),
                provider="github",
                installation_id=data.installation_id,
                account_login=data.account_login,
                account_type=data.account_type,
            )
            self.db.add(integration)

        await self.db.commit()
        await self.db.refresh(integration)
        return integration

    async def get_integration(self, org_id: UUID) -> OrganizationIntegration | None:
        result = await self.db.execute(
            select(OrganizationIntegration).where(
                OrganizationIntegration.organization_id == str(org_id)
            )
        )
        return result.scalar_one_or_none()

    async def delete_integration(self, org_id: UUID) -> bool:
        integration = await self.get_integration(org_id)
        if not integration:
            return False
        await self.db.delete(integration)
        await self.db.commit()
        return True

    async def _get_installation_token(self, installation_id: str) -> str:
        """Exchange App JWT for an installation access token."""
        app_jwt = _make_app_jwt()
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"https://api.github.com/app/installations/{installation_id}/access_tokens",
                headers={
                    "Authorization": f"Bearer {app_jwt}",
                    "Accept": "application/vnd.github+json",
                    "X-GitHub-Api-Version": "2022-11-28",
                },
            )
            resp.raise_for_status()
            return resp.json()["token"]

    async def list_repositories(
        self, installation_id: str, per_page: int = 100
    ) -> list[GitHubRepoItem]:
        token = await self._get_installation_token(installation_id)
        repos: list[GitHubRepoItem] = []
        page = 1

        async with httpx.AsyncClient() as client:
            while True:
                resp = await client.get(
                    "https://api.github.com/installation/repositories",
                    headers={
                        "Authorization": f"Bearer {token}",
                        "Accept": "application/vnd.github+json",
                        "X-GitHub-Api-Version": "2022-11-28",
                    },
                    params={"per_page": per_page, "page": page},
                )
                resp.raise_for_status()
                data = resp.json()
                for r in data.get("repositories", []):
                    repos.append(
                        GitHubRepoItem(
                            external_repo_id=str(r["id"]),
                            owner_name=r["owner"]["login"],
                            repo_name=r["name"],
                            full_name=r["full_name"],
                            default_branch=r.get("default_branch"),
                            clone_url=r.get("clone_url"),
                            html_url=r.get("html_url"),
                            private=r.get("private", False),
                        )
                    )
                # GitHub paginates: stop when we get fewer than per_page
                if len(data.get("repositories", [])) < per_page:
                    break
                page += 1

        return repos
```

**Step 2: Check PyJWT is available**

```bash
cd apps/api && python -c "import jwt; print(jwt.__version__)"
```

If missing, install it:
```bash
cd apps/api && uv add PyJWT cryptography
```

**Step 3: Verify import**

```bash
cd apps/api && python -c "from app.services.github import GitHubService; print('ok')"
```
Expected: `ok`

**Step 4: Commit**

```bash
git add apps/api/app/services/github.py
git commit -m "feat: add GitHubService for App JWT, install URL, repo listing"
```

---

## Task 6: GitHub API routes

**Files:**
- Create: `apps/api/app/api/v1/routes/github.py`
- Modify: `apps/api/app/api/v1/router.py`

**Step 1: Create `github.py` route file**

```python
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.middleware.auth import UserContext, get_current_user
from app.schemas.github import (
    GitHubConnectRequest,
    GitHubInstallUrlResponse,
    GitHubIntegrationResponse,
    GitHubRepoListResponse,
)
from app.services.github import GitHubService
from app.services.organizations import OrganizationService

router = APIRouter()


@router.get(
    "/organizations/{org_id}/github/install-url",
    response_model=GitHubInstallUrlResponse,
)
async def get_github_install_url(
    org_id: UUID,
    current_user: UserContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    org_service = OrganizationService(db)
    org = await org_service.get_by_id(org_id, current_user.user_id)
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")

    gh = GitHubService(db)
    url = gh.get_install_url(str(org_id))
    return GitHubInstallUrlResponse(url=url)


@router.post(
    "/organizations/{org_id}/github/connect",
    response_model=GitHubIntegrationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def connect_github(
    org_id: UUID,
    data: GitHubConnectRequest,
    current_user: UserContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    org_service = OrganizationService(db)
    has_permission = await org_service.user_has_permission(
        org_id, current_user.user_id, ["admin", "owner"]
    )
    if not has_permission:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins and owners can connect GitHub",
        )

    gh = GitHubService(db)
    integration = await gh.save_integration(org_id, data)
    return integration


@router.get(
    "/organizations/{org_id}/github/repositories",
    response_model=GitHubRepoListResponse,
)
async def list_github_repositories(
    org_id: UUID,
    current_user: UserContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    org_service = OrganizationService(db)
    org = await org_service.get_by_id(org_id, current_user.user_id)
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")

    gh = GitHubService(db)
    integration = await gh.get_integration(org_id)
    if not integration:
        raise HTTPException(
            status_code=404,
            detail="No GitHub integration found. Connect GitHub first.",
        )

    repos = await gh.list_repositories(integration.installation_id)
    return GitHubRepoListResponse(items=repos, total=len(repos))


@router.get(
    "/organizations/{org_id}/github/integration",
    response_model=GitHubIntegrationResponse,
)
async def get_github_integration(
    org_id: UUID,
    current_user: UserContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    org_service = OrganizationService(db)
    org = await org_service.get_by_id(org_id, current_user.user_id)
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")

    gh = GitHubService(db)
    integration = await gh.get_integration(org_id)
    if not integration:
        raise HTTPException(status_code=404, detail="No GitHub integration found")
    return integration


@router.delete(
    "/organizations/{org_id}/github/integration",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def disconnect_github(
    org_id: UUID,
    current_user: UserContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    org_service = OrganizationService(db)
    has_permission = await org_service.user_has_permission(
        org_id, current_user.user_id, ["admin", "owner"]
    )
    if not has_permission:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins and owners can disconnect GitHub",
        )

    gh = GitHubService(db)
    deleted = await gh.delete_integration(org_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="No GitHub integration found")
```

**Step 2: Register in `router.py`**

In `apps/api/app/api/v1/router.py`:

Add import:
```python
from app.api.v1.routes import (
    ...
    github,
    ...
)
```

Add router registration (before the organizations router):
```python
api_router.include_router(github.router, tags=["github"])
```

**Step 3: Start API and verify routes appear**

```bash
cd apps/api && python -m uvicorn app.main:app --port 8000 &
sleep 2 && curl -s http://localhost:8000/api/v1/openapi.json | python -m json.tool | grep "github"
kill %1
```
Expected: Lines showing `/organizations/{org_id}/github/install-url` etc.

**Step 4: Commit**

```bash
git add apps/api/app/api/v1/routes/github.py apps/api/app/api/v1/router.py
git commit -m "feat: add GitHub App API routes (install-url, connect, repos, disconnect)"
```

---

## Task 7: Update `api.ts` — add GitHub API client methods

**Files:**
- Modify: `apps/web/lib/api.ts`

**Step 1: Add `github` namespace to the `api` object**

Add after the `organizations` block:

```typescript
github: {
  getInstallUrl: (orgId: string) =>
    request<{ url: string }>(`/organizations/${orgId}/github/install-url`),
  connect: (orgId: string, data: { installation_id: string; account_login?: string; account_type?: string }) =>
    request<any>(`/organizations/${orgId}/github/connect`, {
      method: "POST",
      body: JSON.stringify(data),
    }),
  getIntegration: (orgId: string) =>
    request<any>(`/organizations/${orgId}/github/integration`),
  listRepositories: (orgId: string) =>
    request<{ items: any[]; total: number }>(`/organizations/${orgId}/github/repositories`),
  disconnect: (orgId: string) =>
    request<void>(`/organizations/${orgId}/github/integration`, { method: "DELETE" }),
},
```

**Step 2: Verify TypeScript compiles**

```bash
cd apps/web && npx tsc --noEmit 2>&1 | head -20
```
Expected: No errors on `lib/api.ts`.

**Step 3: Commit**

```bash
git add apps/web/lib/api.ts
git commit -m "feat: add GitHub API methods to frontend api client"
```

---

## Task 8: GitHub callback page — handles redirect from GitHub

**Files:**
- Create: `apps/web/app/(dashboard)/github/callback/page.tsx`

This page handles the URL GitHub redirects to after App installation:
`/github/callback?installation_id=123&state={org_id}&setup_action=install`

It saves the integration via the API, then redirects to the org onboarding page.

**Step 1: Create the page**

```tsx
"use client";

import { useEffect, useRef } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import { Suspense } from "react";
import { api } from "@/lib/api";

function CallbackContent() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const ran = useRef(false);

  useEffect(() => {
    if (ran.current) return;
    ran.current = true;

    const installationId = searchParams.get("installation_id");
    const orgId = searchParams.get("state"); // we pass org_id as state
    const setupAction = searchParams.get("setup_action");

    if (!installationId || !orgId) {
      router.replace("/dashboard");
      return;
    }

    api.github
      .connect(orgId, { installation_id: installationId })
      .then(() => {
        router.replace(`/dashboard/${orgId}/onboarding?org_id=${orgId}&github_connected=true`);
      })
      .catch(() => {
        router.replace(`/dashboard/${orgId}?github_error=true`);
      });
  }, [searchParams, router]);

  return (
    <div style={{ display: "flex", alignItems: "center", justifyContent: "center", height: "100vh" }}>
      <p>Connecting GitHub...</p>
    </div>
  );
}

export default function GitHubCallbackPage() {
  return (
    <Suspense fallback={<div />}>
      <CallbackContent />
    </Suspense>
  );
}
```

**Step 2: Configure GitHub App callback URL**

In your GitHub App settings, set the "Callback URL" (also called "Post installation setup URL") to:
```
http://localhost:3000/github/callback
```
(or your production URL in prod).

**Step 3: Verify the page renders**

```bash
cd apps/web && npm run build 2>&1 | tail -20
```
Expected: No build errors.

**Step 4: Commit**

```bash
git add apps/web/app/(dashboard)/github/callback/page.tsx
git commit -m "feat: add GitHub App OAuth callback page"
```

---

## Task 9: Update onboarding backend — add `connect_github` step

**Files:**
- Modify: `apps/worker/app/services/onboarding.py`
- Modify: `apps/api/app/api/v1/routes/internal.py` (the onboarding endpoint)

**Step 1: Update `build_onboarding_checklist` to accept `has_github` param**

In `apps/worker/app/services/onboarding.py`, update the function signature and add the new step between `create_org` and `create_project`:

```python
def build_onboarding_checklist(
    user_id: str,
    org_id: str | None,
    has_github: bool,          # NEW
    has_projects: bool,
    has_repositories: bool,
    has_scans: bool,
    has_findings: bool,
) -> OnboardingChecklist:
```

Insert this step after `create_org` and before `create_project`:

```python
steps.append(OnboardingStep(
    id="connect_github",
    label="Connect GitHub",
    description="Install the ScanForge GitHub App to access your repositories",
    completed=has_github,
    action_url=None if has_github else f"/dashboard/{org_id}/settings#integrations",
))
```

**Step 2: Update the onboarding API route to pass `has_github`**

Find `apps/api/app/api/v1/routes/internal.py` (the `GET /onboarding` endpoint). It needs to query `organization_integrations` to determine `has_github`.

Locate the section where `build_onboarding_checklist` is called and add:

```python
from app.db.models.organization import OrganizationIntegration
from sqlalchemy import select, exists

# Before calling build_onboarding_checklist, add:
has_github = False
if org_id:
    github_result = await db.execute(
        select(exists().where(
            OrganizationIntegration.organization_id == str(org_id)
        ))
    )
    has_github = github_result.scalar()

# Update the call:
checklist = build_onboarding_checklist(
    user_id=...,
    org_id=org_id,
    has_github=has_github,   # NEW
    has_projects=has_projects,
    has_repositories=has_repositories,
    has_scans=has_scans,
    has_findings=has_findings,
)
```

**Step 3: Read `internal.py` first, then apply the exact edit**

```bash
cat apps/api/app/api/v1/routes/internal.py
```

Apply changes based on what you see.

**Step 4: Verify app starts without error**

```bash
cd apps/api && python -c "from app.api.v1.routes.internal import router; print('ok')"
```

**Step 5: Commit**

```bash
git add apps/worker/app/services/onboarding.py apps/api/app/api/v1/routes/internal.py
git commit -m "feat: add connect_github step to onboarding checklist"
```

---

## Task 10: Update onboarding frontend — Connect GitHub step card

**Files:**
- Modify: `apps/web/app/(dashboard)/onboarding/page.tsx`

**Step 1: Add the `connect_github` icon to `STEP_ICONS`**

```tsx
import { ..., Github } from "lucide-react";

const STEP_ICONS: Record<string, React.ReactNode> = {
  ...
  connect_github: <Github size={20} />,
};
```

**Step 2: Add inline Connect GitHub action for the `connect_github` step**

In the step card rendering section, add handling for the `connect_github` step alongside the existing `create_org` inline form:

```tsx
{step.id === "connect_github" && !step.completed && orgId && (
  <ConnectGitHubButton orgId={orgId} />
)}
```

**Step 3: Create `ConnectGitHubButton` component inline in the file**

Add above the `OnboardingContent` function:

```tsx
function ConnectGitHubButton({ orgId }: { orgId: string }) {
  const [loading, setLoading] = useState(false);

  const handleConnect = async () => {
    setLoading(true);
    try {
      const { url } = await api.github.getInstallUrl(orgId);
      window.location.href = url;
    } catch {
      setLoading(false);
    }
  };

  return (
    <button onClick={handleConnect} disabled={loading} className={styles.inlineBtn}>
      {loading ? "Redirecting..." : "Connect GitHub"}
    </button>
  );
}
```

**Step 4: Handle `github_connected=true` query param — show success toast/message**

After the existing `searchParams` usage, add:

```tsx
const githubConnected = searchParams.get("github_connected") === "true";
```

And in the JSX, show a success banner if `githubConnected`:

```tsx
{githubConnected && (
  <div className={styles.completeBanner}>
    <CheckCircle2 size={20} />
    <span>GitHub connected successfully!</span>
  </div>
)}
```

**Step 5: Build to verify no errors**

```bash
cd apps/web && npx tsc --noEmit 2>&1 | head -30
```

**Step 6: Commit**

```bash
git add apps/web/app/(dashboard)/onboarding/page.tsx
git commit -m "feat: add Connect GitHub step to onboarding UI"
```

---

## Task 11: Replace repositories page manual form with GitHub repo picker

**Files:**
- Modify: `apps/web/app/(dashboard)/dashboard/[org_id]/projects/[project_id]/repositories/page.tsx`

This is the biggest frontend change. The modal form is replaced entirely.

**Step 1: Replace modal state and form state**

Remove:
```tsx
const [form, setForm] = useState({ provider: "github", owner_name: "", ... });
const [error, setError] = useState("");
```

Add:
```tsx
const [githubRepos, setGithubRepos] = useState<any[]>([]);
const [repoSearch, setRepoSearch] = useState("");
const [selectedRepos, setSelectedRepos] = useState<Set<string>>(new Set());
const [loadingGithubRepos, setLoadingGithubRepos] = useState(false);
const [connectingRepos, setConnectingRepos] = useState(false);
const [connectError, setConnectError] = useState("");
const [hasGithub, setHasGithub] = useState<boolean | null>(null);
```

**Step 2: Load GitHub integration status on mount**

Add inside the existing `useEffect` (after repos load):

```tsx
api.github.getIntegration(org_id as string)
  .then(() => setHasGithub(true))
  .catch(() => setHasGithub(false));
```

**Step 3: Load GitHub repos when modal opens**

```tsx
const handleOpenModal = async () => {
  setShowModal(true);
  if (hasGithub) {
    setLoadingGithubRepos(true);
    try {
      const res = await api.github.listRepositories(org_id as string);
      setGithubRepos(res.items ?? []);
    } catch {
      setConnectError("Failed to load repositories from GitHub");
    } finally {
      setLoadingGithubRepos(false);
    }
  }
};
```

Replace the `onClick` on "Connect Repository" button with `handleOpenModal`.

**Step 4: Replace modal contents**

Replace the entire `<form onSubmit={handleConnect}>` section inside the modal with:

```tsx
{!hasGithub ? (
  <div>
    <p>No GitHub integration found.</p>
    <p>
      Go to{" "}
      <a href={`/dashboard/${org_id}/settings#integrations`}>
        Organization Settings → Integrations
      </a>{" "}
      to connect GitHub first.
    </p>
    <div className={rStyles.modalActions}>
      <button type="button" className={rStyles.btnGhost} onClick={() => setShowModal(false)}>Close</button>
    </div>
  </div>
) : (
  <>
    <input
      placeholder="Search repositories..."
      value={repoSearch}
      onChange={(e) => setRepoSearch(e.target.value)}
      className={rStyles.searchInput}
    />

    {loadingGithubRepos ? (
      <div className={rStyles.loadingRepos}>Loading repositories...</div>
    ) : (
      <div className={rStyles.repoPickerList}>
        {githubRepos
          .filter((r) =>
            r.full_name.toLowerCase().includes(repoSearch.toLowerCase())
          )
          .map((r) => (
            <label key={r.external_repo_id} className={rStyles.repoPickerItem}>
              <input
                type="checkbox"
                checked={selectedRepos.has(r.external_repo_id)}
                onChange={(e) => {
                  const next = new Set(selectedRepos);
                  e.target.checked
                    ? next.add(r.external_repo_id)
                    : next.delete(r.external_repo_id);
                  setSelectedRepos(next);
                }}
              />
              <span className={rStyles.repoPickerName}>{r.full_name}</span>
              {r.private && <span className={rStyles.repoPickerBadge}>private</span>}
            </label>
          ))}
      </div>
    )}

    {connectError && <p className={rStyles.error}>{connectError}</p>}

    <div className={rStyles.modalActions}>
      <button
        type="button"
        className={rStyles.btnGhost}
        onClick={() => { setShowModal(false); setSelectedRepos(new Set()); }}
      >
        Cancel
      </button>
      <button
        type="button"
        className={rStyles.btnPrimary}
        disabled={selectedRepos.size === 0 || connectingRepos}
        onClick={handleConnectSelected}
      >
        {connectingRepos
          ? "Connecting..."
          : `Connect ${selectedRepos.size > 0 ? selectedRepos.size : ""} Repo${selectedRepos.size !== 1 ? "s" : ""}`}
      </button>
    </div>
  </>
)}
```

**Step 5: Add `handleConnectSelected` function**

```tsx
const handleConnectSelected = async () => {
  setConnectingRepos(true);
  setConnectError("");
  const toConnect = githubRepos.filter((r) => selectedRepos.has(r.external_repo_id));
  const errors: string[] = [];

  await Promise.allSettled(
    toConnect.map((r) =>
      api.repositories
        .create(org_id as string, project_id as string, {
          provider: "github",
          external_repo_id: r.external_repo_id,
          owner_name: r.owner_name,
          repo_name: r.repo_name,
          full_name: r.full_name,
          default_branch: r.default_branch ?? "main",
          clone_url: r.clone_url ?? "",
          html_url: r.html_url ?? "",
        })
        .then((repo) => setRepos((prev) => [...prev, repo]))
        .catch((err) => errors.push(err.message))
    )
  );

  setConnectingRepos(false);
  if (errors.length === 0) {
    setShowModal(false);
    setSelectedRepos(new Set());
  } else {
    setConnectError(`${errors.length} repo(s) failed: ${errors[0]}`);
  }
};
```

**Step 6: Update `api.ts` `repositories.create` to accept `external_repo_id`**

In `apps/web/lib/api.ts`, add `external_repo_id?: string` to the `create` data type.

**Step 7: Add CSS for new picker elements**

In `apps/web/app/(dashboard)/dashboard/[org_id]/projects/[project_id]/repositories/page.module.css`, add:

```css
.searchInput {
  width: 100%;
  padding: 8px 12px;
  margin-bottom: 12px;
  border: 1px solid var(--border);
  border-radius: 6px;
  background: var(--input-bg, var(--card));
  color: var(--text);
  font-size: 14px;
}

.repoPickerList {
  max-height: 300px;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 4px;
  margin-bottom: 16px;
}

.repoPickerItem {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 10px;
  border-radius: 6px;
  cursor: pointer;
  transition: background 0.15s;
}

.repoPickerItem:hover {
  background: var(--hover, rgba(255,255,255,0.04));
}

.repoPickerName {
  flex: 1;
  font-size: 13px;
}

.repoPickerBadge {
  font-size: 11px;
  padding: 2px 6px;
  border-radius: 4px;
  background: var(--badge-bg, rgba(255,255,255,0.08));
  color: var(--text-muted);
}

.loadingRepos {
  padding: 24px;
  text-align: center;
  color: var(--text-muted);
  font-size: 13px;
}
```

**Step 8: Build and verify**

```bash
cd apps/web && npx tsc --noEmit 2>&1 | head -30
```

**Step 9: Commit**

```bash
git add apps/web/app/(dashboard)/dashboard/[org_id]/projects/[project_id]/repositories/page.tsx
git add apps/web/app/(dashboard)/dashboard/[org_id]/projects/[project_id]/repositories/page.module.css
git add apps/web/lib/api.ts
git commit -m "feat: replace manual repo form with GitHub App repo picker"
```

---

## Task 12: Add GitHub Integrations card to Org Settings

**Files:**
- Modify: `apps/web/app/(dashboard)/dashboard/[org_id]/settings/page.tsx`

**Step 1: Add integration state**

```tsx
const [githubIntegration, setGithubIntegration] = useState<any>(null);
const [githubLoading, setGithubLoading] = useState(true);
```

**Step 2: Load integration on mount**

```tsx
useEffect(() => {
  if (!org_id) return;
  api.github.getIntegration(org_id as string)
    .then((data) => { setGithubIntegration(data); setGithubLoading(false); })
    .catch(() => setGithubLoading(false));
}, [org_id]);
```

**Step 3: Add GitHub integration handler functions**

```tsx
const handleConnectGitHub = async () => {
  try {
    const { url } = await api.github.getInstallUrl(org_id as string);
    window.location.href = url;
  } catch { /* no-op */ }
};

const handleDisconnectGitHub = async () => {
  if (!confirm("Disconnect GitHub? This will not remove connected repositories but new repos cannot be added.")) return;
  try {
    await api.github.disconnect(org_id as string);
    setGithubIntegration(null);
  } catch { /* no-op */ }
};
```

**Step 4: Add the Integrations settings card**

Add a new card in the `settingsGrid` div, after the General card:

```tsx
<div className={sStyles.settingsCard} id="integrations">
  <div className={sStyles.settingsCardHeader}>
    <Github size={16} />
    <h2>Integrations</h2>
  </div>

  {githubLoading ? (
    <div className={sStyles.securityRow}><span>Loading...</span></div>
  ) : githubIntegration ? (
    <div className={sStyles.securityRow}>
      <div>
        <span className={sStyles.securityLabel}>GitHub App</span>
        <span className={sStyles.securityValue}>
          Connected as <strong>{githubIntegration.account_login ?? "unknown"}</strong>
        </span>
      </div>
      <div style={{ display: "flex", gap: "8px", alignItems: "center" }}>
        <span className={sStyles.securityStatus}>Active</span>
        <button
          className={sStyles.removeBtn}
          onClick={handleDisconnectGitHub}
          title="Disconnect GitHub"
        >
          Disconnect
        </button>
      </div>
    </div>
  ) : (
    <div className={sStyles.securityRow}>
      <div>
        <span className={sStyles.securityLabel}>GitHub App</span>
        <span className={sStyles.securityValue}>Not connected</span>
      </div>
      <button className={sStyles.btnPrimary} onClick={handleConnectGitHub}>
        Connect GitHub
      </button>
    </div>
  )}
</div>
```

**Step 5: Add `Github` icon import**

```tsx
import { Settings, Users, Shield, Save, Trash2, Plus, Github } from "lucide-react";
```

**Step 6: Build and verify**

```bash
cd apps/web && npx tsc --noEmit 2>&1 | head -30
```

**Step 7: Commit**

```bash
git add apps/web/app/(dashboard)/dashboard/[org_id]/settings/page.tsx
git commit -m "feat: add GitHub integration card to org settings"
```

---

## Task 13: Update `.env.example` / documentation

**Files:**
- Modify: `.env.example` or `apps/api/.env.example` (whichever exists)

**Step 1: Find env example file**

```bash
find . -name ".env.example" -not -path "*/node_modules/*" -not -path "*/.venv/*"
```

**Step 2: Add new env var**

Add to the GitHub section:
```
GITHUB_APP_SLUG=your-app-slug-here
```

**Step 3: Commit**

```bash
git add .env.example   # or apps/api/.env.example
git commit -m "docs: add GITHUB_APP_SLUG to env example"
```

---

## Task 14: End-to-end smoke test

This is a manual verification checklist — no automated tests for OAuth flows (they require live GitHub credentials).

**Checklist:**

1. Set `GITHUB_APP_SLUG` in your `.env`
2. Start API: `cd apps/api && uvicorn app.main:app --reload`
3. Start web: `cd apps/web && npm run dev`
4. Register/login and create a new organization
5. Visit `/dashboard/{org_id}/onboarding` — verify "Connect GitHub" step appears as incomplete
6. Click "Connect GitHub" — verify redirect to `https://github.com/apps/{slug}/installations/new`
7. Complete GitHub App installation — verify redirect back to `/github/callback`
8. Verify redirect lands at onboarding with "GitHub connected successfully!" banner
9. Verify "Connect GitHub" step now shows as complete
10. Navigate to Org Settings → verify "GitHub App: Connected as {your-username}"
11. Go to any project → Repositories → click "Connect Repository"
12. Verify modal shows a list of repos from GitHub (not a manual form)
13. Select 1-2 repos → click "Connect" → verify they appear in the list
14. Verify repos have correct metadata (branch, URLs) without manual entry

---

## Summary of Files Changed

| File | Type |
|---|---|
| `apps/api/app/core/config.py` | Modified |
| `apps/api/alembic/versions/0007_org_github_integration.py` | Created |
| `apps/api/app/db/models/organization.py` | Modified |
| `apps/api/app/db/models/__init__.py` | Modified |
| `apps/api/app/schemas/github.py` | Created |
| `apps/api/app/services/github.py` | Created |
| `apps/api/app/api/v1/routes/github.py` | Created |
| `apps/api/app/api/v1/router.py` | Modified |
| `apps/worker/app/services/onboarding.py` | Modified |
| `apps/api/app/api/v1/routes/internal.py` | Modified |
| `apps/web/lib/api.ts` | Modified |
| `apps/web/app/(dashboard)/github/callback/page.tsx` | Created |
| `apps/web/app/(dashboard)/onboarding/page.tsx` | Modified |
| `apps/web/app/(dashboard)/dashboard/[org_id]/projects/[project_id]/repositories/page.tsx` | Modified |
| `apps/web/app/(dashboard)/dashboard/[org_id]/projects/[project_id]/repositories/page.module.css` | Modified |
| `apps/web/app/(dashboard)/dashboard/[org_id]/settings/page.tsx` | Modified |
| `.env.example` | Modified |
