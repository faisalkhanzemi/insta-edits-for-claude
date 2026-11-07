"""Minimal MCP Streamable HTTP client for the Edits automation server (standard library only)."""

from __future__ import annotations

import json
import threading
import urllib.error
import urllib.request
from typing import Any, Callable, Iterable, Iterator, List, Optional

# Answers to the GET notification stream that mean "there is no stream", so don't retry.
# Edits 454 answers 403 even with a valid token and session (measured 7 Nov 2026); the spec says 405.
NO_STREAM = (403, 404, 405)


class EditsError(Exception):
    """The Edits server could not be used."""


class EditsUnreachable(EditsError):
    """Nothing answered at the server URL: Edits is closed or its automation server is off."""


class EditsHTTPError(EditsError):
    def __init__(self, status: int, body: str):
        super().__init__(f"HTTP {status}")
        self.status = status
        self.body = body


def iter_sse(lines: Iterable[str]) -> Iterator[Any]:
    """Yield decoded JSON payloads from server-sent-event lines."""
    data: List[str] = []
    for raw in lines:
        line = raw.rstrip("\r\n")
        if not line:
            if data:
                yield json.loads("\n".join(data))
                data = []
            continue
        if line.startswith(":"):
            continue
        field, _, value = line.partition(":")
        if field == "data":
            data.append(value[1:] if value.startswith(" ") else value)
    if data:
        yield json.loads("\n".join(data))


def _flatten(payload: Any) -> List[Any]:
    return list(payload) if isinstance(payload, list) else [payload]


class EditsClient:
    def __init__(self, url: str, token: Optional[str], timeout: float = 600.0):
        self.url = url
        self._token = token
        self.timeout = timeout
        self.session_id: Optional[str] = None
        self.protocol_version: Optional[str] = None

    def _headers(self, accept: str) -> dict:
        headers = {"Accept": accept}
        if self._token:
            headers["Authorization"] = "Bearer " + self._token
        if self.session_id:
            headers["Mcp-Session-Id"] = self.session_id
        if self.protocol_version:
            headers["MCP-Protocol-Version"] = self.protocol_version
        return headers

    def post(self, message: Any) -> List[Any]:
        """Send one JSON-RPC message (or a batch) and return every message the server sends back."""
        body = json.dumps(message).encode("utf-8")
        headers = self._headers("application/json, text/event-stream")
        headers["Content-Type"] = "application/json"
        request = urllib.request.Request(self.url, data=body, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                session = response.headers.get("Mcp-Session-Id")
                if session:
                    self.session_id = session
                ctype = (response.headers.get("Content-Type") or "").lower()
                text = response.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as err:
            raise EditsHTTPError(err.code, err.read().decode("utf-8", "replace")[:500]) from None
        except (urllib.error.URLError, ConnectionError, OSError) as err:
            raise EditsUnreachable(str(getattr(err, "reason", err))) from None
        if not text.strip():
            return []
        if "text/event-stream" in ctype:
            messages: List[Any] = []
            for payload in iter_sse(text.splitlines()):
                messages.extend(_flatten(payload))
        else:
            messages = _flatten(json.loads(text))
        self._remember_protocol(messages)
        return messages

    def _remember_protocol(self, messages: List[Any]) -> None:
        for msg in messages:
            result = msg.get("result") if isinstance(msg, dict) else None
            if isinstance(result, dict) and isinstance(result.get("protocolVersion"), str) and "serverInfo" in result:
                self.protocol_version = result["protocolVersion"]

    def stream_supported(self, timeout: float = 3.0) -> Optional[bool]:
        """True if the server offers a GET event stream, False if it refuses, None if unknown."""
        request = urllib.request.Request(self.url, headers=self._headers("text/event-stream"), method="GET")
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return response.status == 200
        except urllib.error.HTTPError as err:
            return False if err.code in NO_STREAM else None
        except Exception:
            return None

    def listen(self, on_message: Callable[[Any], None], stop: threading.Event, log: Callable[[str], None]) -> None:
        """Forward server-initiated messages (such as tools/list_changed) until stopped.

        Reconnects with backoff. Gives up quietly if the server has no GET stream.
        """
        delay = 1.0
        while not stop.is_set():
            request = urllib.request.Request(self.url, headers=self._headers("text/event-stream"), method="GET")
            try:
                with urllib.request.urlopen(request, timeout=None) as response:
                    delay = 1.0
                    lines = (raw.decode("utf-8", "replace") for raw in response)
                    for payload in iter_sse(lines):
                        for msg in _flatten(payload):
                            on_message(msg)
                        if stop.is_set():
                            return
            except urllib.error.HTTPError as err:
                if err.code in NO_STREAM:
                    log(f"Edits has no notification stream (HTTP {err.code}); the bridge checks the tools itself")
                    return
                log(f"notification stream error HTTP {err.code}; retrying")
            except Exception as err:  # connection dropped, Edits restarted, etc.
                if stop.is_set():
                    return
                log(f"notification stream closed ({err}); retrying")
            stop.wait(delay)
            delay = min(delay * 2, 30.0)
