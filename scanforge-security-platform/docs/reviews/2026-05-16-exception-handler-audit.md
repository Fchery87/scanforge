# Exception Handler Audit — 2026-05-16

OWASP A10:2025 — Mishandling of Exceptional Conditions

## Scope

All `except Exception` and bare `except:` blocks across `apps/api/app` and `apps/worker/app`.

## Methodology

1. `grep -rn "except Exception\|except:" apps/api/app apps/worker/app` — initial enumeration
2. Manual review of each block for: sanitized response, `exc_info=True` logging, no internal detail in HTTP body
3. AST-based advisory script added at `apps/api/scripts/check_exception_handlers.py`

## Findings and Actions

### Fixed

| File | Line | Issue | Fix |
|------|------|-------|-----|
| `apps/api/app/api/v1/routes/github.py` | ~150 | `github_install_callback` — `save_integration` exceptions propagated to global handler without sanitization | Wrapped in `try/except` → `HTTPException(502, GENERIC_EXTERNAL_SERVICE_ERROR)` |
| `apps/api/app/api/v1/routes/internal.py` | 322 | Scheduled scan loop — `except Exception: failed += 1` with no logging | Added `logger.error("Failed to create scheduled scan …", exc_info=True)` |

### Correct — No Change Needed

| File | Pattern | Rationale |
|------|---------|-----------|
| `apps/api/app/api/v1/routes/github.py:115,209` | `except Exception as exc: raise HTTPException(502, GENERIC_EXTERNAL_SERVICE_ERROR)` | Sanitized re-raise. FastAPI global handler logs with `exc_info=True`. |
| `apps/api/app/middleware/audit.py:67,93` | `except Exception: pass` | Intentionally silent — JWT decoding for audit context and audit log creation are non-critical side effects. Failure must not break the request. |
| `apps/api/app/services/github.py:130` | `except Exception: logger.warning(…, exc_info=True)` | Correct — logs with context, best-effort GitHub install detail fetch. |
| `apps/api/app/services/github.py:174` | `except Exception: logger.error(…, exc_info=True); raise` | Correct — logs + re-raises for caller to handle. |
| `apps/api/app/services/scan_lifecycle.py:70` | `except Exception: logger.error(…, exc_info=True)` | Correct — logs + stores `GENERIC_QUEUE_ERROR` in scan record. |
| Worker scanner files (`trivy`, `gitleaks`, etc.) | `except Exception: return ScannerResult(success=False, …)` | Correct — structured failure result. Orchestrator logs the failure in `run_single`. |
| `apps/worker/app/services/scan_pipeline/execution.py:88` | `except Exception: continue` (in `collect_changed_files`) | Best-effort command fallback loop. Outer function returns `[]` on total failure. |
| `apps/worker/app/services/scan_pipeline/persistence.py:106` | `except Exception: pass` (in `send_failure_notification`) | Best-effort notification — must not re-fail an already-failed scan. |
| `apps/worker/app/worker/main.py:86,109,136` | `except Exception: print(…)` | Worker process-level handler. Uses `print` which goes to stdout — captured by container logs. |

### Advisory — No HTTP Exposure, Future Improvement

The `check_exception_handlers.py` script reports the following as advisory (exit 0). No HTTP response exposure; these are worker-internal or middleware patterns. Can be addressed in a future logging cleanup pass:

- `apps/api/app/middleware/audit.py:67,93` — documented above as intentionally silent
- `apps/worker/app/scanners/base.py:43` — scanner base class fallback
- `apps/worker/app/scanners/syft.py:94`, `trivy.py:26` — scanner parse error silencing
- `apps/worker/app/services/scan_pipeline/execution.py:88` — git diff fallback
- `apps/worker/app/services/scan_pipeline/persistence.py:106` — failure notification best-effort

## Regression Tests Added

`tests/test_error_sanitization.py`:
- `test_github_oauth_callback_errors_are_sanitized` — verifies 502 with no internal markers
- `test_github_install_callback_errors_are_sanitized` — verifies 502 with no SQL/path/traceback in detail

The `_INTERNAL_MARKERS` tuple checks for: Traceback, RuntimeError, ValueError, SELECT, INSERT, /home/, .py:, sqlalchemy, asyncpg.

## CI Enforcement

Advisory lint step added to API job:
```yaml
- name: Audit exception handlers (advisory)
  run: python scripts/check_exception_handlers.py
```

Promote to blocking (add `sys.exit(1)`) after a logging cleanup pass over the advisory items.
