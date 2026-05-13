"""Tailored training picks AI-generated prompts using recent weaknesses."""

from pathlib import Path
from typing import Optional
from uuid import uuid4

import soundfile as sf
from fastapi import APIRouter, File, Form, Request, UploadFile
from fastapi.responses import HTMLResponse

from coach import generate_tailored_prompt
from coach_pipeline import analyze_session
from config import COACH_PROVIDER, RECORDINGS_DIR
from prompts import get_random_prompt
from storage import (
    get_due_sounds,
    get_due_words,
    get_user_weaknesses,
    save_session,
    update_sound_after_practice,
    update_word_after_practice,
)
from web.audio_io import TranscodeError, transcode_to_wav
from web.spaced_repetition import update_practiced_due_words, update_practiced_target_sounds

router = APIRouter()


@router.get("/train", response_class=HTMLResponse)
def train_index(request: Request) -> HTMLResponse:
    weaknesses = get_user_weaknesses(limit=10)
    due_sounds = get_due_sounds(limit=5)
    due_words = get_due_words(limit=5)
    try:
        prompt = generate_tailored_prompt(weaknesses, due_sounds=due_sounds, due_words=due_words)
        prompt_source = "tailored"
    except Exception:
        # Generation can fail for several reasons (no API key, network error,
        # parse failure). The CLI also handles this — fall back to a random
        # built-in prompt so the page is still usable.
        prompt = get_random_prompt()
        prompt_source = "fallback"

    templates = request.app.state.templates
    return templates.TemplateResponse(
        request,
        "pages/train.html",
        {
            "prompt": prompt,
            "prompt_source": prompt_source,
            "weaknesses": weaknesses,
        },
    )


@router.post("/train/analyze", response_class=HTMLResponse)
async def analyze(
    request: Request,
    audio: UploadFile = File(...),
    prompt_id: Optional[str] = Form(None),
    expected_text: Optional[str] = Form(None),
    target_sounds: Optional[list[str]] = Form(None),
    mode: str = Form("train"),
) -> HTMLResponse:
    templates = request.app.state.templates
    tmp_in = Path(RECORDINGS_DIR) / f"{uuid4().hex}.in"
    tmp_in.write_bytes(await audio.read())
    recording_name = f"{uuid4().hex}.wav"
    wav_path = Path(RECORDINGS_DIR) / recording_name
    try:
        transcode_to_wav(tmp_in, wav_path)
    except TranscodeError as exc:
        tmp_in.unlink(missing_ok=True)
        return templates.TemplateResponse(
            request,
            "partials/error_banner.html",
            {"message": f"Audio could not be processed. {exc}"},
        )
    finally:
        tmp_in.unlink(missing_ok=True)

    audio_data, sr = sf.read(wav_path, dtype="float32")
    try:
        result = analyze_session(
            audio_data, sr,
            expected_text=expected_text, mode=mode,
            provider=COACH_PROVIDER, audio_path=wav_path,
        )
    except Exception as exc:
        return templates.TemplateResponse(
            request,
            "partials/error_banner.html",
            {"message": f"Audio analysis failed: {exc}"},
        )
    coach = result.coach or {}
    # Mirror the practice route's full field list so train sessions also feed
    # pronunciation/grammar/filler-word/confidence spaced repetition.
    sid = save_session(
        result.analysis,
        mode=mode, prompt_id=prompt_id,
        recording_path=str(wav_path),
        transcript=coach.get("transcript"),
        ai_summary=coach.get("summary"),
        ai_tips=coach.get("tips"),
        grammar_issues=coach.get("grammar_issues"),
        suggested_revision=coach.get("suggested_revision"),
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
            expected_text,
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
            "analysis": result.analysis, "coach": result.coach,
            "provider": result.provider, "error": result.error,
            "recording_name": recording_name,
            "session_id": sid,
        },
    )
