# ruff: noqa: S110, RUF059, I001
"""R12 queue recovery drill (invoked by scripts/rehearse_queue_recovery.sh).

Enqueues synthetic QueueJob messages on the organization scan stream, kills a
real consumer process after it claims a delivery but before it acks, then
verifies the production QueueClient XAUTOCLAIM reclaim path recovers the
orphaned pending message with zero message loss. Evidence-only: no app code
changes; the visibility timeout is shortened on the drill client only so the
idle window is testable in seconds.
"""

from __future__ import annotations

import json
import multiprocessing
import os
import shutil
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

WORKER_DIR = os.environ.get(
    "R12_WORKER_DIR",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "apps", "worker"),
)
sys.path.insert(0, os.path.abspath(WORKER_DIR))

STREAM = "queue:scans:00000000-0000-0000-0000-00000000r12"
GROUP = "scanforge-workers"
JOB_COUNT = 5
VISIBILITY_TIMEOUT_MS = 300  # drill-only shortened idle window (client default: 30 min)


def log(msg: str) -> None:
    print(f"[r12_queue_recovery] {msg}", flush=True)


def to_plain(obj):
    if isinstance(obj, bytes):
        return obj.decode()
    if isinstance(obj, dict):
        return {to_plain(k): to_plain(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [to_plain(x) for x in obj]
    return obj


def make_backend():
    """Return (label, redis_client, owned_process_or_None)."""
    import redis

    host = os.environ.get("R12_REDIS_HOST", "127.0.0.1")
    port = int(os.environ.get("R12_REDIS_PORT", "6379"))
    probe = redis.Redis(host=host, port=port, socket_connect_timeout=0.5)
    try:
        probe.ping()
        return f"local-redis {host}:{port}", probe, None
    except Exception:  # noqa: BLE001 (probe: any connection failure means "not a local redis")
        pass

    if shutil.which("redis-server"):
        port2 = 6390
        proc = subprocess.Popen(
            ["redis-server", "--port", str(port2), "--save", "", "--appendonly", "no"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        c = redis.Redis(host="127.0.0.1", port=port2, socket_connect_timeout=8)
        deadline = time.time() + 10
        while time.time() < deadline:
            try:
                c.ping()
                return f"local-redis-disposable 127.0.0.1:{port2} (spawned)", c, proc
            except Exception:  # noqa: BLE001 (spawn retry: any failure means retry)
                time.sleep(0.2)
        proc.terminate()
        raise RuntimeError("spawned redis-server did not become ready")

    import fakeredis

    server = fakeredis.FakeServer()
    c = fakeredis.FakeRedis(server=server, decode_responses=False)
    c.ping()
    return "fakeredis-fallback (no local Redis server available)", c, None


def serve_rest(_backend_label: str, r) -> tuple[ThreadingHTTPServer, int]:
    from redis.exceptions import ResponseError

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *a):  # silence per-request noise
            pass

        def do_POST(self):
            n = int(self.headers.get("Content-Length", "0"))
            args = json.loads(self.rfile.read(n) or b"[]")
            try:
                result = execute(r, args)
                body = json.dumps({"result": result}).encode()
                self.send_response(200)
            except ResponseError as exc:
                import traceback; traceback.print_exc()
                body = json.dumps({"error": str(exc)}).encode()
                self.send_response(400)
            except Exception:  # noqa: BLE001 (drill shim: never crash the harness thread)
                import traceback; traceback.print_exc()
                body = json.dumps({"error": "shim-500"}).encode()
                self.send_response(500)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    def execute(r, args):
        cmd = str(args[0]).upper()
        if cmd == "XGROUP":
            # XGROUP CREATE key group id [MKSTREAM]
            if len(args) >= 6 and str(args[5]).upper() == "MKSTREAM":
                try:
                    r.xgroup_create(args[2], args[3], id=str(args[4]), mkstream=True)
                except ResponseError as exc:
                    if "BUSYGROUP" not in str(exc):
                        raise
                return "OK"
            r.xgroup_create(args[2], args[3], id=str(args[4]))
            return "OK"
        if cmd == "XREADGROUP":
            # XREADGROUP GROUP g c COUNT 1 BLOCK ms STREAMS key >
            res = r.xreadgroup(args[2], args[3], {args[-2]: ">"}, count=int(args[5]), block=int(args[7]))
            return to_plain(res)
        if cmd == "XAUTOCLAIM":
            # XAUTOCLAIM key group consumer min-idle start COUNT n
            cursor, messages, deleted = r.xautoclaim(
                args[1], args[2], args[3], min_idle_time=int(args[4]), start_id=args[5], count=int(args[7])
            )
            return to_plain([str(cursor), messages, deleted])
        if cmd == "XPENDING":
            return to_plain(r.xpending(args[1], args[2]))
        if cmd == "XADD":
            fields = args[2:]
            return to_plain(r.xadd(args[1], dict(zip(fields[::2], fields[1::2], strict=True))))
        if cmd == "XACK":
            return int(r.xack(args[1], args[2], *args[3:]))
        if cmd == "XLEN":
            return int(r.xlen(args[1]))
        if cmd == "XDEL":
            return int(r.xdel(args[1], *args[2:]))
        raise ResponseError(f"drill shim: unsupported command {cmd}")

    srv = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, srv.server_address[1]


def consumer_victim(ready_q, claimed_q, port: int) -> None:
    """Consumer that dies right after claiming: prints claim, then blocks forever."""
    import asyncio

    from app.clients.queue import QueueClient

    class FastClient(QueueClient):
        visibility_timeout_ms = VISIBILITY_TIMEOUT_MS

    async def main():
        client = FastClient(
            f"http://127.0.0.1:{port}/", "drill-token",
            organization_id="00000000-0000-0000-0000-00000000r12",
            consumer_name="victim-consumer",
        )
        ready_q.put("up")
        while True:
            job, status = await client.dequeue_with_status(1)
            if job is not None:
                claimed_q.put((job.job_id, job.stream_entry_id))
                await asyncio.sleep(3600)  # simulates long scan; killed before ack

    asyncio.run(main())


def main() -> int:
    label, r, owned = make_backend()
    log(f"backend: {label}")
    srv, port = serve_rest(label, r)
    log(f"upstash-REST shim at 127.0.0.1:{port} (drill-only harness)")
    failures: list[str] = []
    try:
        from app.clients.queue import QueueClient

        class FastClient(QueueClient):
            visibility_timeout_ms = VISIBILITY_TIMEOUT_MS

        # Enqueue synthetic messages directly on the org stream (same field
        # contract the API-side producer uses: job=<QueueJob JSON>).
        r.delete(STREAM)
        job_ids = []
        t_enqueue0 = time.perf_counter()
        for i in range(JOB_COUNT):
            scan_id = f"r12-drill-scan-{i}"
            from app.contracts.queue import QueueJob
            job = QueueJob(job_type="scan.repo.full", job_id=scan_id, payload={"scan_id": scan_id}, created_at="2026-01-01T00:00:00Z")
            r.xadd(STREAM, {"job": job.model_dump_json(), "job_id": scan_id})
            job_ids.append(scan_id)
        enqueue_ms = (time.perf_counter() - t_enqueue0) * 1000
        log(f"enqueued {JOB_COUNT} synthetic messages in {enqueue_ms:.0f} ms")

        # Start the victim consumer; wait for it to claim one message.
        ready_q: multiprocessing.Queue = multiprocessing.Queue()
        claimed_q: multiprocessing.Queue = multiprocessing.Queue()
        victim = multiprocessing.Process(target=consumer_victim, args=(ready_q, claimed_q, port), daemon=True)
        t_claim0 = time.perf_counter()
        victim.start()
        ready_q.get(timeout=15)
        killed_job, killed_entry = claimed_q.get(timeout=15)
        claim_ms = (time.perf_counter() - t_claim0) * 1000
        log(f"victim consumer claimed {killed_job} (entry {killed_entry}) in {claim_ms:.0f} ms")

        # Kill it mid-claim: no ack, pending entry stays orphaned.
        victim.kill()
        victim.join(timeout=5)
        t_kill = time.perf_counter()
        log(f"victim consumer SIGKILLed mid-claim (pending entry {killed_entry} orphaned)")

        # Recovery consumer reclaims via XAUTOCLAIM, then drains the rest.
        recoverer = FastClient(
            f"http://127.0.0.1:{port}/", "drill-token",
            organization_id="00000000-0000-0000-0000-00000000r12",
            consumer_name="recovery-consumer",
        )
        import asyncio

        async def recover():
            delivered: dict[str, int] = {}
            recovery_ms = None
            deadline = time.time() + 30
            while len(delivered) < JOB_COUNT and time.time() < deadline:
                job, status = await recoverer.dequeue_with_status(1)
                if job is None:
                    continue
                delivered[job.job_id] = delivered.get(job.job_id, 0) + 1
                if job.job_id == killed_job and recovery_ms is None:
                    recovery_ms = (time.perf_counter() - t_kill) * 1000
                    if job.stream_entry_id != killed_entry:
                        raise AssertionError(
                            f"reclaimed entry {job.stream_entry_id} != orphaned {killed_entry}"
                        )
                await recoverer.ack(job)  # persist-then-ack contract simulated by immediate ack
            return delivered, recovery_ms

        t_total0 = time.perf_counter()
        delivered, recovery_ms = asyncio.run(recover())
        total_ms = (time.perf_counter() - t_total0) * 1000
        # Fold in the victim's pre-kill delivery: the orphaned message was
        # delivered once to the killed consumer and once to the recoverer.
        delivered[killed_job] = delivered.get(killed_job, 0) + 1

        # --- assertions: no loss, exact set, at-most-one duplicate (the killed delivery) ---
        dupes = {k: v for k, v in delivered.items() if v > 1}
        lost = sorted(set(job_ids) - set(delivered))
        pending = r.xpending(STREAM, GROUP)["pending"]
        xlen = r.xlen(STREAM)
        dlq_len = r.xlen(STREAM + ":dlq") if r.exists(STREAM + ":dlq") else 0

        log(f"delivered map: {delivered}")
        log(f"XAUTOCLAIM recovered orphaned message {killed_job} in {recovery_ms:.0f} ms")
        log(f"end-to-end (first recovery poll -> last ack): {total_ms:.0f} ms; pending={pending}; stream_len={xlen}; dlq={dlq_len}")

        if lost:
            failures.append(f"message loss: {lost}")
        if pending != 0:
            failures.append(f"pending entries remain: {pending}")
        if xlen != 0:
            failures.append(f"stream not fully acked+deleted: xlen={xlen}")
        if dlq_len != 0:
            failures.append(f"unexpected DLQ entries: {dlq_len}")
        if len(delivered) != JOB_COUNT:
            failures.append(f"distinct delivered {len(delivered)} != {JOB_COUNT}")
        if not dupes or dupes != {killed_job: 2}:
            failures.append(f"expected exactly one redelivery of {killed_job}, got duplicates: {dupes}")
        else:
            log(f"orphaned entry {killed_entry} redelivered exactly once after XAUTOCLAIM")

        if failures:
            for f in failures:
                log(f"FAIL: {f}")
            return 1
        log("RESULT: PASS (0 lost, 0 stranded pending, XAUTOCLAIM reclaim proven, latency above)")
        return 0
    finally:
        srv.shutdown()
        if owned is not None:
            owned.terminate()
            owned.wait(timeout=5)
            log("disposable redis-server stopped")


if __name__ == "__main__":
    multiprocessing.set_start_method("spawn")
    sys.exit(main())
