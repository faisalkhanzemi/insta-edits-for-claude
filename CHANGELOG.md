# Changelog

All notable changes to this project are documented here. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses [Semantic Versioning](https://semver.org/).

## [0.1.0] - 2026-11-07

### Added
- Stdio MCP bridge to the Edits for Mac automation server (Streamable HTTP), standard library only, Python 3.9+.
- Tool-set sync: Edits declares `tools.listChanged` but never sends it, so the bridge re-lists tools after every call and sends `notifications/tools/list_changed` when Edits moves between home (32 tools) and the editor (274 tools). `serve --no-sync` turns it off.
- Reply normalisation: drops `"resultType": "complete"` when Edits sends it without `ttlMs`/`cacheScope`, which some Claude Code builds rejected with `Invalid result for tools/list`.
- Forwarding of a server-to-client notification stream if Edits ever offers one (`serve --no-stream` turns it off).
- Session and `MCP-Protocol-Version` header handling, JSON and event-stream replies, batch requests.
- Clear JSON-RPC errors when Edits is closed or the token is rejected; the token is never logged.
- `doctor` command (with `--json` for bug reports) and `set-token` (hidden prompt, file saved with 0600 permissions).
- Claude Code plugin with a keychain-stored token prompt, a marketplace manifest, and an `edits` skill with notes measured against Edits 454: sandboxed import folders, absolute paths, HDR projects, beat detection fallback, keyframe and export formats, and library music in automation exports.

[0.1.0]: https://github.com/faisalkhanzemi/insta-edits-for-claude/releases/tag/v0.1.0
