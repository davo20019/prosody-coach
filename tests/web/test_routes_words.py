def test_words_page_lists_due(client, monkeypatch):
    monkeypatch.setattr("web.routes.words.get_due_words", lambda limit=10: [
        {"word": "thought", "ipa": "θɔːt", "related_sound": "th"},
    ])
    response = client.get("/words")
    assert response.status_code == 200
    assert "thought" in response.text


def test_word_practice_post_updates_progress(client, monkeypatch):
    captured = {}
    monkeypatch.setattr(
        "web.routes.words.update_word_after_practice",
        lambda w, ok: captured.update({"w": w, "ok": ok}),
    )
    response = client.post("/words/thought/practice", data={"was_correct": "true"})
    assert response.status_code == 200
    assert captured == {"w": "thought", "ok": True}
