def test_settings_renders_provider_and_local_status(client, monkeypatch):
    from types import SimpleNamespace
    monkeypatch.setattr("web.routes.settings.COACH_PROVIDER", "gemini")
    monkeypatch.setattr("web.routes.settings.GEMINI_API_KEY", "set-key")
    monkeypatch.setattr(
        "web.routes.settings.diagnose_local_setup",
        lambda: [
            type("C", (), {"label": "whisper-cli", "ok": True, "detail": "found", "fix": ""})(),
            type("C", (), {"label": "gemma model", "ok": False, "detail": "missing", "fix": "download it"})(),
        ],
    )
    fake_local_config = SimpleNamespace(
        whisper_bin="/usr/local/bin/whisper-cli", whisper_model="/models/ggml-base.en.bin",
        whisper_server_url="", llm_base_url="http://127.0.0.1:8080/v1",
        llm_model="gemma-local", llm_timeout=120.0,
    )
    monkeypatch.setattr("web.routes.settings.LocalCoachConfig",
                          type("LCC", (), {"from_env": staticmethod(lambda: fake_local_config)}))
    response = client.get("/settings")
    assert response.status_code == 200
    assert "gemini" in response.text
    assert "whisper-cli" in response.text
    assert "missing" in response.text
    assert "download it" in response.text
    # Spec parity surfaces:
    assert "About prosody" in response.text                # prosody info
    assert "Local AI configuration" in response.text       # prosody local config
    assert "ggml-base.en.bin" in response.text             # config value rendered


def test_settings_warns_when_no_provider_configured(client, monkeypatch):
    from types import SimpleNamespace
    monkeypatch.setattr("web.routes.settings.COACH_PROVIDER", "gemini")
    monkeypatch.setattr("web.routes.settings.GEMINI_API_KEY", "")
    monkeypatch.setattr("web.routes.settings.diagnose_local_setup", lambda: [])
    monkeypatch.setattr(
        "web.routes.settings.LocalCoachConfig",
        type("LCC", (), {"from_env": staticmethod(lambda: SimpleNamespace(
            whisper_bin="", whisper_model="", whisper_server_url="",
            llm_base_url="", llm_model="", llm_timeout=0))}),
    )
    response = client.get("/settings")
    assert response.status_code == 200
    assert "No AI coaching configured" in response.text or "GEMINI_API_KEY" in response.text
