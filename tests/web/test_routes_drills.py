def test_drills_index_shows_levels_and_status(client, monkeypatch):
    monkeypatch.setattr("web.routes.drills.get_available_levels", lambda: [1, 2, 3])
    # Real shape of get_rhythm_progress(): npvi_baseline / npvi_current /
    # current_level / levels (dict keyed 1..6).
    monkeypatch.setattr("web.routes.drills.get_rhythm_progress", lambda: {
        "npvi_baseline": 42.0,
        "npvi_current": 47.5,
        "current_level": 2,
        "levels": {
            1: {"consecutive_passes": 3, "total_attempts": 5, "unlocked_at": "2026-05-10"},
            2: {"consecutive_passes": 1, "total_attempts": 2, "unlocked_at": "2026-05-11"},
            3: {"consecutive_passes": 0, "total_attempts": 0, "unlocked_at": None},
        },
    })
    monkeypatch.setattr("web.routes.drills.get_due_rhythm_drills", lambda level=None, limit=5: [])
    response = client.get("/drills")
    assert response.status_code == 200
    assert "Level 1" in response.text
    assert "42" in response.text  # baseline value rendered
    assert "Due for practice" in response.text
    assert "Nothing due right now" in response.text  # empty-state copy


def test_drills_index_lists_due_drills(client, monkeypatch):
    """Spec parity: Drills shows 'due drills', resolves text via
    prompts.get_rhythm_drill (the rhythm_drills table has no text column)."""
    monkeypatch.setattr("web.routes.drills.get_available_levels", lambda: [1, 2])
    monkeypatch.setattr("web.routes.drills.get_rhythm_progress", lambda: {
        "npvi_baseline": 40.0, "npvi_current": 50.0, "current_level": 1,
        "levels": {1: {"consecutive_passes": 0, "total_attempts": 0, "unlocked_at": None}},
    })
    # Real storage shape: rhythm_drills row has drill_id/level/last_attempted,
    # NO text column.
    monkeypatch.setattr(
        "web.routes.drills.get_due_rhythm_drills",
        lambda level=None, limit=5: [
            {"drill_id": "d-99", "level": 1, "last_attempted": "2026-05-10"},
        ],
    )
    monkeypatch.setattr(
        "web.routes.drills.get_rhythm_drill",
        lambda did: {"id": did, "text": "BUH-buh-BUH-buh",
                       "level": 1, "focus": "stress contrast"} if did == "d-99" else None,
    )
    response = client.get("/drills")
    assert response.status_code == 200
    assert "BUH-buh-BUH-buh" in response.text  # text came from get_rhythm_drill
    # Link must include the drill_id so the run page loads THAT drill, not a
    # random one from the level.
    assert "/drills/level/1?drill_id=d-99" in response.text
    assert "Nothing due right now" not in response.text


def test_drill_run_renders_random_drill_when_no_id(client, monkeypatch):
    monkeypatch.setattr(
        "web.routes.drills.get_random_rhythm_drill",
        lambda level: {
            "id": "d-1",
            "text": "BUH-buh-BUH",
            "level": level,
            "focus": "stress contrast",
            "technique": "Lengthen stressed syllables",
        },
    )
    response = client.get("/drills/level/2")
    assert response.status_code == 200
    assert "BUH-buh-BUH" in response.text
    assert "/drills/attempt" in response.text


def test_drill_run_loads_specific_drill_when_drill_id_given(client, monkeypatch):
    """Clicking a due drill row must practice that exact drill, not a random one."""
    captured = {}
    def fake_random(level):
        captured["random_called"] = True
        return {"id": "rand", "text": "RANDOM", "level": level, "focus": "", "technique": ""}
    monkeypatch.setattr("web.routes.drills.get_random_rhythm_drill", fake_random)
    monkeypatch.setattr(
        "web.routes.drills.get_rhythm_drill",
        lambda did: {"id": did, "text": "DUE-DRILL-TEXT", "level": 2,
                       "focus": "schwa", "technique": "reduce"} if did == "d-99" else None,
    )

    response = client.get("/drills/level/2?drill_id=d-99")
    assert response.status_code == 200
    assert "DUE-DRILL-TEXT" in response.text
    assert "RANDOM" not in response.text
    assert "random_called" not in captured  # never reached the fallback


def test_drill_run_falls_back_to_random_when_drill_id_unknown(client, monkeypatch):
    monkeypatch.setattr(
        "web.routes.drills.get_rhythm_drill",
        lambda did: None,   # unknown id
    )
    monkeypatch.setattr(
        "web.routes.drills.get_random_rhythm_drill",
        lambda level: {"id": "fb", "text": "FALLBACK", "level": level,
                         "focus": "", "technique": ""},
    )
    response = client.get("/drills/level/2?drill_id=ghost")
    assert response.status_code == 200
    assert "FALLBACK" in response.text


def test_baseline_post_records_baseline(client, monkeypatch):
    captured = {}
    monkeypatch.setattr("web.routes.drills.set_rhythm_baseline", lambda v: captured.setdefault("v", v))
    response = client.post("/drills/baseline", data={"npvi": "55.5"})
    assert response.status_code == 200
    assert captured["v"] == 55.5
    assert "baseline" in response.text.lower()


# --- /drills/attempt POST tests ----------------------------------------------

import io
from pathlib import Path
from types import SimpleNamespace
import numpy as np
import soundfile as sf


def _drill_prosody_stub(score=8, pvi=55):
    return SimpleNamespace(
        pitch=SimpleNamespace(score=7, feedback="p"),
        volume=SimpleNamespace(score=7, feedback="v"),
        tempo=SimpleNamespace(score=7, estimated_wpm=140, feedback="t"),
        rhythm=SimpleNamespace(score=score, pvi=pvi, feedback="r"),
        pauses=SimpleNamespace(score=7, feedback="pa"),
        to_dict=lambda: {"duration": 5.0, "pitch_score": 7, "volume_score": 7,
                          "tempo_score": 7, "rhythm_score": score,
                          "pause_score": 7, "overall_score": float(score)},
    )


def _drill_progress_with_config():
    return {
        "npvi_baseline": 40.0, "npvi_current": 55.0, "current_level": 2,
        "levels": {
            2: {"consecutive_passes": 0, "total_attempts": 0, "unlocked_at": None,
                "config": {"npvi_target": 50, "min_rhythm_score": 6}},
        },
    }


def _patch_drill_pipeline(monkeypatch, tmp_path, prosody, *, rhythm_coach=None,
                            rhythm_raises=None, analyzer_raises=None):
    """Common monkeypatching for drill attempt tests."""
    monkeypatch.setattr("web.routes.drills.RECORDINGS_DIR", tmp_path)
    monkeypatch.setattr(
        "web.routes.drills.transcode_to_wav",
        lambda src, dst: (sf.write(dst, np.zeros(16000, dtype=np.int16), 16000, subtype="PCM_16") or dst),
    )
    if analyzer_raises is not None:
        def boom(*a, **k): raise analyzer_raises
        monkeypatch.setattr("web.routes.drills.analyze_prosody", boom)
    else:
        monkeypatch.setattr("web.routes.drills.analyze_prosody", lambda *a, **k: prosody)
    monkeypatch.setattr("web.routes.drills.get_rhythm_progress", _drill_progress_with_config)
    captured = {"updates": [], "attempts": [], "saves": []}
    monkeypatch.setattr(
        "web.routes.drills.update_rhythm_progress",
        lambda **k: captured["updates"].append(k),
    )
    monkeypatch.setattr(
        "web.routes.drills.save_rhythm_drill_attempt",
        lambda **k: captured["attempts"].append(k),
    )
    monkeypatch.setattr(
        "web.routes.drills.save_session",
        lambda *a, **k: (captured["saves"].append(k), 1)[1],
    )
    # Patch the rhythm coach import to a fake. The route imports lazily, so
    # we set the attribute on the coach module.
    import coach
    if rhythm_raises is not None:
        def boom(*a, **k): raise rhythm_raises
        monkeypatch.setattr(coach, "analyze_rhythm_with_coach", boom, raising=False)
    else:
        monkeypatch.setattr(
            coach, "analyze_rhythm_with_coach",
            lambda *a, **k: rhythm_coach, raising=False,
        )
    return captured


def test_drill_attempt_passes_when_ai_says_so(client, tmp_path, monkeypatch):
    """Gemini path: trust rhythm_result.level_passed AND its rhythm_score."""
    monkeypatch.setattr("web.routes.drills.COACH_PROVIDER", "gemini")
    prosody = _drill_prosody_stub(score=4, pvi=30)  # measured rule would FAIL
    rhythm = SimpleNamespace(
        transcript="x", encouragement="great work", technique_tip="lift the stress",
        level_passed=True, rhythm_score=8, word_stress_issues=None,
    )
    cap = _patch_drill_pipeline(monkeypatch, tmp_path, prosody, rhythm_coach=rhythm)

    response = client.post(
        "/drills/attempt",
        data={"drill_id": "d-1", "level": "2", "expected_text": "BUH-buh", "mode": "drill"},
        files={"audio": ("rec.webm", io.BytesIO(b"\x1a\x45\xdf\xa3"), "audio/webm")},
    )
    assert response.status_code == 200
    assert cap["updates"][0]["passed"] is True
    assert cap["updates"][0]["rhythm_score"] == 8
    assert cap["attempts"][0]["rhythm_score"] == 8
    assert cap["saves"][0]["coach_status"] == "ok"
    assert cap["saves"][0]["ai_summary"] == "great work"
    assert cap["saves"][0]["ai_tips"] == ["lift the stress"]
    assert "PASS" in response.text


def test_drill_attempt_local_provider_falls_back_to_measured_rule(client, tmp_path, monkeypatch):
    """Local path: returns CoachingResult → use measured rule + map local
    coach fields (coaching_tips, overall_feedback) into the template/save_session."""
    monkeypatch.setattr("web.routes.drills.COACH_PROVIDER", "local")
    prosody = _drill_prosody_stub(score=8, pvi=60)  # measured rule would PASS
    local_result = SimpleNamespace(
        transcript="hola world",
        coaching_tips=["lengthen stressed syllables", "reduce schwa"],
        overall_feedback="solid attempt — keep going",
    )
    import local_coach
    monkeypatch.setattr(local_coach, "analyze_with_local_coach",
                         lambda *a, **k: local_result, raising=False)
    cap = _patch_drill_pipeline(monkeypatch, tmp_path, prosody, rhythm_coach=local_result)

    response = client.post(
        "/drills/attempt",
        data={"drill_id": "d-1", "level": "2", "expected_text": "BUH-buh", "mode": "drill"},
        files={"audio": ("rec.webm", io.BytesIO(b"\x1a\x45\xdf\xa3"), "audio/webm")},
    )
    assert response.status_code == 200
    assert cap["updates"][0]["passed"] is True
    assert cap["updates"][0]["rhythm_score"] == 8
    assert cap["saves"][0]["ai_summary"] == "solid attempt — keep going"
    assert cap["saves"][0]["ai_tips"] == ["lengthen stressed syllables", "reduce schwa"]
    assert "solid attempt" in response.text
    assert "lengthen stressed syllables" in response.text
    assert "PASS" in response.text


def test_drill_attempt_records_failure_when_coach_raises(client, tmp_path, monkeypatch):
    monkeypatch.setattr("web.routes.drills.COACH_PROVIDER", "gemini")
    prosody = _drill_prosody_stub(score=4, pvi=30)  # measured rule would FAIL too
    cap = _patch_drill_pipeline(
        monkeypatch, tmp_path, prosody, rhythm_raises=RuntimeError("API down"),
    )
    response = client.post(
        "/drills/attempt",
        data={"drill_id": "d-1", "level": "2", "expected_text": "BUH-buh", "mode": "drill"},
        files={"audio": ("rec.webm", io.BytesIO(b"\x1a\x45\xdf\xa3"), "audio/webm")},
    )
    assert response.status_code == 200
    assert cap["saves"][0]["coach_status"] == "failed"
    assert "API down" in cap["saves"][0]["coach_error"]
    assert cap["updates"][0]["passed"] is False
    assert "Keep practicing" in response.text


def test_drill_attempt_renders_error_banner_when_praat_fails(client, tmp_path, monkeypatch):
    monkeypatch.setattr("web.routes.drills.COACH_PROVIDER", "gemini")
    cap = _patch_drill_pipeline(
        monkeypatch, tmp_path, _drill_prosody_stub(),
        analyzer_raises=RuntimeError("Sound is too short for analysis"),
    )
    response = client.post(
        "/drills/attempt",
        data={"drill_id": "d-1", "level": "2", "expected_text": "BUH-buh", "mode": "drill"},
        files={"audio": ("rec.webm", io.BytesIO(b"\x1a\x45\xdf\xa3"), "audio/webm")},
    )
    assert response.status_code == 200
    assert "Audio analysis failed" in response.text
    assert cap["saves"] == []
