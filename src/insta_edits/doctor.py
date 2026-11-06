"""`insta-edits doctor`: check every link between Claude and Edits, one line per check."""

from __future__ import annotations

import json
import platform
import shutil
import subprocess
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import List, Optional

from . import __version__, compat, config
from .transport import EditsClient, EditsHTTPError, EditsUnreachable

BUNDLE_ID = "com.burbn.basel.mac"


@dataclass
class Check:
    name: str
    status: str  # "ok" | "warn" | "fail" | "skip"
    detail: str = ""


@dataclass
class Report:
    version: str = __version__
    checks: List[Check] = field(default_factory=list)

    def add(self, name: str, status: str, detail: str = "") -> Check:
        check = Check(name, status, detail)
        self.checks.append(check)
        return check

    @property
    def ok(self) -> bool:
        return all(c.status in ("ok", "warn", "skip") for c in self.checks)


def _edits_app() -> Optional[str]:
    for path in ("/Applications/Edits.app", str(Path("~/Applications/Edits.app").expanduser())):
        if Path(path).exists():
            return path
    if shutil.which("mdfind"):
        out = subprocess.run(
            ["mdfind", f"kMDItemCFBundleIdentifier == '{BUNDLE_ID}'"], capture_output=True, text=True, timeout=10
        ).stdout.strip()
        if out:
            return out.splitlines()[0]
    return None


def run_doctor() -> Report:
    report = Report()
    url = config.server_url()

    if platform.system() == "Darwin":
        report.add("macOS", "ok", platform.mac_ver()[0] or platform.release())
    else:
        report.add("macOS", "warn", f"{platform.system()}: Edits for Mac only runs on macOS (Apple silicon)")

    app = _edits_app() if platform.system() == "Darwin" else None
    report.add("Edits app installed", "ok" if app else "fail", app or "not found; download it from edits.com/desktop")

    probe = EditsClient(url, token=None, timeout=5)
    try:
        probe.post({"jsonrpc": "2.0", "id": 0, "method": "ping"})
        report.add("Automation server", "ok", f"answering at {url}")
    except EditsHTTPError as err:
        report.add("Automation server", "ok", f"answering at {url} (HTTP {err.status} without a token, as expected)")
    except EditsUnreachable:
        report.add(
            "Automation server", "fail", f"nothing at {url}. In Edits: Settings > Automation > Enable Automation Server"
        )
        return report

    token = config.load_token()
    if not token:
        report.add("Access token", "fail", f"not set. Run `insta-edits set-token` or set {config.ENV_TOKEN}")
        return report
    if token.source == "environment":
        report.add("Access token", "ok", "from the environment")
    else:
        private = config.token_file_is_private(Path(token.source))
        report.add(
            "Access token",
            "ok" if private else "warn",
            f"from {token.source}" + ("" if private else " (readable by other users: run chmod 600 on it)"),
        )

    client = EditsClient(url, token.value, timeout=15)
    try:
        replies = client.post(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2025-06-18",
                    "capabilities": {},
                    "clientInfo": {"name": "insta-edits-doctor", "version": __version__},
                },
            }
        )
    except EditsHTTPError as err:
        status = "fail"
        if err.status in (401, 403):
            detail = "token rejected: copy the current token from Edits > Settings > Automation and run set-token"
        else:
            detail = f"HTTP {err.status}"
        report.add("Sign-in", status, detail)
        return report
    init = next((r for r in replies if isinstance(r, dict) and r.get("id") == 1), {})
    announces_changes = bool(
        (((init.get("result") or {}).get("capabilities") or {}).get("tools") or {}).get("listChanged")
    )
    info = (init.get("result") or {}).get("serverInfo") or {}
    if "error" in init or not info:
        report.add("Sign-in", "fail", json.dumps(init.get("error") or init)[:200])
        return report
    report.add(
        "Sign-in", "ok", f"{info.get('name', '?')} {info.get('version', '')}, protocol {client.protocol_version}"
    )
    client.post({"jsonrpc": "2.0", "method": "notifications/initialized"})

    tools_reply = next(
        (r for r in client.post({"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}}) if r.get("id") == 2),
        {},
    )
    result = tools_reply.get("result") or {}
    tools = result.get("tools") or []
    in_editor = any(t.get("name") == "addText" for t in tools)
    where = "a project is open" if in_editor else "home screen; Edits offers more once a project is open"
    report.add("Tools", "ok" if tools else "warn", f"{len(tools)} on the current screen ({where})")
    report.add(
        "Reply format",
        "ok",
        "normalised for older Claude Code builds (resultType without caching fields)"
        if compat.needs_fix(result)
        else "standard; nothing to normalise",
    )

    names = {t.get("name") for t in tools if isinstance(t, dict)}
    if "getCapabilities" in names:
        caps = next(
            (
                r
                for r in client.post(
                    {
                        "jsonrpc": "2.0",
                        "id": 3,
                        "method": "tools/call",
                        "params": {"name": "getCapabilities", "arguments": {}},
                    }
                )
                if r.get("id") == 3
            ),
            {},
        )
        text = "".join(
            c.get("text", "") for c in ((caps.get("result") or {}).get("content") or []) if isinstance(c, dict)
        )
        try:
            schema = json.loads(text).get("schemaVersion")
        except (ValueError, AttributeError):
            schema = None
        if schema:
            report.add("Edits automation schema", "ok", str(schema))

    stream = client.stream_supported()
    if stream:
        report.add("Tool-change notifications", "ok", "Edits streams them; new tools appear as soon as a project opens")
    elif announces_changes:
        report.add(
            "Tool-change notifications",
            "ok",
            "Edits announces them but never sends any; the bridge checks after each call and tells Claude",
        )
    else:
        report.add("Tool-change notifications", "ok", "the bridge checks after each call and tells Claude")
    return report


MARK = {"ok": "✓", "warn": "!", "fail": "✗", "skip": "-"}


def render(report: Report) -> str:
    width = max(len(c.name) for c in report.checks) if report.checks else 0
    lines = [f"insta-edits {report.version} doctor", ""]
    for c in report.checks:
        lines.append(f"  {MARK[c.status]} {c.name.ljust(width)}  {c.detail}")
    lines.append("")
    lines.append("All good. Claude can drive Edits." if report.ok else "Fix the ✗ items above, then run doctor again.")
    return "\n".join(lines)


def as_json(report: Report) -> str:
    return json.dumps(asdict(report), indent=2)
