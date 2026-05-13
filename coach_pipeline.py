"""Provider-aware orchestrator that runs prosody analysis + AI coaching.

This is the single entry point used by the web layer (and, optionally, by the
CLI in the future). Wraps the existing Gemini and local paths behind one
signature so route handlers don't need to know which provider is in use.

Sequential, not concurrent: both Gemini's `analyze_with_coach` and the local
`analyze_with_local_coach` accept the prosody analysis as input, so they can
only start after `analyze_prosody` returns. The cost is ~0.5-1s of analyzer
time before the long-running AI call begins.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

import numpy as np

from analyzer import analyze_prosody


@dataclass
class SessionResult:
    """Outcome of a complete analysis pass.

    `analysis` is always present (Praat is local and reliable).
    `coach` is None when status == 'failed'.
    """
    analysis: Any
    coach: Optional[dict]
    provider: str
    status: str       # 'ok' | 'failed'
    error: Optional[str]


def _run_gemini(
    audio_data: np.ndarray,
    sample_rate: int,
    analysis: Any,
    *,
    expected_text: Optional[str] = None,
    audio_path: Optional[Path] = None,
) -> dict:
    """Call Gemini. Routes to the practice-mode prompt when expected_text is given."""
    if expected_text:
        from coach import analyze_with_coach_practice
        coaching = analyze_with_coach_practice(audio_data, sample_rate, analysis, expected_text)
    else:
        from coach import analyze_with_coach
        coaching = analyze_with_coach(audio_data, sample_rate, analysis)
    return _normalize_coaching(coaching)


def _run_local(
    audio_data: np.ndarray,
    sample_rate: int,
    analysis: Any,
    *,
    expected_text: Optional[str] = None,
    audio_path: Optional[Path] = None,
) -> dict:
    """Call the local whisper.cpp + llama.cpp path."""
    from local_coach import analyze_with_local_coach
    coaching = analyze_with_local_coach(
        audio_data, sample_rate, analysis,
        audio_path=audio_path, expected_text=expected_text,
    )
    return _normalize_coaching(coaching)


def _normalize_coaching(coaching: Any) -> dict:
    """Convert a CoachingResult into the flat dict the templates and storage use.

    The real attribute names on coach.CoachingResult are `coaching_tips` and
    `overall_feedback`; we surface them here as `tips` and `summary` for the
    rest of the web stack.
    """
    if coaching is None:
        return {}
    if isinstance(coaching, dict):
        return coaching
    return {
        "transcript": getattr(coaching, "transcript", None),
        "tips": list(getattr(coaching, "coaching_tips", []) or []),
        "summary": getattr(coaching, "overall_feedback", None),
        "grammar_issues": list(getattr(coaching, "grammar_issues", []) or []),
        "suggested_revision": getattr(coaching, "suggested_revision", None),
        "confidence_score": getattr(coaching, "confidence_score", None),
        "confidence_feedback": getattr(coaching, "confidence_feedback", None),
        "filler_word_count": getattr(coaching, "filler_word_count", None),
        "filler_words_detail": getattr(coaching, "filler_words_detail", None),
        "pronunciation_issues": list(getattr(coaching, "pronunciation_issues", []) or []),
        "fluency_score": getattr(coaching, "fluency_score", None),
        "fluency_feedback": getattr(coaching, "fluency_feedback", None),
    }


_PROVIDERS = {"gemini": "_run_gemini", "local": "_run_local"}


def analyze_session(
    audio_data: np.ndarray,
    sample_rate: int,
    *,
    expected_text: Optional[str],
    mode: str,
    provider: str,
    audio_path: Optional[Path],
) -> SessionResult:
    """Run prosody analysis, then AI coaching. Return one result.

    Sequential because both providers consume the analysis. If the coach call
    raises, we still return the prosody analysis with status='failed'.
    """
    if provider not in _PROVIDERS:
        raise ValueError(f"Unknown provider: {provider!r}")

    coach_fn = globals()[_PROVIDERS[provider]]
    analysis = analyze_prosody(audio_data, sample_rate, expected_text, audio_path)
    try:
        coach = coach_fn(
            audio_data, sample_rate, analysis,
            expected_text=expected_text, audio_path=audio_path,
        )
        return SessionResult(
            analysis=analysis, coach=coach,
            provider=provider, status="ok", error=None,
        )
    except Exception as exc:
        return SessionResult(
            analysis=analysis, coach=None,
            provider=provider, status="failed", error=str(exc),
        )
