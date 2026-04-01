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
from app.services.scan_orchestrator import ScanOrchestrator  # noqa: E402


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

            print(f"[worker] Processing job {job.job_id} ({job.job_type})")

            success = await orchestrator.process_job(job)

            if success:
                print(f"[worker] Job {job.job_id} completed successfully")
            else:
                # The orchestrator owns retry and DLQ decisions so failed jobs are
                # not duplicated in the queue by the outer worker loop.
                retry_count = await queue.get_retry_count(job.job_id)
                print(
                    f"[worker] Job {job.job_id} failed in orchestrator "
                    f"(retry_count={retry_count}/{orchestrator.MAX_RETRIES})"
                )

        except Exception as e:
            print(f"[worker] Error processing job: {e}")
            print(traceback.format_exc())

    async def run(self):
        queue, r2, api_base = self._get_clients()
        orchestrator = ScanOrchestrator(
            queue=queue,
            r2=r2,
            api_base_url=api_base,
        )

        print(f"[worker] Starting worker with concurrency={self.concurrency}")

        try:
            queue_len = await queue.get_queue_length()
            print(f"[worker] Queue length: {queue_len}")
        except Exception as e:
            print(f"[worker] WARNING: Could not connect to Redis queue: {e}")
            print("[worker] Check UPSTASH_REDIS_REST_URL and UPSTASH_REDIS_REST_TOKEN in .env")

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
                    print(f"[worker] status: queue={ql} active={active} workers={self.concurrency}")
                except Exception:
                    pass
                await asyncio.sleep(30)

        loops = [asyncio.create_task(worker_loop()), asyncio.create_task(monitor_loop())]

        try:
            await asyncio.gather(*loops)
        except asyncio.CancelledError:
            print("[worker] Shutdown signal received")
        finally:
            self._running = False
            print(f"[worker] Waiting for {len(tasks)} active tasks to complete...")
            await asyncio.wait_for(
                asyncio.gather(*tasks, return_exceptions=True),
                timeout=self.shutdown_timeout,
            )
            print("[worker] Shutdown complete")


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
        print("[worker] Interrupted")
    finally:
        loop.close()


async def _shutdown(worker: Worker):
    worker._running = False
    await asyncio.sleep(0.1)


if __name__ == "__main__":
    main()
