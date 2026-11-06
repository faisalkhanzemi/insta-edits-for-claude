import stat

from insta_edits import config


def test_env_token_wins(monkeypatch, tmp_path):
    f = tmp_path / "token"
    f.write_text("from-file")
    monkeypatch.setenv(config.ENV_TOKEN_FILE, str(f))
    monkeypatch.setenv(config.ENV_TOKEN, "from-env")
    tok = config.load_token()
    assert tok.value == "from-env" and tok.source == "environment"


def test_unresolved_plugin_placeholder_is_ignored(monkeypatch, tmp_path):
    monkeypatch.setenv(config.ENV_TOKEN, "${user_config.edits_token}")
    monkeypatch.setenv(config.ENV_TOKEN_FILE, str(tmp_path / "missing"))
    assert config.load_token() is None


def test_file_token(monkeypatch, tmp_path):
    monkeypatch.delenv(config.ENV_TOKEN, raising=False)
    f = tmp_path / "token"
    f.write_text("  abc  \n")
    monkeypatch.setenv(config.ENV_TOKEN_FILE, str(f))
    assert config.load_token().value == "abc"


def test_save_token_is_private(tmp_path):
    path = config.save_token("secret", tmp_path / "dir" / "token")
    assert path.read_text() == "secret"
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    assert stat.S_IMODE(path.parent.stat().st_mode) == 0o700
    assert config.token_file_is_private(path)


def test_token_repr_is_redacted():
    assert "secret" not in repr(config.Token("secret", "environment"))


def test_url_override(monkeypatch):
    monkeypatch.setenv(config.ENV_URL, "http://127.0.0.1:9/mcp")
    assert config.server_url() == "http://127.0.0.1:9/mcp"
