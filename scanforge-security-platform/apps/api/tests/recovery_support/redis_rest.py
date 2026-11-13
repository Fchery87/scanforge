"""Owned Redis REST transport, forwarding every command to real Redis (no state emulation)."""
import json
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import redis

client = redis.Redis(host="127.0.0.1", port=int(sys.argv[1]), decode_responses=True, protocol=2)


class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        args = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        with client.client() as connection:
            connection.response_callbacks = {}
            try:
                payload = {"result": connection.execute_command(*args)}
            except redis.ResponseError as exc:
                payload = {"error": str(exc)}
        body = json.dumps(payload).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *_args):
        pass


ThreadingHTTPServer(("127.0.0.1", int(sys.argv[2])), Handler).serve_forever()
