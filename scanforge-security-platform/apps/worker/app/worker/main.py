"""Worker entry point — polls the scan queue and orchestrates scan execution."""

from __future__ import annotations

import asyncio
import os
import signal
import traceback
from pathlib import Path


# Load .env from repo root before reading os.environ
def _load_env():
    current = Path(__file__).resolve()
    for parent in current.parents:
        env_path = parent / ".env"
        if env_path.exists():
            from dotenv import load_dotenv

            load_dotenv(env_path, override=False)
            return


_load_env()

from app.clients.queue import QueueClient  # noqa: E402
from app.clients.r2 import R2Client  # noqa: E402
from app.core.logging import configure_logging, get_logger  # noqa: E402
from app.services.notifications import NotificationDispatcher  # noqa: E402
from app.services.scan_orchestrator import ScanOrchestrator  # noqa: E402

configure_logging(level=os.environ.get("LOG_LEVEL", "INFO"))
_log = get_logger(__name__)


class Worker:
    def __init__(
        self,
        concurrency: int = 2,
        poll_interval: float = 5.0,
        shutdown_timeout: float = 30.0,
    ):
        self.concurrency = concurrency
        self.poll_interval = poll_interval
        self.shutdown_timeout = shutdown_timeout
        self._running = False
        self._shutdown_event = asyncio.Event()

    def _get_clients(self):
        redis_url = os.environ.get("UPSTASH_REDIS_REST_URL", "")
        redis_token = os.environ.get("UPSTASH_REDIS_REST_TOKEN", "")
        r2_endpoint = os.environ.get("R2_ENDPOINT", "")
        r2_bucket = os.environ.get("R2_BUCKET", "")
        r2_access = os.environ.get("R2_ACCESS_KEY_ID", "")
        r2_secret = os.environ.get("R2_SECRET_ACCESS_KEY", "")
        r2_public = os.environ.get("R2_PUBLIC_BASE_URL", "")
        api_base = os.environ.get("API_BASE_URL", "http://localhost:8000")

        queue = QueueClient(redis_url=redis_url, redis_token=redis_token)
        r2 = R2Client(
            endpoint=r2_endpoint,
            bucket=r2_bucket,
            access_key_id=r2_access,
            secret_access_key=r2_secret,
            public_base_url=r2_public,
        )
        return queue, r2, api_base

    async def process_single_job(self, queue: QueueClient, orchestrator: ScanOrchestrator):
        try:
            job = await queue.dequeue(timeout_seconds=5)
            if job is None:
                return

            _log.info("processing job", extra={"job_id": job.job_id, "job_type": job.job_type})

            success = await orchestrator.process_job(job)

            if success:
                _log.info("job completed successfully", extra={"job_id": job.job_id})
            else:
                retry_count = await queue.get_retry_count(job.job_id)
                _log.info(
                    "job failed in orchestrator",
                    extra={
                        "job_id": job.job_id,
                        "retry_count": retry_count,
                        "max_retries": orchestrator.MAX_RETRIES,
                    },
                )

        except Exception as e:
            _log.error("error processing job", extra={"error": str(e), "traceback": traceback.format_exc()})

    async def run(self):
        queue, r2, api_base = self._get_clients()
        orchestrator = ScanOrchestrator(
            queue=queue,
            r2=r2,
            api_base_url=api_base,
        )
        orchestrator.set_notifier(
            NotificationDispatcher(
                api_base_url=api_base,
                internal_api_key=os.environ.get("INTERNAL_API_KEY", ""),
            )
        )

        _log.info("starting worker", extra={"concurrency": self.concurrency})

        try:
            queue_len = await queue.get_queue_length()
            _log.info("queue length", extra={"length": queue_len})
        except Exception as e:
            _log.warning(
                "could not connect to Redis queue — check UPSTASH_REDIS_REST_URL and UPSTASH_REDIS_REST_TOKEN",
                extra={"error": str(e)},
            )

        self._running = True
        tasks: list[asyncio.Task] = []

        async def worker_loop():
            while self._running:
                active = [t for t in tasks if not t.done()]

                if len(active) < self.concurrency:
                    task = asyncio.create_task(self.process_single_job(queue, orchestrator))
                    tasks.append(task)

                await asyncio.sleep(1)

                done = [t for t in tasks if t.done()]
                for t in done:
                    tasks.remove(t)

        async def monitor_loop():
            while self._running:
                try:
                    ql = await queue.get_queue_length()
                    active = len([t for t in tasks if not t.done()])
                    _log.info(
                        "worker status",
                        extra={"queue_length": ql, "active_tasks": active, "workers": self.concurrency},
                    )
                except Exception:
                    pass
                await asyncio.sleep(30)

        loops = [asyncio.create_task(worker_loop()), asyncio.create_task(monitor_loop())]

        try:
            await asyncio.gather(*loops)
        except asyncio.CancelledError:
            _log.info("shutdown signal received")
        finally:
            self._running = False
            _log.info(
                "waiting for active tasks to complete",
                extra={"active_tasks": len(tasks), "timeout": self.shutdown_timeout},
            )
            await asyncio.wait_for(
                asyncio.gather(*tasks, return_exceptions=True),
                timeout=self.shutdown_timeout,
            )
            _log.info("shutdown complete")


def main():
    concurrency = int(os.environ.get("WORKER_CONCURRENCY", "2"))
    worker = Worker(concurrency=concurrency)

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, lambda: asyncio.create_task(_shutdown(worker)))

    try:
        loop.run_until_complete(worker.run())
    except KeyboardInterrupt:
        _log.info("interrupted")
    finally:
        loop.close()


async def _shutdown(worker: Worker):
    worker._running = False
    await asyncio.sleep(0.1)


if __name__ == "__main__":
    main()
