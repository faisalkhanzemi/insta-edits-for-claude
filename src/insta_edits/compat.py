"""Normalise Edits replies that some MCP clients reject.

Edits for Mac (build 454, November 2026) marks every result `"resultType": "complete"` but does
not send the caching fields (`ttlMs`, `cacheScope`) that newer MCP schemas pair with it. Some
Claude Code builds rejected the whole tool list because of it:

    Invalid result for tools/list:
      "ttlMs"      expected number, received undefined
      "cacheScope" expected one of "public" | "private"

Claude Code 2.1.296 accepts the reply as is. For older clients the bridge drops `resultType`
when the caching fields are missing or malformed, and drops malformed caching fields.

Edits' catalog (`getCapabilities`, `listCatalogKinds`, `getCatalogItem`, `listCatalog`) names
`selectSpeedPanelPreset` as the tool for speed-curve presets, but that tool's own description says
it is deprecated, refused and crashed the app; `setSpeedCurve` takes the same `preset` value and
works (tested on Edits 455, 10 Nov 2026). The bridge points those catalog entries at
`setSpeedCurve`. Everything else passes through untouched.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Tuple

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


SPEED_KIND = "speedCurvePreset"
BROKEN_SPEED_TOOL = "selectSpeedPanelPreset"
WORKING_SPEED_TOOL = "setSpeedCurve"


def _point_speed_catalog(value: Any) -> Tuple[Any, bool]:
    """Copy of value with speed-curve catalog entries pointed at setSpeedCurve, and whether anything changed."""
    if isinstance(value, dict):
        changed = False
        out: Dict[str, Any] = {}
        for key, item in value.items():
            out[key], item_changed = _point_speed_catalog(item)
            changed = changed or item_changed
        if out.get("kind") == SPEED_KIND and out.get("applyTool") == BROKEN_SPEED_TOOL:
            out["applyTool"] = WORKING_SPEED_TOOL
            changed = True
        return out, changed
    if isinstance(value, list):
        items = [_point_speed_catalog(item) for item in value]
        return [item for item, _ in items], any(c for _, c in items)
    return value, False


def fix_speed_catalog(message: Any) -> Any:
    """Point speed-curve catalog entries in a tool result at setSpeedCurve; anything else is returned as is."""
    if not isinstance(message, dict) or not isinstance(message.get("result"), dict):
        return message
    result = message["result"]
    new_result = dict(result)
    changed = False
    content = result.get("content")
    if isinstance(content, list):
        new_content = []
        for block in content:
            text = block.get("text") if isinstance(block, dict) else None
            if isinstance(text, str) and BROKEN_SPEED_TOOL in text:
                try:
                    data = json.loads(text)
                except ValueError:
                    data = None
                if data is not None:
                    data, block_changed = _point_speed_catalog(data)
                    if block_changed:
                        block = dict(block, text=json.dumps(data, indent=2, ensure_ascii=False))
                        changed = True
            new_content.append(block)
        new_result["content"] = new_content
    if "structuredContent" in result:
        new_result["structuredContent"], structured_changed = _point_speed_catalog(result["structuredContent"])
        changed = changed or structured_changed
    if not changed:
        return message
    message = dict(message)
    message["result"] = new_result
    return message


def fix_message(message: Any) -> Any:
    """Return the JSON-RPC message with an unsupported resultType and malformed caching hints removed,
    and speed-curve catalog entries pointed at setSpeedCurve."""
    message = fix_speed_catalog(message)
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
