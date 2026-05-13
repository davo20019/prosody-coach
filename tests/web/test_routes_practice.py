def test_get_practice_renders_form(client):
    response = client.get("/practice")
    assert response.status_code == 200
    body = response.text
    assert 'data-recorder' in body
    assert 'data-record' in body  # the button
    assert '/practice/analyze' in body  # the form action
    assert 'id="result-region"' in body


def test_root_redirects_to_practice(client):
    response = client.get("/", follow_redirects=False)
    assert response.status_code in (302, 307)
    assert response.headers["location"] == "/practice"


def test_practice_with_prompt_id_loads_prompt_text(client, monkeypatch):
    monkeypatch.setattr(
        "web.routes.practice.get_prompt_by_id",
        lambda pid: {"id": pid, "text": "The quick brown fox", "category": "stress"} if pid == "p1" else None,
    )
    response = client.get("/practice?prompt_id=p1")
    assert response.status_code == 200
    assert "The quick brown fox" in response.text


def test_practice_with_unknown_prompt_id_renders_blank(client, monkeypatch):
    monkeypatch.setattr("web.routes.practice.get_prompt_by_id", lambda pid: None)
    response = client.get("/practice?prompt_id=nope")
    assert response.status_code == 200
    assert "nope" not in response.text  # no leak of the bogus id as content


def test_practice_renders_tips_drawer(client):
    """Spec parity: prosody tips content is available on the Practice page."""
    response = client.get("/practice")
    assert response.status_code == 200
    assert "Tips for Spanish speakers" in response.text
    assert "schwa" in response.text.lower()
    assert "<details" in response.text  # collapsible
