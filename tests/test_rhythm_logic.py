from types import SimpleNamespace

from rich.console import Console


def test_rhythm_feedback_labels_ioi_target_range(monkeypatch):
    import feedback

    captured = Console(record=True, width=120)
    monkeypatch.setattr(feedback, "console", captured)

    result = SimpleNamespace(
        rhythm_score=7,
        stress_correct=True,
        stress_feedback="stress ok",
        function_reduction=True,
        reduction_feedback="reduction ok",
        technique_tip="",
        transcript="",
        stress_pattern="",
        linked="",
        linked_ipa="",
        word_stress_issues=None,
        timing_feedback="",
        encouragement="",
    )
    prosody = SimpleNamespace(
        rhythm=SimpleNamespace(
            pvi=48,
            pvi_type="ioi",
            pvi_ioi=48,
            pvi_vocalic=None,
            vowel_count=None,
        )
    )

    feedback.display_rhythm_feedback(
        result,
        prosody,
        level=2,
        passed=True,
        progress=(1, 3),
        show_details=True,
    )

    assert "target: 48-58" in captured.export_text()
