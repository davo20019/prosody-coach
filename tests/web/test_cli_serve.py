from typer.testing import CliRunner


def test_serve_command_invokes_uvicorn(monkeypatch):
    captured = {}

    def fake_run(target, **kwargs):
        captured["target"] = target
        captured.update(kwargs)
    monkeypatch.setattr("uvicorn.run", fake_run)
    monkeypatch.setattr("webbrowser.open", lambda url: captured.setdefault("url", url))

    from main import app
    runner = CliRunner()
    result = runner.invoke(app, ["serve", "--no-browser", "--port", "7777"])
    assert result.exit_code == 0
    assert captured["target"] == "web.app:create_app"
    assert captured["port"] == 7777
    assert captured["host"] == "127.0.0.1"   # hardcoded, not exposed as a flag
    assert captured["factory"] is True
    assert "url" not in captured  # --no-browser respected


def test_serve_does_not_expose_host_flag():
    """Spec: bind to 127.0.0.1 only. There must be no --host option."""
    from main import app
    runner = CliRunner()
    result = runner.invoke(app, ["serve", "--host", "0.0.0.0"])
    assert result.exit_code != 0
    assert "no such option" in result.stdout.lower() or "no such option" in (result.stderr or "").lower()


def test_serve_opens_browser_by_default(monkeypatch):
    monkeypatch.setattr("uvicorn.run", lambda *a, **k: None)
    opened = []
    monkeypatch.setattr("webbrowser.open", lambda url: opened.append(url))

    # Replace threading.Timer with an immediate executor: when serve calls
    # Timer(delay, fn).start(), fire fn() right away. SimpleNamespace gives us
    # an object whose `.start` is a real callable (not a method that binds
    # `self`), so this avoids the TypeError that bound-method tricks cause.
    from types import SimpleNamespace
    monkeypatch.setattr(
        "threading.Timer",
        lambda delay, fn: SimpleNamespace(start=lambda: fn()),
    )

    from main import app
    runner = CliRunner()
    result = runner.invoke(app, ["serve", "--port", "7878"])
    assert result.exit_code == 0
    assert opened == ["http://127.0.0.1:7878"]
