import plistlib

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
        speed = next(c for c in report.checks if c.name == "Speed-curve catalog")
        assert "the bridge points it at setSpeedCurve" in speed.detail
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


def test_doctor_shows_the_edits_version(monkeypatch, tmp_path):
    app = tmp_path / "Edits.app"
    (app / "Contents").mkdir(parents=True)
    with open(app / "Contents" / "Info.plist", "wb") as f:
        plistlib.dump({"CFBundleShortVersionString": "455.0.0"}, f)
    monkeypatch.setenv(config.ENV_URL, "http://127.0.0.1:9/mcp")
    monkeypatch.setattr(doctor.platform, "system", lambda: "Darwin")
    monkeypatch.setattr(doctor, "_edits_app", lambda: str(app))
    report = doctor.run_doctor()
    installed = next(c for c in report.checks if c.name == "Edits app installed")
    assert installed.status == "ok" and installed.detail == f"455.0.0 at {app}"


def test_doctor_still_passes_when_the_version_is_unreadable(tmp_path):
    assert doctor._app_version(str(tmp_path / "Missing.app")) is None
