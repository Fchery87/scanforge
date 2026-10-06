import asyncio
import os

import httpx


async def trigger_due_scan_schedules(
    *,
    api_base_url: str | None = None,
    scheduler_api_key: str | None = None,
) -> dict:
    base_url = (api_base_url or os.environ.get("API_BASE_URL") or "http://localhost:8000").rstrip("/")
    scheduler_key = scheduler_api_key or os.environ.get("SCHEDULER_API_KEY", "")

    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{base_url}/api/v1/internal/scan-schedules/run-due",
            headers={"X-Scheduler-Key": scheduler_key},
            timeout=60.0,
        )
        response.raise_for_status()
        return response.json()


async def retry_github_checks() -> dict:
    base_url = os.environ.get("API_BASE_URL", "http://localhost:8000").rstrip("/")
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{base_url}/api/v1/internal/github-checks/retry",
            headers={"X-Scheduler-Key": os.environ.get("SCHEDULER_API_KEY", "")},
            timeout=450.0,
        )
        response.raise_for_status()
        return response.json()


async def run_scheduled_scans():
    results = await asyncio.gather(trigger_due_scan_schedules(), retry_github_checks(), return_exceptions=True)
    for name, result in zip(("schedules", "github_checks"), results, strict=True):
        if isinstance(result, BaseException):
            print(f"[scheduler] {name} failed ({type(result).__name__})")
        else:
            print(f"[scheduler] {name} processed {result}")
    if any(isinstance(result, BaseException) for result in results):
        raise RuntimeError("Scheduler maintenance failed")


if __name__ == "__main__":
    asyncio.run(run_scheduled_scans())
