# Contributing

Thanks for helping. Edits for Mac ships weekly, so the most useful contributions are reports of what changed.

## Reporting a problem

Run this and paste the output in the issue (it contains no secrets):

```bash
insta-edits doctor --json
```

Include your Edits version (Edits > About Edits) and your Claude Code version (`claude --version`).

## Development

```bash
git clone https://github.com/faisalkhanzemi/insta-edits-for-claude
cd insta-edits-for-claude
python3 -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"
pytest
ruff check . && ruff format --check .
```

The tests run against `tests/fake_edits.py`, a stand-in server that mirrors what the real Edits server does, so you don't need Edits installed to run them. When Edits changes its behaviour, update the fake first, then the bridge.

Keep the bridge on the standard library only and compatible with Python 3.9 (the version macOS ships).
