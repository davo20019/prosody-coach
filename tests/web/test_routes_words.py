def test_words_page_lists_due(client, monkeypatch):
    monkeypatch.setattr("web.routes.words.get_due_words", lambda limit=10: [
        {"word": "thought", "ipa": "θɔːt", "related_sound": "th"},
    ])
    monkeypatch.setattr("web.routes.words.get_all_tracked_words", lambda: [])
    response = client.get("/words")
    assert response.status_code == 200
    assert "thought" in response.text


def test_words_page_makes_practice_primary_and_manual_review_secondary(client, monkeypatch):
    monkeypatch.setattr("web.routes.words.get_due_words", lambda limit=10: [
        {"word": "thought", "ipa": "θɔːt", "related_sound": "th"},
    ])
    monkeypatch.setattr("web.routes.words.get_all_tracked_words", lambda: [])

    response = client.get("/words")

    assert response.status_code == 200
    assert 'href="/train"' in response.text
    assert "Practice due words" in response.text
    assert "Manual overrides" in response.text
    assert "Mark as reviewed" in response.text
    assert "Mark correct" not in response.text
    assert "<th></th>" not in response.text


def test_words_page_lists_tracked(client, monkeypatch):
    monkeypatch.setattr("web.routes.words.get_due_words", lambda limit=10: [])
    monkeypatch.setattr("web.routes.words.get_all_tracked_words", lambda: [
        {"word": "thought", "ipa": "θɔːt", "related_sound": "th", "times_mispronounced": 3},
        {"word": "red", "ipa": "ɹɛd", "related_sound": "r", "times_mispronounced": 1},
    ])
    response = client.get("/words")
    assert response.status_code == 200
    assert "All tracked words" in response.text
    assert "thought" in response.text and "red" in response.text
    assert "mispronounced 3×" in response.text


def test_word_practice_post_updates_progress(client, monkeypatch):
    captured = {}
    monkeypatch.setattr(
        "web.routes.words.update_word_after_practice",
        lambda w, ok: captured.update({"w": w, "ok": ok}),
    )
    response = client.post("/words/thought/practice", data={"was_correct": "true"})
    assert response.status_code == 200
    assert captured == {"w": "thought", "ok": True}
    assert "Reviewed: thought" in response.text
