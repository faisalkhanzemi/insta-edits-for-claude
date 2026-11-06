# Insta Edits for Claude

**Let Claude Code edit in Instagram Edits for Mac, with the full editor and not just the home screen.**

[![CI](https://github.com/faisalkhanzemi/insta-edits-for-claude/actions/workflows/ci.yml/badge.svg)](https://github.com/faisalkhanzemi/insta-edits-for-claude/actions/workflows/ci.yml)
![Python 3.9+](https://img.shields.io/badge/python-3.9%2B-blue)
![Dependencies: none](https://img.shields.io/badge/dependencies-none-brightgreen)
[![License: MIT](https://img.shields.io/badge/license-MIT-lightgrey)](LICENSE)

<p align="center"><a href="assets/hero.mp4"><img src="assets/hero.gif" alt="A real Claude Code session making a beat-synced Dubai in 15 seconds reel inside Instagram Edits for Mac: clips cut on the beat, punch-in zooms, a speed ramp, a title and labels, frame checks, then export" width="100%"></a></p>

<p align="center"><sub>One prompt, a real Claude Code session, nothing scripted. Edits found no beats, so Claude analysed the music itself (122 BPM), cut every clip on a beat, checked its own frames and exported the reel. <a href="assets/hero.mp4">Watch with sound</a>.</sub></p>

Edits for Mac, which Meta launched on 5 November 2026, has a built-in automation server that speaks MCP: in Meta's words, you can connect AI agents "to the desktop editor through MCP so they can help with your projects". You can point Claude Code at it directly, but you only get part of it.

Edits changes its tools with the screen. The home screen offers **32 tools**: projects, imports and catalogs. Open a project and it offers **274**, with text, captions, effects, transitions, keyframes, audio and export. Edits says it will announce that change (`tools.listChanged: true`) but never sends the notification. Claude keeps the 32 home tools for the whole session and never sees the editor.

This bridge sits between the two. After every tool call it asks Edits which tools it offers now. If the set has changed, it tells Claude, and Claude refreshes the list. It also fixes a reply format that some Claude Code builds reject, gives readable errors, and keeps your token out of config files.

```
Claude Code ──stdio──▶ insta-edits ──HTTP──▶ Edits for Mac (127.0.0.1:19501)
             ◀── tools/list_changed ──┘  checks the tool set after each call
```

## What you get

- **The full editor.** Claude receives `notifications/tools/list_changed` as soon as Edits moves between home (32 tools) and the editor (274). Without the bridge, that notification never arrives.
- **Replies that every Claude Code build accepts.** Edits marks each result `"resultType": "complete"` without the caching fields that newer MCP schemas pair with it. Some Claude Code builds then dropped every tool, with `Invalid result for tools/list: ttlMs … cacheScope`. The bridge removes the marker only when those fields are missing.
- **Your token stays private.** The plugin keeps it in the macOS keychain. The CLI keeps it in a `0600` file. It never appears in `~/.claude.json`, in logs or in error messages.
- **Errors you can act on.** "Cannot reach Edits: open it and enable the Automation Server" replaces a stack trace. A rejected token says how to update it.
- **`doctor` checks every link** from the app to the sign-in, and `--json` gives you a report to attach to a bug.
- **An `edits` skill** that teaches Claude how the server behaves: discover before guessing, work in normalised canvas coordinates, check rendered frames, and **never publish without your explicit go-ahead**.
- **Python standard library only.** Nothing to `pip install` for the plugin, and it runs on the `python3` that comes with macOS.

## Requirements

- A Mac with Apple silicon (M1 or later) and [Edits for Mac](https://edits.instagram.com/desktop), free and signed in to Instagram
- Claude Code
- `python3` 3.9 or newer. Run `xcode-select --install` if macOS asks for the command line tools.

## Install

### 1. Turn on the automation server in Edits

Go to **Edits › Settings › Automation**, switch on **Enable Automation Server**, and copy the **Access token**. Keep Edits open while Claude works.

### 2a. As a Claude Code plugin (recommended)

Start `claude` in a terminal and type:

```
/plugin marketplace add faisalkhanzemi/insta-edits-for-claude
/plugin install insta-edits@insta-edits
```

Claude Code asks for the access token with a masked prompt and stores it in your keychain. Restart Claude Code, then run `/mcp`: `edits` should show as connected. The plugin also installs the `edits` skill.

<details>
<summary>Installing from a shell script, or using the Claude desktop app</summary>

The shell commands do the same thing but don't prompt for the token, so set it afterwards with `/plugin configure insta-edits@insta-edits` inside Claude Code:

```bash
claude plugin marketplace add faisalkhanzemi/insta-edits-for-claude
```

```bash
claude plugin install insta-edits@insta-edits
```

A plugin installed this way, at user scope, also shows up in the Code tab of the Claude desktop app, which reads the same settings.
</details>

### 2b. As a standalone MCP server

```bash
pipx install git+https://github.com/faisalkhanzemi/insta-edits-for-claude
```

```bash
insta-edits set-token
```

```bash
claude mcp add --scope user edits -- insta-edits serve
```

`set-token` asks for the token with a hidden prompt and saves it to `~/.config/insta-edits/token` with `0600` permissions. Never put the token itself on the `claude mcp add` line: it would end up in plain text in `~/.claude.json` and in your shell history.

## Check the connection

```bash
insta-edits doctor
```

```
insta-edits 0.1.0 doctor

  ✓ macOS                      27.0.1
  ✓ Edits app installed        /Applications/Edits.app
  ✓ Automation server          answering at http://127.0.0.1:19501/mcp (HTTP 403 without a token, as expected)
  ✓ Access token               from ~/.config/insta-edits/token
  ✓ Sign-in                    metapilot-native 1.0.0, protocol 2025-06-18
  ✓ Tools                      32 on the current screen (Edits offers more once a project is open)
  ✓ Reply format               normalised for older Claude Code builds (resultType without caching fields)
  ✓ Edits automation schema    2026.10.19-1
  ✓ Tool-change notifications  Edits announces them but never sends any; the bridge checks after each call and tells Claude

All good. Claude can drive Edits.
```

Each `✗` line names its fix. Plugin users who want `doctor` can install the CLI as in 2b. The plugin token lives in the keychain, so without `set-token` the doctor checks stop at the sign-in step.

## Using it

Ask for edits in plain words:

> Open my latest Edits project and tell me what's on the timeline.

> Import `~/Movies/broll/` into a new project, cut it to the beat of the voice-over, and add word-by-word captions in a clean sans.

> Add a soft zoom on every product close-up and a whoosh on each cut, then render a preview so I can check the frames.

Claude opens the project, the editor tools appear, and it works from them. It doesn't post. Publishing stays in the Edits window unless you explicitly tell Claude to share a specific video.

## How it works

| Step | What happens |
| --- | --- |
| Session | The bridge forwards `initialize`, keeps Edits' `Mcp-Session-Id`, and sends `MCP-Protocol-Version` on every request. |
| Replies | It accepts both JSON and `text/event-stream` replies and batch requests, and normalises `resultType` only when the caching fields are missing. |
| Tool sync | After each `tools/call` it sends its own `tools/list` to Edits, using an id Claude never sees, and compares the tool names. If they changed, it writes `notifications/tools/list_changed` to Claude. Turn this off with `serve --no-sync`. |
| Notifications | If a future Edits build opens a server-to-client stream, the bridge listens on it and forwards what arrives. Edits doesn't offer one today, so the bridge stops trying after the first refusal. Turn it off with `serve --no-stream`. |
| Errors | When Edits is closed the bridge returns JSON-RPC `-32001`. When Edits returns an HTTP error it returns `-32002`. Both carry a one-line fix. |

Settings come from the environment: `EDITS_MCP_URL` (default `http://127.0.0.1:19501/mcp`), `EDITS_MCP_TOKEN`, and `EDITS_MCP_TOKEN_FILE`. Logs go to stderr.

## Tested with

| | Version |
| --- | --- |
| Edits for Mac | 454.0.0 (server `metapilot-native` 1.0.0, automation schema 2026.10.19-1) |
| Claude Code | 2.1.296 |
| macOS | 27.0.1 |
| Python | 3.9.6 (system), 3.11, 3.13 in CI |

Edits updates often and its automation server is undocumented. If a new build breaks something, run `insta-edits doctor --json` and [open an issue](https://github.com/faisalkhanzemi/insta-edits-for-claude/issues/new/choose) with the output. It contains no token.

## Troubleshooting

| Symptom | Fix |
| --- | --- |
| `Cannot reach Edits` | Open Edits and switch on Settings › Automation › Enable Automation Server. |
| HTTP 401 or 403 | The token changed in Edits. Update it in `/plugin`, or run `insta-edits set-token`. |
| Only home tools, even with a project open | Check that `edits` in `/mcp` points to the bridge and not straight at `127.0.0.1:19501`, and that you didn't start it with `--no-sync`. |
| Import fails with `file not found: ~/…` | Edits doesn't expand `~`. Pass the full path, such as `/Users/you/Movies/clip.mp4`. |
| Import fails with `Sandbox bookmark unavailable` | Edits is sandboxed. In our tests it imported from `~/Movies` and refused `~/Downloads`, `~/Desktop`, temp folders and project folders. Move the footage into `~/Movies` and import it from there. |
| Exported video is silent where the song should be | Songs from Edits' music library come in as licensed tracks, and exports started through automation leave them out: the music bed was silent in every test, while our own audio files exported fine. Export or post from the Edits window when a library song matters. |
| `addSongToComposition` adds a different song | Passing a track id sometimes added another track. Passing the exact title added the right song in our test. |

## Security

- The bridge only connects to the URL you configure, which defaults to `127.0.0.1`. It sends nothing anywhere else and has no telemetry.
- The token is redacted in every log line, error message and `repr`. `doctor --json` reports where the token came from, never its value.
- Edits is signed in to your Instagram account. The bundled skill tells Claude never to publish, share or schedule without your explicit go-ahead for that specific post.
- Report vulnerabilities privately as described in [SECURITY.md](SECURITY.md).

## FAQ

**Is this official?** No. It's an independent open-source project, not affiliated with or endorsed by Meta, Instagram or Anthropic. "Instagram" and "Edits" are trademarks of Meta Platforms, Inc.

**Does it work on Windows or with the Edits phone app?** No. Edits on desktop is only available on macOS, and the automation server only exists there.

**Do I still need this if my Claude Code build accepts Edits' replies?** Yes, for the editor tools. Edits never announces that its tools changed, and no client can find that out without asking.

**Can Claude post to Instagram for me?** The bridge won't stop Claude from calling Edits' share tools, but the bundled skill tells it to wait for your explicit go-ahead. Posting from the Edits window is the safer default.

## Development

```bash
git clone https://github.com/faisalkhanzemi/insta-edits-for-claude && cd insta-edits-for-claude
python3 -m venv .venv && . .venv/bin/activate
pip install -e . pytest ruff
pytest && ruff check . && ruff format --check .
```

The tests run against `tests/fake_edits.py`, a stand-in that behaves like the real server: it sends no notifications, changes its tool set when a project opens, and replies with `resultType`. You don't need a Mac or Edits to run them. See [CONTRIBUTING.md](CONTRIBUTING.md).

## Acknowledgements

Demo footage: stock clips from [Pexels](https://www.pexels.com/license/) (Pexels License). Music: "Tech House vibes" by Alejandro Magaña, [Mixkit](https://mixkit.co/license/) (Mixkit License).

Thanks to [iamjeeth/claude-edits-skill](https://github.com/iamjeeth/claude-edits-skill) for the early field notes on Edits' automation server.

## License

[MIT](LICENSE) © Faisal Khan
