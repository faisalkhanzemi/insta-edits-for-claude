"""A stand-in for the Edits for Mac automation server (build 454, Nov 2026), matching its observed behaviour.

- requires `Authorization: Bearer <token>` (403 with JSON instructions otherwise, like Edits)
- issues an Mcp-Session-Id on initialize and declares `tools.listChanged`
- marks every result `"resultType": "complete"` without the caching fields newer schemas expect
- swaps its tool set when a project opens, like Edits (home tools -> editor tools)
- by default has NO notification stream and never sends tools/list_changed, like Edits
- options: answer in text/event-stream, offer a GET stream that does notify, send bad cacheScope hints
"""

from __future__ import annotations

import json
import queue
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Optional

TOKEN = "test-token-123"
HOME_TOOLS = [
    {"name": "appState", "inputSchema": {"type": "object"}},
    {"name": "openProject", "inputSchema": {"type": "object"}},
    {"name": "getCapabilities", "inputSchema": {"type": "object"}},
]
EDITOR_TOOLS = HOME_TOOLS + [{"name": "addText", "inputSchema": {"type": "object"}}]


class FakeEdits:
    def __init__(
        self, sse_replies: bool = False, stream: bool = False, cache_scope: Optional[str] = None, port: int = 0
    ):
        self.sse_replies = sse_replies
        self.stream = stream
        self.cache_scope = cache_scope
        self.screen = "home"
        self.session = "sess-1"
        self.notifications: queue.Queue = queue.Queue()
        self.received = []
        fake = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *a):  # keep test output quiet
                pass

            def _auth_ok(self) -> bool:
                if self.headers.get("Authorization") == f"Bearer {TOKEN}":
                    return True
                body = json.dumps({"error": "unauthorized", "instructions": "Access token required."}).encode()
                self.send_response(403)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return False

            def do_GET(self):
                if not self._auth_ok():
                    return
                if not fake.stream:
                    self.send_response(405)
                    self.end_headers()
                    return
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream")
                self.end_headers()
                while True:
                    try:
                        msg = fake.notifications.get(timeout=5)
                    except queue.Empty:
                        return
                    self.wfile.write(f"event: message\ndata: {json.dumps(msg)}\n\n".encode())
                    self.wfile.flush()

            def do_POST(self):
                if not self._auth_ok():
                    return
                msg = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                fake.received.append(
                    {
                        "msg": msg,
                        "session": self.headers.get("Mcp-Session-Id"),
                        "protocol": self.headers.get("MCP-Protocol-Version"),
                    }
                )
                reply = fake.answer(msg)
                if reply is None:
                    self.send_response(202)
                    self.end_headers()
                    return
                if fake.sse_replies:
                    body = f"event: message\ndata: {json.dumps(reply)}\n\n".encode()
                    ctype = "text/event-stream"
                else:
                    body = json.dumps(reply).encode()
                    ctype = "application/json"
                self.send_response(200)
                self.send_header("Content-Type", ctype)
                self.send_header("Content-Length", str(len(body)))
                if msg.get("method") == "initialize":
                    self.send_header("Mcp-Session-Id", fake.session)
                self.end_headers()
                self.wfile.write(body)

        self.httpd = ThreadingHTTPServer(("127.0.0.1", port), Handler)
        self.url = f"http://127.0.0.1:{self.httpd.server_address[1]}/mcp"
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)

    def answer(self, msg: dict):
        method, mid = msg.get("method"), msg.get("id")
        if mid is None:
            return None
        if method == "initialize":
            return {
                "jsonrpc": "2.0",
                "id": mid,
                "result": {
                    "protocolVersion": "2025-06-18",
                    "capabilities": {"tools": {"listChanged": True}},
                    "serverInfo": {"name": "metapilot-native", "version": "1.0.0"},
                },
            }
        if method == "tools/list":
            tools = EDITOR_TOOLS if self.screen == "editor" else HOME_TOOLS
            result = {"tools": tools, "resultType": "complete"}
            if self.cache_scope is not None:
                result["cacheScope"] = self.cache_scope
            return {"jsonrpc": "2.0", "id": mid, "result": result}
        if method == "tools/call":
            name = msg["params"]["name"]
            if name == "openProject":
                self.screen = "editor"
                if self.stream:
                    self.notifications.put({"jsonrpc": "2.0", "method": "notifications/tools/list_changed"})
            if name == "getCapabilities":
                return {
                    "jsonrpc": "2.0",
                    "id": mid,
                    "result": {
                        "content": [{"type": "text", "text": json.dumps({"ok": True, "schemaVersion": "2026.10.19-1"})}]
                    },
                }
            return {
                "jsonrpc": "2.0",
                "id": mid,
                "result": {"content": [{"type": "text", "text": json.dumps({"ok": True, "screen": self.screen})}]},
            }
        return {"jsonrpc": "2.0", "id": mid, "error": {"code": -32601, "message": "method not found"}}

    def __enter__(self):
        self.thread.start()
        return self

    def __exit__(self, *exc):
        self.httpd.shutdown()
        self.httpd.server_close()
