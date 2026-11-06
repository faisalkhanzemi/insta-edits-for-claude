"""Where the bridge finds the Edits server and its access token."""

from __future__ import annotations

import os
import stat
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

DEFAULT_URL = "http://127.0.0.1:19501/mcp"
DEFAULT_TOKEN_FILE = Path("~/.config/insta-edits/token").expanduser()

ENV_URL = "EDITS_MCP_URL"
ENV_TOKEN = "EDITS_MCP_TOKEN"
ENV_TOKEN_FILE = "EDITS_MCP_TOKEN_FILE"


@dataclass(frozen=True)
class Token:
    value: str
    source: str  # human-readable: "environment" or the file path

    def __repr__(self) -> str:  # never leak the secret in logs or tracebacks
        return f"Token(source={self.source!r}, value=<redacted>)"


def server_url() -> str:
    return os.environ.get(ENV_URL, DEFAULT_URL).strip() or DEFAULT_URL


def token_file() -> Path:
    raw = os.environ.get(ENV_TOKEN_FILE, "").strip()
    return Path(raw).expanduser() if raw else DEFAULT_TOKEN_FILE


def load_token() -> Optional[Token]:
    """Token from $EDITS_MCP_TOKEN, else from the token file. None when neither is set."""
    env = os.environ.get(ENV_TOKEN, "").strip()
    # Claude Code leaves an unresolved ${user_config...} literal when the option is unset.
    if env and not env.startswith("${"):
        return Token(env, "environment")
    path = token_file()
    try:
        value = path.read_text(encoding="utf-8").strip()
    except OSError:
        return None
    return Token(value, str(path)) if value else None


def token_file_is_private(path: Path) -> bool:
    """True when nobody but the owner can read the token file."""
    try:
        mode = path.stat().st_mode
    except OSError:
        return False
    return not (mode & (stat.S_IRWXG | stat.S_IRWXO))


def save_token(value: str, path: Optional[Path] = None) -> Path:
    """Write the token with 0600 permissions, creating a 0700 parent directory."""
    path = path or token_file()
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    fd = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        fh.write(value.strip())
    os.chmod(path, 0o600)
    return path
