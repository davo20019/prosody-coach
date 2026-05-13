def test_train_page_uses_tailored_prompt_generator(client, monkeypatch):
    captured = {}
    monkeypatch.setattr(
        "web.routes.train.get_user_weaknesses",
        lambda limit=10: {"weakest_components": ["pitch"]},
    )
    monkeypatch.setattr(
        "web.routes.train.get_due_sounds",
        lambda limit=5: [{"sound": "th"}],
    )
    monkeypatch.setattr(
        "web.routes.train.get_due_words",
        lambda limit=5: [{"word": "thought"}],
    )
    def fake_gen(weaknesses, due_sounds=None, due_words=None):
        captured["weak"] = weaknesses
        captured["sounds"] = due_sounds
        captured["words"] = due_words
        return {
            "id": "tailored-1",
            "text": "Tailored sentence to read",
            "key_sounds": "th",
            "target_sounds": [{"sound": "th", "ipa": "θ"}],
        }
    monkeypatch.setattr("web.routes.train.generate_tailored_prompt", fake_gen)

    response = client.get("/train")
    assert response.status_code == 200
    assert "Tailored sentence to read" in response.text
    assert "/train/analyze" in response.text
    assert 'name="target_sounds" value="th"' in response.text
    assert captured["weak"] == {"weakest_components": ["pitch"]}
    assert captured["sounds"] == [{"sound": "th"}]
    assert captured["words"] == [{"word": "thought"}]


def test_train_page_falls_back_when_generation_fails(client, monkeypatch):
    monkeypatch.setattr(
        "web.routes.train.get_user_weaknesses",
        lambda limit=10: {"weakest_components": []},
    )
    monkeypatch.setattr("web.routes.train.get_due_sounds", lambda limit=5: [])
    monkeypatch.setattr("web.routes.train.get_due_words", lambda limit=5: [])
    def boom(*a, **k):
        raise RuntimeError("no api key")
    monkeypatch.setattr("web.routes.train.generate_tailored_prompt", boom)
    monkeypatch.setattr(
        "web.routes.train.get_random_prompt",
        lambda *a, **k: {"id": "fb-1", "text": "Fallback prompt", "category": "stress"},
    )
    response = client.get("/train")
    assert response.status_code == 200
    assert "Fallback prompt" in response.text


def test_train_post_uses_practice_pipeline_and_persists_full_coach(client, tmp_path, monkeypatch):
    """Train must persist the same coach fields Practice does — pronunciation,
    grammar, confidence, fillers, fluency — so train sessions feed spaced
    repetition and history detail like practice sessions do."""
    import io
    import numpy as np
    import soundfile as sf
    from coach_pipeline import SessionResult
    from types import SimpleNamespace

    monkeypatch.setattr("web.routes.train.RECORDINGS_DIR", tmp_path)
    monkeypatch.setattr(
        "web.routes.train.transcode_to_wav",
        lambda src, dst: (sf.write(dst, np.zeros(16000, dtype=np.int16), 16000, subtype="PCM_16") or dst),
    )

    analysis = SimpleNamespace(
        pitch=SimpleNamespace(score=8, feedback="p"),
        volume=SimpleNamespace(score=8, feedback="v"),
        tempo=SimpleNamespace(score=8, estimated_wpm=140, feedback="t"),
        rhythm=SimpleNamespace(score=8, pvi=55, feedback="r"),
        pauses=SimpleNamespace(score=8, feedback="pa"),
        to_dict=lambda: {"duration": 5.0, "pitch_score": 8, "volume_score": 8,
                          "tempo_score": 8, "rhythm_score": 8, "pause_score": 8,
                          "overall_score": 8.0},
    )
    full_coach = {
        "transcript": "the quick brown fox",
        "summary": "good baseline",
        "tips": ["pace yourself"],
        "grammar_issues": [{"original": "fox", "corrected": "fox", "explanation": "ok"}],
        "suggested_revision": "the quick brown fox",
        "confidence_score": 7,
        "confidence_feedback": "steady",
        "filler_word_count": 1,
        "filler_words_detail": "um x1",
        "pronunciation_issues": [{"sound": "th", "example": "the", "ipa": "/ð/", "tip": "voiced"}],
        "fluency_score": 8,
        "fluency_feedback": "smooth",
    }
    monkeypatch.setattr(
        "web.routes.train.analyze_session",
        lambda *a, **k: SessionResult(
            analysis=analysis, coach=full_coach,
            provider="gemini", status="ok", error=None,
        ),
    )
    saved = []
    monkeypatch.setattr(
        "web.routes.train.save_session",
        lambda *a, **k: (saved.append(k), 1)[1],
    )
    response = client.post(
        "/train/analyze",
        data={"mode": "train"},
        files={"audio": ("rec.webm", io.BytesIO(b"\x1a\x45\xdf\xa3"), "audio/webm")},
    )
    assert response.status_code == 200
    assert "Component" in response.text  # analysis_card rendered

    assert len(saved) == 1
    kw = saved[0]
    # Mirrors the practice route's save_session field list — these are the
    # columns spaced repetition / history detail / weakness tracking depend on.
    assert kw["transcript"] == "the quick brown fox"
    assert kw["ai_summary"] == "good baseline"
    assert kw["ai_tips"] == ["pace yourself"]
    assert kw["grammar_issues"] == full_coach["grammar_issues"]
    assert kw["suggested_revision"] == "the quick brown fox"
    assert kw["confidence_score"] == 7
    assert kw["confidence_feedback"] == "steady"
    assert kw["filler_word_count"] == 1
    assert kw["filler_words_detail"] == "um x1"
    assert kw["pronunciation_issues"] == full_coach["pronunciation_issues"]
    assert kw["fluency_score"] == 8
    assert kw["fluency_feedback"] == "smooth"
    assert kw["coach_provider"] == "gemini"
    assert kw["coach_status"] == "ok"


def test_train_post_advances_due_word_when_practiced_correctly(client, tmp_path, monkeypatch):
    import io
    import numpy as np
    import soundfile as sf
    from coach_pipeline import SessionResult
    from types import SimpleNamespace

    monkeypatch.setattr("web.routes.train.RECORDINGS_DIR", tmp_path)
    monkeypatch.setattr(
        "web.routes.train.transcode_to_wav",
        lambda src, dst: (sf.write(dst, np.zeros(16000, dtype=np.int16), 16000, subtype="PCM_16") or dst),
    )

    analysis = SimpleNamespace(
        pitch=SimpleNamespace(score=8, feedback="p"),
        volume=SimpleNamespace(score=8, feedback="v"),
        tempo=SimpleNamespace(score=8, estimated_wpm=140, feedback="t"),
        rhythm=SimpleNamespace(score=8, pvi=55, feedback="r"),
        pauses=SimpleNamespace(score=8, feedback="pa"),
        to_dict=lambda: {"duration": 5.0, "pitch_score": 8, "volume_score": 8,
                          "tempo_score": 8, "rhythm_score": 8, "pause_score": 8,
                          "overall_score": 8.0},
    )
    monkeypatch.setattr(
        "web.routes.train.analyze_session",
        lambda *a, **k: SessionResult(
            analysis=analysis,
            coach={"transcript": "I thought about it", "pronunciation_issues": []},
            provider="gemini",
            status="ok",
            error=None,
        ),
    )
    monkeypatch.setattr("web.routes.train.save_session", lambda *a, **k: 1)
    monkeypatch.setattr(
        "web.routes.train.get_due_words",
        lambda limit=100: [{"word": "thought", "ipa": "θɔːt", "related_sound": "th"}],
    )
    updates = []
    monkeypatch.setattr(
        "web.routes.train.update_word_after_practice",
        lambda word, was_correct: updates.append((word, was_correct)),
    )

    response = client.post(
        "/train/analyze",
        data={"mode": "train", "expected_text": "I thought about it."},
        files={"audio": ("rec.webm", io.BytesIO(b"\x1a\x45\xdf\xa3"), "audio/webm")},
    )

    assert response.status_code == 200
    assert updates == [("thought", True)]


def test_train_post_advances_target_sound_when_practiced_correctly(client, tmp_path, monkeypatch):
    import io
    import numpy as np
    import soundfile as sf
    from coach_pipeline import SessionResult
    from types import SimpleNamespace

    monkeypatch.setattr("web.routes.train.RECORDINGS_DIR", tmp_path)
    monkeypatch.setattr(
        "web.routes.train.transcode_to_wav",
        lambda src, dst: (sf.write(dst, np.zeros(16000, dtype=np.int16), 16000, subtype="PCM_16") or dst),
    )

    analysis = SimpleNamespace(
        pitch=SimpleNamespace(score=8, feedback="p"),
        volume=SimpleNamespace(score=8, feedback="v"),
        tempo=SimpleNamespace(score=8, estimated_wpm=140, feedback="t"),
        rhythm=SimpleNamespace(score=8, pvi=55, feedback="r"),
        pauses=SimpleNamespace(score=8, feedback="pa"),
        to_dict=lambda: {"duration": 5.0, "pitch_score": 8, "volume_score": 8,
                          "tempo_score": 8, "rhythm_score": 8, "pause_score": 8,
                          "overall_score": 8.0},
    )
    monkeypatch.setattr(
        "web.routes.train.analyze_session",
        lambda *a, **k: SessionResult(
            analysis=analysis,
            coach={"transcript": "I thought about it", "pronunciation_issues": []},
            provider="gemini",
            status="ok",
            error=None,
        ),
    )
    monkeypatch.setattr("web.routes.train.save_session", lambda *a, **k: 1)
    updates = []
    monkeypatch.setattr(
        "web.routes.train.update_sound_after_practice",
        lambda sound, was_correct: updates.append((sound, was_correct)),
    )

    response = client.post(
        "/train/analyze",
        data={"mode": "train", "expected_text": "I thought about it.", "target_sounds": ["th"]},
        files={"audio": ("rec.webm", io.BytesIO(b"\x1a\x45\xdf\xa3"), "audio/webm")},
    )

    assert response.status_code == 200
    assert updates == [("th", True)]
