from fake_edits import TOKEN, FakeEdits
from insta_edits import config, doctor


def _statuses(report):
    return {c.name: c.status for c in report.checks}


def test_doctor_all_good(monkeypatch, tmp_path):
    with FakeEdits() as edits:
        monkeypatch.setenv(config.ENV_URL, edits.url)
        monkeypatch.setenv(config.ENV_TOKEN, TOKEN)
        monkeypatch.setattr(doctor, "_edits_app", lambda: "/Applications/Edits.app")
        report = doctor.run_doctor()
        s = _statuses(report)
        assert s["Sign-in"] == "ok" and s["Tools"] == "ok"
        fmt = next(c for c in report.checks if c.name == "Reply format")
        assert "normalised" in fmt.detail
        notes = next(c for c in report.checks if c.name == "Tool-change notifications")
        assert "never sends" in notes.detail
        assert any(c.name == "Edits automation schema" and c.detail == "2026.10.19-1" for c in report.checks)
        assert TOKEN not in doctor.render(report) and TOKEN not in doctor.as_json(report)


def test_doctor_reports_server_off(monkeypatch):
    monkeypatch.setenv(config.ENV_URL, "http://127.0.0.1:9/mcp")
    monkeypatch.setattr(doctor, "_edits_app", lambda: "/Applications/Edits.app")
    report = doctor.run_doctor()
    assert _statuses(report)["Automation server"] == "fail"
    assert not report.ok


def test_doctor_reports_rejected_token(monkeypatch):
    with FakeEdits() as edits:
        monkeypatch.setenv(config.ENV_URL, edits.url)
        monkeypatch.setenv(config.ENV_TOKEN, "wrong")
        monkeypatch.setattr(doctor, "_edits_app", lambda: "/Applications/Edits.app")
        report = doctor.run_doctor()
        assert _statuses(report)["Sign-in"] == "fail"
        assert "set-token" in next(c.detail for c in report.checks if c.name == "Sign-in")
