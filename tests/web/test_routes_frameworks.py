"""Integration tests for the /frameworks routes."""


def test_frameworks_index_lists_all_frameworks(client, monkeypatch):
    monkeypatch.setattr(
        "web.routes.frameworks.get_framework_progress", lambda: {}
    )
    monkeypatch.setattr(
        "web.routes.frameworks.get_due_framework_prompts", lambda limit=5: []
    )
    response = client.get("/frameworks")
    assert response.status_code == 200
    # The five v1 frameworks must all appear by name.
    assert "STAR Method" in response.text
    assert "PREP" in response.text
    assert "SCQA" in response.text
    assert "SBI" in response.text
    assert "Story Arc" in response.text
    # Empty-state copy when nothing is due.
    assert "Nothing due right now" in response.text


def test_frameworks_index_shows_due_prompts(client, monkeypatch):
    monkeypatch.setattr(
        "web.routes.frameworks.get_framework_progress", lambda: {}
    )
    monkeypatch.setattr(
        "web.routes.frameworks.get_due_framework_prompts",
        lambda limit=5: [
            {
                "framework_id": "star",
                "prompt_id": "star_1",
                "last_attempted": "2026-05-10",
                "last_score": 7.5,
            },
        ],
    )
    response = client.get("/frameworks")
    assert response.status_code == 200
    # Prompt text comes from frameworks.FRAMEWORKS via get_prompt.
    assert "Tell me about a time" in response.text
    # Link must include the prompt_id so the run page loads THAT prompt.
    assert "/frameworks/star?prompt_id=star_1" in response.text
    assert "Nothing due right now" not in response.text


def test_framework_run_renders_default_prompt(client, monkeypatch):
    # _pick_next_prompt sorts by least-recently-practiced. Force an empty
    # progress dict so the test doesn't depend on local DB history.
    monkeypatch.setattr(
        "web.routes.frameworks.get_framework_progress", lambda fid=None: {}
    )
    response = client.get("/frameworks/star")
    assert response.status_code == 200
    assert "STAR Method" in response.text
    # First prompt should be selected by default.
    assert "Tell me about a time you handled a conflict" in response.text
    assert 'data-repeat-inline' in response.text
    assert 'data-repeat-inline hidden' in response.text
    # Slot structure summary appears in the page.
    assert "Situation" in response.text and "Result" in response.text


def test_framework_run_loads_specific_prompt(client):
    response = client.get("/frameworks/star?prompt_id=star_3")
    assert response.status_code == 200
    # star_3 is the manager-disagreement prompt.
    assert "disagreed with your manager" in response.text


def test_framework_run_returns_404_for_unknown_framework(client):
    response = client.get("/frameworks/nope")
    assert response.status_code == 404


def test_framework_attempt_unknown_framework_renders_error_banner(client):
    """Bad framework_id on POST returns the shared error banner, not a 500."""
    # No need to stub audio handling; the framework check fires first.
    response = client.post(
        "/frameworks/attempt",
        files={"audio": ("x.webm", b"not real audio", "audio/webm")},
        data={"framework_id": "nope", "prompt_id": "star_1"},
    )
    assert response.status_code == 200
    assert "Unknown framework: nope" in response.text


def test_nav_contains_frameworks_link(client):
    """Sidebar nav must include the Frameworks entry (regression guard)."""
    response = client.get("/frameworks")
    assert response.status_code == 200
    # The link plus the label render in the Speak section.
    assert 'href="/frameworks"' in response.text
    assert "Frameworks" in response.text


# --------------------------------------------------------------------------- #
# Rotation (no prompt_id given → least-recently-practiced)
# --------------------------------------------------------------------------- #

def test_framework_run_picks_least_recently_practiced(client, monkeypatch):
    """When no prompt_id is given, rotation should prefer prompts the user
    has not yet attempted, then the oldest by last_attempted."""
    monkeypatch.setattr(
        "web.routes.frameworks.get_framework_progress",
        lambda framework_id=None: {
            "framework_id": "star",
            "total_attempts": 3,
            "total_passes": 1,
            "last_score": 6.0,
            "last_attempted": "2026-05-10T10:00:00",
            "prompt_progress": [
                {"prompt_id": "star_1", "last_attempted": "2026-05-10T10:00:00"},
                # star_2 not in progress → unseen → should win.
                {"prompt_id": "star_3", "last_attempted": "2026-05-09T10:00:00"},
            ],
        } if framework_id == "star" else {},
    )
    response = client.get("/frameworks/star")
    assert response.status_code == 200
    # star_2 is the "learn something new quickly" prompt.
    assert "learn something new quickly" in response.text


def test_framework_run_rotation_falls_back_to_oldest(client, monkeypatch):
    """When all prompts have been seen, pick the oldest last_attempted."""
    monkeypatch.setattr(
        "web.routes.frameworks.get_framework_progress",
        lambda framework_id=None: {
            "framework_id": "star",
            "total_attempts": 5, "total_passes": 2, "last_score": 7.0,
            "last_attempted": "2026-05-10",
            # Every star_N has progress; oldest is star_3.
            "prompt_progress": [
                {"prompt_id": "star_1", "last_attempted": "2026-05-10"},
                {"prompt_id": "star_2", "last_attempted": "2026-05-09"},
                {"prompt_id": "star_3", "last_attempted": "2026-05-01"},
                {"prompt_id": "star_4", "last_attempted": "2026-05-05"},
                {"prompt_id": "star_5", "last_attempted": "2026-05-08"},
            ],
        } if framework_id == "star" else {},
    )
    response = client.get("/frameworks/star")
    assert response.status_code == 200
    # star_3 is the "disagreed with your manager" prompt.
    assert "disagreed with your manager" in response.text


# --------------------------------------------------------------------------- #
# Generate endpoint
# --------------------------------------------------------------------------- #

def test_framework_generate_renders_ephemeral_prompt(client, monkeypatch):
    """GET /frameworks/{id}/generate calls the model and renders the run page
    with the generated text and a `generated:` prompt id."""
    monkeypatch.setattr(
        "web.routes.frameworks.generate_prompt",
        lambda framework, provider: "Describe a moment where you had to escalate an issue to leadership.",
    )
    response = client.get("/frameworks/star/generate")
    assert response.status_code == 200
    assert "Describe a moment where you had to escalate" in response.text
    # Badge appears for AI-generated prompts.
    assert "AI-generated" in response.text
    # The hidden form field carries a `generated:` id so the POST handler
    # knows to use prompt_text and skip spaced repetition.
    assert 'name="prompt_id" value="generated:' in response.text
    # prompt_text hidden field is populated so the POST works without a
    # catalog lookup.
    assert "Describe a moment where you had to escalate" in response.text


def test_framework_generate_surfaces_model_error(client, monkeypatch):
    """If the model can't produce a usable prompt, show the error banner."""
    def _boom(framework, provider):
        raise RuntimeError("model returned empty")
    monkeypatch.setattr("web.routes.frameworks.generate_prompt", _boom)
    response = client.get("/frameworks/star/generate")
    assert response.status_code == 200
    assert "Could not generate a prompt" in response.text


def test_framework_generate_404_for_unknown_framework(client):
    response = client.get("/frameworks/nope/generate")
    assert response.status_code == 404


# --------------------------------------------------------------------------- #
# Ephemeral attempts skip spaced-repetition tracking
# --------------------------------------------------------------------------- #

def test_save_framework_attempt_skips_progress_for_ephemeral_prompts(monkeypatch):
    """Ephemeral prompts (id prefix `generated:`) must not write to
    framework_prompt_progress — they're one-shots, not recurrers."""
    import storage

    saved_session_calls = []
    upsert_calls = []

    monkeypatch.setattr(
        storage, "save_session",
        lambda **kw: saved_session_calls.append(kw) or 42,
    )
    monkeypatch.setattr(
        storage, "_upsert_framework_prompt_progress",
        lambda *a, **kw: upsert_calls.append((a, kw)),
    )

    class _Stub:
        slots = []
        grammar_notes = []
        cultural_note = ""
        overall_note = ""

    class _AnalysisStub:
        def to_dict(self):
            return {"overall_score": 5.0, "duration": 10.0}

    storage.save_framework_attempt(
        analysis=_AnalysisStub(),
        framework_id="star",
        prompt_id="generated:abc123",
        structure=_Stub(),
        per_slot_prosody=None,
        overall_score=8.0,
        passed=True,
        transcript="x",
        recording_path=None,
        coach_provider="local",
        coach_status="ok",
    )

    assert len(saved_session_calls) == 1
    assert saved_session_calls[0]["mode"] == "framework"
    # No SR row written for ephemeral prompts.
    assert upsert_calls == []


def test_save_framework_attempt_writes_progress_for_curated_prompts(monkeypatch):
    import storage

    upsert_calls = []
    monkeypatch.setattr(storage, "save_session", lambda **kw: 99)
    monkeypatch.setattr(
        storage, "_upsert_framework_prompt_progress",
        lambda *a, **kw: upsert_calls.append(a),
    )

    class _Stub:
        slots = []
        grammar_notes = []
        cultural_note = ""
        overall_note = ""

    class _AnalysisStub:
        def to_dict(self):
            return {"overall_score": 5.0, "duration": 10.0}

    storage.save_framework_attempt(
        analysis=_AnalysisStub(),
        framework_id="star",
        prompt_id="star_1",   # curated
        structure=_Stub(),
        per_slot_prosody=None,
        overall_score=7.5,
        passed=True,
        transcript="x",
        recording_path=None,
        coach_provider="local",
        coach_status="ok",
    )

    assert len(upsert_calls) == 1
    assert upsert_calls[0][:2] == ("star", "star_1")


# --------------------------------------------------------------------------- #
# Starter phrases (ESL scaffolding)
# --------------------------------------------------------------------------- #

def test_run_page_renders_starter_phrases(client):
    """Run page must include the collapsible starter-phrases block when the
    framework's slots define them. The block is closed by default so the
    casual user isn't pushed into formulaic delivery — they have to open it."""
    response = client.get("/frameworks/star")
    assert response.status_code == 200
    # Block heading is present.
    assert "Starter phrases" in response.text
    # The block is a <details> element (collapsible) — no `open` attribute,
    # so it's closed by default. Sanity check both shapes:
    assert "<details" in response.text
    # A known STAR starter from frameworks.py.
    assert "At my last role," in response.text
    assert "My responsibility was to" in response.text


def test_all_frameworks_have_three_starters_per_slot():
    """Guard against contributors adding a framework without starters."""
    import frameworks as fwmod
    for fid, fw in fwmod.FRAMEWORKS.items():
        for slot in fw["slots"]:
            assert "starters" in slot, f"{fid}.{slot['id']}: missing starters"
            assert len(slot["starters"]) == 3, (
                f"{fid}.{slot['id']}: expected 3 starters, "
                f"got {len(slot['starters'])}"
            )
            for s in slot["starters"]:
                assert isinstance(s, str) and s.strip(), (
                    f"{fid}.{slot['id']}: empty starter"
                )
