"""End-to-end: run the real bridge process against the fake Edits server, speak MCP over stdio."""

import json
import os
import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest

from fake_edits import TOKEN, FakeEdits

SRC = str(Path(__file__).resolve().parents[1] / "src")

INIT = {
    "jsonrpc": "2.0",
    "id": 1,
    "method": "initialize",
    "params": {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "test", "version": "0"}},
}
INITIALIZED = {"jsonrpc": "2.0", "method": "notifications/initialized"}


class BridgeProcess:
    def __init__(self, url, token=TOKEN, extra_args=()):
        env = dict(os.environ, PYTHONPATH=SRC, EDITS_MCP_URL=url, EDITS_MCP_TOKEN_FILE="/nonexistent")
        env.pop("EDITS_MCP_TOKEN", None)
        if token:
            env["EDITS_MCP_TOKEN"] = token
        self.proc = subprocess.Popen(
            [sys.executable, "-m", "insta_edits", "serve", *extra_args],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=env,
        )
        self.lines = []
        self._reader = threading.Thread(target=self._read, daemon=True)
        self._reader.start()

    def _read(self):
        for line in self.proc.stdout:
            self.lines.append(json.loads(line))

    def send(self, msg):
        self.proc.stdin.write(json.dumps(msg) + "\n")
        self.proc.stdin.flush()

    def wait_for(self, predicate, timeout=10):
        end = time.time() + timeout
        while time.time() < end:
            for m in self.lines:
                if predicate(m):
                    return m
            time.sleep(0.02)
        raise AssertionError(f"no matching message; got {self.lines}")

    def close(self):
        self.proc.stdin.close()
        self.proc.wait(timeout=10)
        return self.proc.stderr.read()


@pytest.mark.parametrize("sse", [False, True], ids=["json-replies", "sse-replies"])
def test_tools_list_is_normalised_and_session_is_kept(sse):
    with FakeEdits(sse_replies=sse) as edits:
        b = BridgeProcess(edits.url)
        b.send(INIT)
        init = b.wait_for(lambda m: m.get("id") == 1)
        assert init["result"]["serverInfo"]["name"] == "metapilot-native"
        b.send(INITIALIZED)
        b.send({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
        tools = b.wait_for(lambda m: m.get("id") == 2)
        assert "resultType" not in tools["result"]
        assert [t["name"] for t in tools["result"]["tools"]] == ["appState", "openProject", "getCapabilities"]
        b.close()
        later = [r for r in edits.received if r["msg"].get("method") != "initialize"]
        assert all(r["session"] == edits.session for r in later), "session id must be sent after initialize"
        assert all(r["protocol"] == "2025-06-18" for r in later), (
            "protocol version header must be sent after initialize"
        )


def _open_project_and_expect_list_changed(b):
    b.send(INIT)
    b.wait_for(lambda m: m.get("id") == 1)
    b.send(INITIALIZED)
    b.send({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
    b.wait_for(lambda m: m.get("id") == 2)
    b.send({"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "appState", "arguments": {}}})
    b.wait_for(lambda m: m.get("id") == 3)
    b.send(
        {
            "jsonrpc": "2.0",
            "id": 4,
            "method": "tools/call",
            "params": {"name": "openProject", "arguments": {"name": "demo"}},
        }
    )
    b.wait_for(lambda m: m.get("id") == 4)
    return b.wait_for(lambda m: m.get("method") == "notifications/tools/list_changed")


def test_bridge_announces_tool_changes_that_edits_never_sends():
    with FakeEdits() as edits:  # like the real Edits: no stream, no notification
        b = BridgeProcess(edits.url)
        _open_project_and_expect_list_changed(b)
        changes = [m for m in b.lines if m.get("method") == "notifications/tools/list_changed"]
        assert len(changes) == 1, "a call that doesn't change the screen must not trigger a notification"
        b.send({"jsonrpc": "2.0", "id": 5, "method": "tools/list"})
        tools = b.wait_for(lambda m: m.get("id") == 5)
        assert "addText" in [t["name"] for t in tools["result"]["tools"]]
        internal = [r for r in edits.received if str(r["msg"].get("id", "")).startswith("insta-edits:")]
        assert internal, "the bridge checks the tool list itself"
        assert not any(str(m.get("id", "")).startswith("insta-edits:") for m in b.lines), (
            "internal replies stay internal"
        )
        b.close()


def test_no_sync_flag_turns_the_check_off():
    with FakeEdits() as edits:
        b = BridgeProcess(edits.url, extra_args=("--no-sync",))
        b.send(INIT)
        b.wait_for(lambda m: m.get("id") == 1)
        b.send({"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {"name": "openProject", "arguments": {}}})
        b.wait_for(lambda m: m.get("id") == 2)
        time.sleep(0.3)
        assert not any(m.get("method") == "notifications/tools/list_changed" for m in b.lines)
        b.close()


def test_tool_list_change_is_forwarded_from_a_stream_when_offered():
    with FakeEdits(stream=True) as edits:
        b = BridgeProcess(edits.url)
        b.send(INIT)
        b.wait_for(lambda m: m.get("id") == 1)
        b.send(INITIALIZED)
        time.sleep(0.3)  # let the notification stream connect
        b.send(
            {
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {"name": "openProject", "arguments": {"name": "demo"}},
            }
        )
        b.wait_for(lambda m: m.get("method") == "notifications/tools/list_changed")
        b.send({"jsonrpc": "2.0", "id": 4, "method": "tools/list"})
        tools = b.wait_for(lambda m: m.get("id") == 4)
        assert "addText" in [t["name"] for t in tools["result"]["tools"]]
        b.close()


def test_no_stream_is_fine():
    with FakeEdits(stream=False) as edits:
        b = BridgeProcess(edits.url)
        b.send(INIT)
        b.wait_for(lambda m: m.get("id") == 1)
        b.send({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
        assert b.wait_for(lambda m: m.get("id") == 2)["result"]["tools"]
        b.close()


def test_bad_token_becomes_a_clear_jsonrpc_error():
    with FakeEdits() as edits:
        b = BridgeProcess(edits.url, token="wrong")
        b.send(INIT)
        err = b.wait_for(lambda m: m.get("id") == 1)
        assert err["error"]["code"] == -32002
        assert "HTTP 403" in err["error"]["message"] and "set-token" in err["error"]["message"]
        assert "wrong" not in b.close(), "the token must never be logged"


def test_batch_requests_are_split():
    with FakeEdits() as edits:
        b = BridgeProcess(edits.url)
        b.send([INIT, {"jsonrpc": "2.0", "id": 2, "method": "tools/list"}])
        b.wait_for(lambda m: m.get("id") == 1)
        assert "cacheScope" not in b.wait_for(lambda m: m.get("id") == 2)["result"]
        b.close()


def _free_port():
    import socket

    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def test_starts_without_edits_and_picks_it_up_when_it_appears(monkeypatch):
    port = _free_port()
    monkeypatch.setenv("INSTA_EDITS_OFFLINE_POLL", "0.2")
    b = BridgeProcess(f"http://127.0.0.1:{port}/mcp")
    b.send(INIT)
    init = b.wait_for(lambda m: m.get("id") == 1)
    assert init["result"]["serverInfo"]["name"] == "insta-edits"
    assert init["result"]["capabilities"]["tools"]["listChanged"] is True
    assert "isn't reachable" in init["result"]["instructions"]
    b.send(INITIALIZED)
    b.send({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
    assert b.wait_for(lambda m: m.get("id") == 2)["result"] == {"tools": []}
    b.send({"jsonrpc": "2.0", "id": 3, "method": "ping"})
    assert b.wait_for(lambda m: m.get("id") == 3)["result"] == {}

    with FakeEdits(port=port) as edits:
        b.wait_for(lambda m: m.get("method") == "notifications/tools/list_changed", timeout=10)
        b.send({"jsonrpc": "2.0", "id": 4, "method": "tools/list"})
        tools = b.wait_for(lambda m: m.get("id") == 4)["result"]["tools"]
        assert {t["name"] for t in tools} >= {"appState", "openProject"}
        assert any(r["msg"].get("method") == "initialize" for r in edits.received)
        b.close()


def test_calls_still_explain_what_to_do_while_edits_is_closed():
    port = _free_port()
    b = BridgeProcess(f"http://127.0.0.1:{port}/mcp")
    b.send(INIT)
    b.wait_for(lambda m: m.get("id") == 1)
    b.send({"jsonrpc": "2.0", "id": 5, "method": "tools/call", "params": {"name": "appState", "arguments": {}}})
    err = b.wait_for(lambda m: m.get("id") == 5)["error"]
    assert err["code"] == -32001
    assert "Enable Automation Server" in err["message"]
    b.close()
