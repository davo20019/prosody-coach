def test_sounds_page_lists_due_and_tracked(client, monkeypatch):
    monkeypatch.setattr("web.routes.sounds.get_due_sounds", lambda limit=10: [
        {"sound": "th", "ipa": "θ", "example_word": "think"},
    ])
    monkeypatch.setattr("web.routes.sounds.get_all_tracked_sounds", lambda: [
        {"sound": "r", "ipa": "ɹ", "example_word": "red"},
        {"sound": "th", "ipa": "θ", "example_word": "think"},
    ])
    response = client.get("/sounds")
    assert response.status_code == 200
    assert "think" in response.text
    assert "red" in response.text
    assert 'data-ipa-scope="sounds"' in response.text
    assert 'data-toggle-ipa' in response.text
    assert 'class="ipa-col"' in response.text


def test_sounds_page_makes_practice_primary_and_manual_review_secondary(client, monkeypatch):
    monkeypatch.setattr("web.routes.sounds.get_due_sounds", lambda limit=10: [
        {"sound": "th", "ipa": "θ", "example_word": "think"},
    ])
    monkeypatch.setattr("web.routes.sounds.get_all_tracked_sounds", lambda: [])

    response = client.get("/sounds")

    assert response.status_code == 200
    assert 'href="/train"' in response.text
    assert "Practice due sounds" in response.text
    assert "Manual overrides" in response.text
    assert "Mark as reviewed" in response.text
    assert "Mark correct" not in response.text
    assert "<th></th>" not in response.text


def test_sound_practice_post_updates_progress(client, monkeypatch):
    captured = {}
    monkeypatch.setattr(
        "web.routes.sounds.update_sound_after_practice",
        lambda sound, was_correct: captured.update({"sound": sound, "ok": was_correct}),
    )
    response = client.post("/sounds/th/practice", data={"was_correct": "true"})
    assert response.status_code == 200
    assert captured == {"sound": "th", "ok": True}
    assert "Reviewed: th" in response.text
