"""Stdio <-> Streamable HTTP bridge between an MCP client and the Edits automation server.

Edits swaps its whole tool set with the screen (about 30 tools at home, about 270 in the editor) and
declares `tools.listChanged`, but never sends the notification. MCP clients such as Claude Code only
re-read the tool list when told, so they stay on the home-screen tools. After every tool call the
bridge re-reads the list itself and sends `notifications/tools/list_changed` when it differs.
"""

from __future__ import annotations

import json
import sys
import threading
from typing import Any, Callable, Optional, TextIO

from . import compat
from .transport import EditsClient, EditsHTTPError, EditsUnreachable

HINT_UNREACHABLE = "Open Edits and turn on Settings > Automation > Enable Automation Server."
HINT_AUTH = (
    "The access token was rejected. Copy the current one from Edits > Settings > Automation "
    "and update it (run: insta-edits set-token)."
)


class Writer:
    """Thread-safe line writer: client replies and stream notifications share stdout."""

    def __init__(self, stream: TextIO):
        self._stream = stream
        self._lock = threading.Lock()

    def write(self, message: Any) -> None:
        line = json.dumps(compat.fix_message(message), ensure_ascii=False)
        with self._lock:
            self._stream.write(line + "\n")
            self._stream.flush()


def _error_for(message: Any, code: int, text: str) -> Optional[dict]:
    if isinstance(message, dict) and "id" in message and "method" in message:
        return {"jsonrpc": "2.0", "id": message["id"], "error": {"code": code, "message": text}}
    return None


def _describe_http_error(err: EditsHTTPError) -> str:
    if err.status in (401, 403):
        return f"Edits refused the request (HTTP {err.status}). {HINT_AUTH}"
    return f"Edits returned HTTP {err.status}: {err.body[:200]}"


LIST_CHANGED = {"jsonrpc": "2.0", "method": "notifications/tools/list_changed"}


def _tool_names(result: Any) -> Optional[frozenset]:
    if not isinstance(result, dict) or not isinstance(result.get("tools"), list) or result.get("nextCursor"):
        return None
    return frozenset(t.get("name") for t in result["tools"] if isinstance(t, dict))


class ToolSync:
    """Tells the client when Edits' tool set changed, because Edits itself never does."""

    def __init__(self, client: EditsClient, log: Callable[[str], None]):
        self._client = client
        self._log = log
        self._known: Optional[frozenset] = None
        self._n = 0

    def seen(self, result: Any) -> None:
        names = _tool_names(result)
        if names is not None:
            self._known = names

    def changed_after_call(self) -> bool:
        self._n += 1
        rid = f"insta-edits:tools:{self._n}"
        try:
            replies = self._client.post({"jsonrpc": "2.0", "id": rid, "method": "tools/list", "params": {}})
        except Exception as err:  # never let the sync check break the real call
            self._log(f"tool sync skipped: {err}")
            return False
        reply = next((r for r in replies if isinstance(r, dict) and r.get("id") == rid), None)
        names = _tool_names(reply.get("result")) if reply else None
        if names is None:
            return False
        before, self._known = self._known, names
        return before is not None and names != before


def serve(
    client: EditsClient,
    stdin: TextIO = sys.stdin,
    stdout: TextIO = sys.stdout,
    log: Callable[[str], None] = lambda msg: None,
    listen: bool = True,
    sync_tools: bool = True,
) -> int:
    writer = Writer(stdout)
    stop = threading.Event()
    listener: Optional[threading.Thread] = None
    sync = ToolSync(client, log) if sync_tools else None

    for raw in stdin:
        raw = raw.strip()
        if not raw:
            continue
        try:
            incoming = json.loads(raw)
        except json.JSONDecodeError:
            log("ignored a line that is not JSON")
            continue
        messages = incoming if isinstance(incoming, list) else [incoming]
        for message in messages:
            try:
                replies = client.post(message)
            except EditsUnreachable as err:
                log(f"cannot reach Edits at {client.url}: {err}")
                reply = _error_for(message, -32001, f"Cannot reach Edits at {client.url}. {HINT_UNREACHABLE}")
                if reply:
                    writer.write(reply)
                continue
            except EditsHTTPError as err:
                log(_describe_http_error(err))
                reply = _error_for(message, -32002, _describe_http_error(err))
                if reply:
                    writer.write(reply)
                continue
            method = message.get("method") if isinstance(message, dict) else None
            for reply in replies:
                if sync and method == "tools/list" and isinstance(reply, dict):
                    sync.seen(reply.get("result"))
                writer.write(reply)
            if sync and method == "tools/call" and sync.changed_after_call():
                log("Edits changed its tool set; notifying the client")
                writer.write(LIST_CHANGED)
            if (
                listen
                and listener is None
                and isinstance(message, dict)
                and message.get("method") == "initialize"
                and client.session_id
            ):
                listener = threading.Thread(
                    target=client.listen, args=(writer.write, stop, log), name="edits-notifications", daemon=True
                )
                listener.start()

    stop.set()
    return 0
