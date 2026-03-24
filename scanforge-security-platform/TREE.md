# Project Tree

```text
repo-security-platform
├── apps
│   ├── api
│   │   ├── alembic
│   │   │   ├── versions
│   │   │   │   └── 0001_initial_placeholder.py
│   │   │   └── env.py
│   │   ├── app
│   │   │   ├── api
│   │   │   │   └── v1
│   │   │   │       ├── routes
│   │   │   │       │   └── health.py
│   │   │   │       └── router.py
│   │   │   ├── core
│   │   │   │   └── config.py
│   │   │   ├── db
│   │   │   │   ├── models
│   │   │   │   │   ├── __init__.py
│   │   │   │   │   ├── artifact.py
│   │   │   │   │   ├── audit.py
│   │   │   │   │   ├── finding.py
│   │   │   │   │   ├── organization.py
│   │   │   │   │   ├── policy.py
│   │   │   │   │   ├── project.py
│   │   │   │   │   ├── repository.py
│   │   │   │   │   ├── scan.py
│   │   │   │   │   └── user.py
│   │   │   │   ├── base.py
│   │   │   │   ├── enums.py
│   │   │   │   ├── mixins.py
│   │   │   │   └── session.py
│   │   │   └── main.py
│   │   ├── README.md
│   │   ├── alembic.ini
│   │   └── pyproject.toml
│   ├── web
│   │   ├── app
│   │   │   ├── (dashboard)
│   │   │   │   └── dashboard
│   │   │   │       └── page.tsx
│   │   │   ├── layout.tsx
│   │   │   └── page.tsx
│   │   ├── lib
│   │   │   └── api.ts
│   │   ├── README.md
│   │   ├── next-env.d.ts
│   │   ├── next.config.ts
│   │   ├── package.json
│   │   └── tsconfig.json
│   └── worker
│       ├── app
│       │   ├── scanners
│       │   │   ├── base.py
│       │   │   ├── gitleaks.py
│       │   │   ├── osv.py
│       │   │   └── trivy.py
│       │   └── worker
│       │       └── main.py
│       ├── README.md
│       └── pyproject.toml
├── docs
│   ├── adr
│   │   ├── ADR-001-web-first-product.md
│   │   └── ADR-002-canonical-finding-model.md
│   └── architecture
│       ├── implementation-plan.md
│       └── system-overview.md
├── infra
│   ├── r2
│   │   └── r2-layout.md
│   ├── render
│   │   └── render-blueprint.md
│   ├── upstash
│   │   └── queue-design.md
│   └── vercel
│       └── vercel-notes.md
├── packages
│   └── contracts
│       └── README.md
├── spec
│   ├── API_OVERVIEW.md
│   ├── DB_SCHEMA.md
│   ├── PRD.md
│   ├── RBAC.md
│   ├── README.md
│   ├── ROADMAP.md
│   ├── SCANNER_PIPELINE.md
│   ├── STACK.md
│   └── TASKS.md
├── .env.example
├── .gitignore
├── Makefile
└── README.md
```
