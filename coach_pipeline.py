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
        "content_feedback": getattr(coaching, "content_feedback", None),
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


@dataclass
class FrameworkSessionResult:
    """Outcome of a framework practice attempt.

    `analysis` (aggregate prosody) is always present. `transcript`, `structure`,
    `per_slot_prosody`, `overall_score`, `passed` are populated when scoring
    succeeds. `status='failed'` means scoring or transcription raised; the
    aggregate prosody is still returned.
    """
    analysis: Any
    transcript: Optional[Any]                     # local_coach.Transcript
    structure: Optional[Any]                      # framework_scoring.FrameworkScore
    per_slot_prosody: Optional[dict]              # {slot_id: ProsodyAnalysis | None}
    per_slot_prosody_available: bool
    overall_score: float
    passed: bool
    provider: str
    status: str                                   # 'ok' | 'failed'
    error: Optional[str]
    model_answer: Optional[Any] = None            # framework_scoring.ModelAnswer or None


def _get_transcript_for_framework(
    audio_data: np.ndarray,
    sample_rate: int,
    *,
    audio_path: Optional[Path],
    provider: str,
):
    """Pick a transcript source and return a Transcript.

    Policy:
      1. whisper-server if configured (gives word timestamps).
      2. whisper-cli if configured AND provider == 'local' (no word timestamps).
         Skipped for Gemini provider because CLI buys nothing there.
      3. Gemini transcription for 'gemini' provider.
      4. Otherwise raise ConfigurationError.
    """
    from local_coach import (
        is_whisper_server_configured,
        is_whisper_cli_configured,
        WhisperServerTranscriber,
        WhisperCppTranscriber,
    )

    if is_whisper_server_configured():
        if audio_path is None:
            raise RuntimeError(
                "whisper-server transcription requires audio_path; got None."
            )
        return WhisperServerTranscriber().transcribe_with_timestamps(audio_path)

    if provider == "local" and is_whisper_cli_configured():
        if audio_path is None:
            raise RuntimeError(
                "whisper-cli transcription requires audio_path; got None."
            )
        return WhisperCppTranscriber().transcribe_with_timestamps(audio_path)

    if provider == "gemini":
        from coach import gemini_transcribe
        return gemini_transcribe(audio_data, sample_rate)

    raise RuntimeError(
        "No transcript source available. Configure LOCAL_WHISPER_SERVER_URL, "
        "or WHISPER_MODEL + WHISPER_CPP_BIN, or use --provider gemini."
    )


def analyze_framework_session(
    audio_data: np.ndarray,
    sample_rate: int,
    *,
    framework: dict,
    prompt: dict,
    provider: str,
    audio_path: Optional[Path],
) -> "FrameworkSessionResult":
    """Run a framework practice attempt: prosody + transcript + structure scoring.

    Always returns a result. If structure scoring or transcription fails, the
    aggregate prosody is still returned with status='failed'.
    """
    if provider not in _PROVIDERS:
        raise ValueError(f"Unknown provider: {provider!r}")

    analysis = analyze_prosody(audio_data, sample_rate, None, audio_path)

    try:
        transcript = _get_transcript_for_framework(
            audio_data, sample_rate,
            audio_path=audio_path, provider=provider,
        )
    except Exception as exc:
        return FrameworkSessionResult(
            analysis=analysis,
            transcript=None, structure=None,
            per_slot_prosody=None, per_slot_prosody_available=False,
            overall_score=0.0, passed=False,
            provider=provider, status="failed", error=f"transcription: {exc}",
        )

    try:
        from framework_scoring import (
            score_framework, compute_overall, resolve_slot_spans,
        )
        from analyzer import analyze_prosody_per_slot

        structure = score_framework(framework, transcript, provider=provider)
        overall, passed = compute_overall(structure, framework)

        per_slot_prosody = None
        per_slot_available = False
        if transcript.words:
            spans = resolve_slot_spans(structure, transcript)
            per_slot_prosody = analyze_prosody_per_slot(audio_data, sample_rate, spans)
            per_slot_available = True

        # Model-answer generation is best-effort: a failure here must not
        # invalidate the scoring/prosody result the learner just earned.
        model_answer = None
        try:
            from framework_scoring import generate_model_answer
            import logging
            model_answer = generate_model_answer(
                framework,
                transcript.text or "",
                (prompt or {}).get("text", ""),
                provider=provider,
            )
        except Exception as exc:
            logging.getLogger(__name__).warning(
                "Model-answer generation failed: %s", exc,
            )

        return FrameworkSessionResult(
            analysis=analysis,
            transcript=transcript, structure=structure,
            per_slot_prosody=per_slot_prosody,
            per_slot_prosody_available=per_slot_available,
            overall_score=overall, passed=passed,
            provider=provider, status="ok", error=None,
            model_answer=model_answer,
        )
    except Exception as exc:
        return FrameworkSessionResult(
            analysis=analysis,
            transcript=transcript, structure=None,
            per_slot_prosody=None, per_slot_prosody_available=False,
            overall_score=0.0, passed=False,
            provider=provider, status="failed", error=f"scoring: {exc}",
        )
