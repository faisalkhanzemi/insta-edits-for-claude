# Security

## How the token is handled

- The Edits access token unlocks full control of the Edits app, which is signed in to an Instagram account. Treat it like a password.
- Installed as a Claude Code plugin, the token is entered in a masked prompt and kept in your system keychain.
- Installed manually, `insta-edits set-token` reads it from a hidden prompt and writes it to `~/.config/insta-edits/token` with `0600` permissions.
- The bridge never prints or logs the token, and `doctor --json` output contains no secrets, so it is safe to paste in an issue.
- The bridge only talks to the Edits server on your own machine (`127.0.0.1:19501` by default). It makes no other network requests and collects no telemetry.

If a token ends up somewhere public (a chat, a screenshot, a commit), regenerate it in Edits > Settings > Automation.

## Reporting a vulnerability

Please report security issues privately through GitHub's **Report a vulnerability** button on the repository's Security tab rather than in a public issue. You'll get a reply within a few days.
