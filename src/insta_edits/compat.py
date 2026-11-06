"""Normalise Edits replies that some MCP clients reject.

Edits for Mac (build 454, November 2026) marks every result `"resultType": "complete"` but does
not send the caching fields (`ttlMs`, `cacheScope`) that newer MCP schemas pair with it. Some
Claude Code builds rejected the whole tool list because of it:

    Invalid result for tools/list:
      "ttlMs"      expected number, received undefined
      "cacheScope" expected one of "public" | "private"

Claude Code 2.1.296 accepts the reply as is. For older clients the bridge drops `resultType`
when the caching fields are missing or malformed, and drops malformed caching fields. Everything
else passes through untouched.
"""

from __future__ import annotations

from typing import Any, Dict, List

VALID_CACHE_SCOPES = ("public", "private")


def cache_hint_problems(result: Any) -> List[str]:
    """Describe what is wrong with the caching hints in a result, if anything."""
    if not isinstance(result, dict):
        return []
    problems = []
    has_scope = "cacheScope" in result
    has_ttl = "ttlMs" in result
    if has_scope and result["cacheScope"] not in VALID_CACHE_SCOPES:
        problems.append(f"cacheScope={result['cacheScope']!r} (expected 'public' or 'private')")
    if has_ttl and not _is_number(result["ttlMs"]):
        problems.append(f"ttlMs={result['ttlMs']!r} (expected a number)")
    if has_scope and not has_ttl:
        problems.append("ttlMs missing while cacheScope is set")
    return problems


def needs_fix(result: Any) -> bool:
    if not isinstance(result, dict):
        return False
    if cache_hint_problems(result):
        return True
    # Only the plain "complete" marker; other result types (such as async tasks) pass through.
    return result.get("resultType") == "complete" and not ("ttlMs" in result and "cacheScope" in result)


def fix_message(message: Any) -> Any:
    """Return the JSON-RPC message with an unsupported resultType and malformed caching hints removed."""
    if not isinstance(message, dict):
        return message
    result = message.get("result")
    if not needs_fix(result):
        return message
    drop = {"resultType"} if result.get("resultType") == "complete" else set()
    if cache_hint_problems(result):
        drop |= {"cacheScope", "ttlMs"}
    cleaned: Dict[str, Any] = {k: v for k, v in result.items() if k not in drop}
    message = dict(message)
    message["result"] = cleaned
    return message


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)
