"""Practice page — pick a prompt (or enter custom text), record, see results."""

from pathlib import Path
from typing import Any, Optional
from uuid import uuid4

import soundfile as sf
from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse

from coach import generate_tailored_prompt
from coach_pipeline import analyze_session
from config import COACH_PROVIDER, RECORDINGS_DIR
from prompts import get_prompt_by_id, get_random_prompt
from storage import (
    get_due_words,
    get_session,
    save_session,
    update_sound_after_practice,
    update_word_after_practice,
)
from web.audio_io import TranscodeError, transcode_to_wav
from web.spaced_repetition import update_practiced_due_words, update_practiced_target_sounds

router = APIRouter()


# Sidebar order matches main.py's component naming; storage uses "pause"
# (singular). _COMPONENT_KEYS maps display-friendly names to session column
# bases, in the order generate_tailored_prompt expects.
_COMPONENT_KEYS = ("pitch", "volume", "tempo", "rhythm", "pause")


def _session_to_weaknesses(session: dict) -> dict:
    """Build a weaknesses dict from a single session's analysis.

    `coach.generate_tailored_prompt` expects the same shape that
    `storage.get_user_weaknesses` produces from history (focus_areas,
    difficulty, recurring_sounds). Here we synthesize that shape from one
    session so the LLM can focus the new prompt on this session's specific
    weak components and pronunciation issues.
    """
    scores = {c: session.get(f"{c}_score") or 0 for c in _COMPONENT_KEYS}
    # Pick the two lowest-scoring components.
    weakest = sorted(scores.items(), key=lambda kv: kv[1])[:2]

    focus_areas: list[dict[str, Any]] = []
    for area, score in weakest:
        focus_areas.append({
            "type": "prosody",
            "area": area,
            "score": score,
            "description": f"Improve {area} (this session: {score}/10)",
        })

    # Surface pronunciation issues if the AI flagged any.
    pron_issues = session.get("pronunciation_issues") or []
    recurring_sounds: list[tuple] = []
    seen: set[str] = set()
    for issue in pron_issues:
        sound = (issue or {}).get("sound", "")
        if sound and sound not in seen:
            seen.add(sound)
            recurring_sounds.append((sound, 1))
            focus_areas.append({
                "type": "pronunciation",
                "sound": sound,
                "occurrences": 1,
                "description": f"Practice '{sound}' sound (flagged in this session)",
            })

    overall = sum(scores.values()) / len(scores) if scores else 5
    if overall >= 7:
        difficulty = "advanced"
    elif overall >= 5:
        difficulty = "intermediate"
    else:
        difficulty = "beginner"

    return {
        "sufficient_data": True,
        "session_count": 1,
        "focus_areas": focus_areas,
        "difficulty": difficulty,
        "recurring_sounds": recurring_sounds,
    }


@router.get("/", include_in_schema=False)
def root() -> RedirectResponse:
    return RedirectResponse(url="/practice", status_code=307)


@router.get("/practice", response_class=HTMLResponse)
def get_practice(request: Request, prompt_id: Optional[str] = None) -> HTMLResponse:
    prompt = get_prompt_by_id(prompt_id) if prompt_id else None
    templates = request.app.state.templates
    return templates.TemplateResponse(
        request,
        "pages/practice.html",
        {"prompt": prompt},
    )


@router.get("/practice/followup/{sid}", response_class=HTMLResponse)
def practice_followup(request: Request, sid: int) -> HTMLResponse:
    """Load the Practice page with an AI-generated sentence that targets the
    weaknesses surfaced in session `sid`.

    Falls back to a random prompt if generation fails (no API key, parse
    error, etc.) — same pattern as the Train page.
    """
    session = get_session(sid)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")

    weaknesses = _session_to_weaknesses(session)
    try:
        prompt = generate_tailored_prompt(weaknesses)
        prompt_source = "followup"
    except Exception:
        prompt = get_random_prompt()
        prompt_source = "fallback"

    templates = request.app.state.templates
    return templates.TemplateResponse(
        request,
        "pages/practice.html",
        {
            "prompt": prompt,
            "prompt_source": prompt_source,
            "followup_session_id": sid,
        },
    )


@router.post("/practice/analyze", response_class=HTMLResponse)
async def analyze(
    request: Request,
    audio: UploadFile = File(...),
    mode: str = Form("analyze"),
    prompt_id: Optional[str] = Form(None),
    expected_text: Optional[str] = Form(None),
    custom_text: Optional[str] = Form(None),
    target_sounds: Optional[list[str]] = Form(None),
) -> HTMLResponse:
    templates = request.app.state.templates

    # 1) Save the uploaded blob to a tmp file.
    tmp_in = Path(RECORDINGS_DIR) / f"{uuid4().hex}.in"
    tmp_in.write_bytes(await audio.read())

    # 2) Transcode to UUID-named WAV inside RECORDINGS_DIR.
    recording_name = f"{uuid4().hex}.wav"
    wav_path = Path(RECORDINGS_DIR) / recording_name
    try:
        transcode_to_wav(tmp_in, wav_path)
    except TranscodeError as exc:
        tmp_in.unlink(missing_ok=True)
        return templates.TemplateResponse(
            request,
            "partials/error_banner.html",
            {
                "message": f"Audio could not be processed. Is ffmpeg installed? Run `prosody local doctor`. (Detail: {exc})",
            },
        )
    finally:
        tmp_in.unlink(missing_ok=True)

    # 3) Load WAV, run analysis + coach. Praat failures (parselmouth raises
    #    on degenerate audio) bubble out of analyze_session — catch and render
    #    an error banner per the spec's "Praat failure → surface the
    #    parselmouth exception text" rule.
    audio_data, sample_rate = sf.read(wav_path, dtype="float32")
    expected = expected_text or custom_text
    try:
        result = analyze_session(
            audio_data, sample_rate,
            expected_text=expected,
            mode=mode,
            provider=COACH_PROVIDER,
            audio_path=wav_path,
        )
    except Exception as exc:
        return templates.TemplateResponse(
            request,
            "partials/error_banner.html",
            {"message": f"Audio analysis failed: {exc}"},
        )

    # 4) Persist (recording first on disk, row references it by path).
    coach = result.coach or {}
    sid = save_session(
        result.analysis,
        mode=mode,
        prompt_id=prompt_id,
        recording_path=str(wav_path),
        transcript=coach.get("transcript"),
        ai_summary=coach.get("summary"),
        ai_tips=coach.get("tips"),
        grammar_issues=coach.get("grammar_issues"),
        suggested_revision=coach.get("suggested_revision"),
        content_feedback=coach.get("content_feedback"),
        confidence_score=coach.get("confidence_score"),
        confidence_feedback=coach.get("confidence_feedback"),
        filler_word_count=coach.get("filler_word_count"),
        filler_words_detail=coach.get("filler_words_detail"),
        pronunciation_issues=coach.get("pronunciation_issues"),
        fluency_score=coach.get("fluency_score"),
        fluency_feedback=coach.get("fluency_feedback"),
        coach_provider=result.provider,
        coach_status=result.status,
        coach_error=result.error,
    )
    if result.status == "ok":
        update_practiced_due_words(
            expected,
            coach.get("pronunciation_issues"),
            get_due_words,
            update_word_after_practice,
        )
        update_practiced_target_sounds(
            target_sounds,
            coach.get("pronunciation_issues"),
            update_sound_after_practice,
        )

    return templates.TemplateResponse(
        request,
        "partials/analysis_card.html",
        {
            "analysis": result.analysis,
            "coach": result.coach,
            "provider": result.provider,
            "error": result.error,
            "recording_name": recording_name,
            "session_id": sid,
            "mode": mode,
            "grammar_issues": (coach or {}).get("grammar_issues") or [],
            "suggested_revision": (coach or {}).get("suggested_revision"),
            "content_feedback": (coach or {}).get("content_feedback"),
        },
    )
