def test_history_list_renders_sessions(client, monkeypatch):
    monkeypatch.setattr(
        "web.routes.history.get_history",
        lambda limit=50, mode=None: [
            {"id": 1, "created_at": "2026-05-12T10:00:00", "mode": "practice",
             "overall_score": 7.5, "coach_provider": "gemini", "coach_status": "ok"},
            {"id": 2, "created_at": "2026-05-12T11:00:00", "mode": "analyze",
             "overall_score": 8.0, "coach_provider": "local", "coach_status": "failed"},
        ],
    )
    response = client.get("/history")
    assert response.status_code == 200
    assert "7.5" in response.text and "8.0" in response.text
    assert "gemini" in response.text and "local" in response.text


def test_history_detail_renders_one_session(client, monkeypatch):
    monkeypatch.setattr(
        "web.routes.history.get_session",
        lambda sid: {
            "id": sid, "created_at": "2026-05-12T10:00:00", "mode": "practice",
            "overall_score": 7.5, "transcript": "the quick fox",
            "ai_summary": "good baseline", "recording_path": "/tmp/abc.wav",
            "pitch_score": 8, "volume_score": 7, "tempo_score": 9,
            "rhythm_score": 6, "pause_score": 8,
            "coach_provider": "gemini", "coach_status": "ok", "coach_error": None,
        } if sid == 42 else None,
    )
    response = client.get("/history/42")
    assert response.status_code == 200
    assert "the quick fox" in response.text
    assert "good baseline" in response.text


def test_history_detail_404_for_unknown(client, monkeypatch):
    monkeypatch.setattr("web.routes.history.get_session", lambda sid: None)
    response = client.get("/history/999")
    assert response.status_code == 404


def test_stats_page_renders_chart_data(client, monkeypatch):
    # Real get_stats() shape: averages dict + recent_trend delta + totals.
    monkeypatch.setattr(
        "web.routes.history.get_stats",
        lambda days=30: {
            "total_sessions": 12,
            "total_practice_time": 5.4,
            "averages": {"pitch": 7.0, "volume": 8.0, "tempo": 7.0,
                         "rhythm": 6.0, "pause": 8.0, "overall": 7.2},
            "recent_trend": 0.4,
        },
    )
    # Real get_best_and_worst() shape: tuples of (component, score).
    monkeypatch.setattr(
        "web.routes.history.get_best_and_worst",
        lambda: {"best": ("volume", 8.0), "worst": ("rhythm", 6.0)},
    )
    response = client.get("/history/stats")
    assert response.status_code == 200
    assert "canvas" in response.text   # bar chart present
    assert "12" in response.text       # total sessions
    assert "volume" in response.text   # best component name
    assert "rhythm" in response.text   # worst component name


def test_stats_page_handles_empty_database(client, monkeypatch):
    """Fresh DB returns averages=None; the page must render, not 500."""
    monkeypatch.setattr(
        "web.routes.history.get_stats",
        lambda days=30: {
            "total_sessions": 0, "total_practice_time": 0,
            "averages": None, "recent_trend": None,
        },
    )
    monkeypatch.setattr(
        "web.routes.history.get_best_and_worst",
        lambda: {"best": None, "worst": None},
    )
    response = client.get("/history/stats")
    assert response.status_code == 200
    assert "No sessions yet" in response.text
    assert "canvas" not in response.text  # chart is gated on has_data
