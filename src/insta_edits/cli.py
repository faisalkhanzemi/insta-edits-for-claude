"""Command line: `insta-edits [serve|doctor|set-token|version]`."""

from __future__ import annotations

import argparse
import getpass
import sys
from typing import List, Optional

from . import __version__, config, doctor
from .bridge import serve
from .transport import EditsClient


def _log(message: str) -> None:
    """Diagnostics go to stderr, which MCP clients show in their server logs; stdout is the protocol."""
    sys.stderr.write(f"[insta-edits] {message}\n")
    sys.stderr.flush()


def cmd_serve(args: argparse.Namespace) -> int:
    token = config.load_token()
    if not token:
        _log(f"no access token: run `insta-edits set-token` or set {config.ENV_TOKEN}. Edits will refuse requests.")
    client = EditsClient(config.server_url(), token.value if token else None)
    return serve(client, log=_log, listen=not args.no_stream, sync_tools=not args.no_sync)


def cmd_doctor(args: argparse.Namespace) -> int:
    report = doctor.run_doctor()
    print(doctor.as_json(report) if args.json else doctor.render(report))
    return 0 if report.ok else 1


def cmd_set_token(args: argparse.Namespace) -> int:
    print("Paste the access token from Edits > Settings > Automation (input is hidden).")
    value = getpass.getpass("Token: ").strip()
    if not value:
        print("No token entered; nothing saved.", file=sys.stderr)
        return 1
    path = config.save_token(value)
    print(f"Saved to {path} (readable only by you).")
    print("Run `insta-edits doctor` to check the connection.")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="insta-edits",
        description="Connect Claude Code (or any MCP client) to Instagram Edits for Mac's automation server.",
    )
    parser.add_argument("--version", action="version", version=f"insta-edits {__version__}")
    sub = parser.add_subparsers(dest="command")

    p_serve = sub.add_parser("serve", help="run the stdio MCP bridge (default)")
    p_serve.add_argument("--no-stream", action="store_true", help="don't open the notification stream")
    p_serve.add_argument("--no-sync", action="store_true", help="don't check for tool-set changes after each call")
    p_serve.set_defaults(func=cmd_serve)

    p_doc = sub.add_parser("doctor", help="check the app, server, token and tools")
    p_doc.add_argument("--json", action="store_true", help="machine-readable output for bug reports (no secrets)")
    p_doc.set_defaults(func=cmd_doctor)

    p_tok = sub.add_parser("set-token", help="save the Edits access token to a private file")
    p_tok.set_defaults(func=cmd_set_token)
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not getattr(args, "func", None):
        args = parser.parse_args(["serve", *(argv or [])])
    return args.func(args)
