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


async def run_scheduled_scans():
    try:
        result = await trigger_due_scan_schedules()
        print(
            "[scheduler] Processed due schedules "
            f"found={result.get('found', 0)} queued={result.get('queued', 0)} failed={result.get('failed', 0)}"
        )
    except Exception as e:
        print(f"[scheduler] Error processing due schedules: {e}")


if __name__ == "__main__":
    asyncio.run(run_scheduled_scans())
