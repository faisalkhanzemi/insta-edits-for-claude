# Changelog

All notable changes to this project are documented here. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Fixed
- The bridge no longer retries Edits' notification stream forever. Edits answers the stream request with 403 even with a valid token (measured on 7 Nov 2026; the spec suggests 405), so 403 now means "no stream", like 404 and 405. Before, the bridge asked again every 30 seconds for the whole session. Tool changes were never affected, because the bridge checks the tools itself.

### Tests
- The fake Edits server answers the stream request with 403, the way the real app does, and a new test checks the bridge asks only once.

### Documentation
- Install: each `/plugin` command in its own copy box, a "before you start" line, and a plain-English install request for people who'd rather ask Claude.
- New "Update or uninstall" section.
- The `doctor` example shows the current version.

## [0.1.1] - 2026-11-07

### Added
- Start in any order: if Edits isn't reachable when the client initializes, the bridge answers `initialize` itself, reports no tools, retries Edits in the background (every 5 s, `INSTA_EDITS_OFFLINE_POLL`) and sends `notifications/tools/list_changed` once Edits answers. Directories that start the server to list its tools, such as Glama, now work without Edits.

### Changed
- `doctor` says when a project is open instead of promising more tools.

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

[0.1.1]: https://github.com/faisalkhanzemi/insta-edits-for-claude/releases/tag/v0.1.1
[0.1.0]: https://github.com/faisalkhanzemi/insta-edits-for-claude/releases/tag/v0.1.0
