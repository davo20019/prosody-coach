def test_app_factory_returns_fastapi_instance(app):
    from fastapi import FastAPI
    assert isinstance(app, FastAPI)


def test_health_endpoint_returns_ok(client):
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_static_assets_are_served(client):
    response = client.get("/static/vendor/htmx.min.js")
    assert response.status_code == 200
    assert "function" in response.text  # JS sanity check


def test_static_css_is_served(client):
    response = client.get("/static/app.css")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/css")


def test_ipa_css_uses_readable_sans_font(client):
    response = client.get("/static/app.css")
    assert response.status_code == 200
    css = response.text
    ipa_rule_start = css.index("/* IPA / phonetic accent */")
    ipa_rule_end = css.index("/* Tag pills */", ipa_rule_start)
    ipa_rule = css[ipa_rule_start:ipa_rule_end]

    assert 'font-family: "Geist"' in ipa_rule
    assert "font-style: normal" in ipa_rule
    assert "Fraunces" not in ipa_rule


def test_recorder_clears_analyzing_status_after_render(client):
    response = client.get("/static/recorder.js")
    assert response.status_code == 200
    body = response.text
    rendered_idx = body.index('new CustomEvent("prosody:analysis-rendered")')
    clear_idx = body.rindex('setStatus("", false)', 0, rendered_idx)
    assert clear_idx < rendered_idx


def test_app_js_toggles_prompt_level_ipa(client):
    response = client.get("/static/app.js")
    assert response.status_code == 200
    body = response.text
    assert "[data-toggle-prompt-ipa]" in body
    assert "data-ipa-visible" in body
    assert "Hide IPA" in body


def test_app_js_toggles_connected_speech(client):
    response = client.get("/static/app.js")
    assert response.status_code == 200
    body = response.text
    assert "[data-toggle-connected-speech]" in body
    assert "data-connected-visible" in body
    assert "Hide connected speech tips" in body
