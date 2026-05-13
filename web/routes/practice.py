"""Practice page — pick a prompt (or enter custom text), record, see results."""

from pathlib import Path
from typing import Optional
from uuid import uuid4

import soundfile as sf
from fastapi import APIRouter, File, Form, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse

from coach_pipeline import analyze_session
from config import COACH_PROVIDER, RECORDINGS_DIR
from prompts import get_prompt_by_id
from storage import save_session
from web.audio_io import TranscodeError, transcode_to_wav

router = APIRouter()


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


@router.post("/practice/analyze", response_class=HTMLResponse)
async def analyze(
    request: Request,
    audio: UploadFile = File(...),
    mode: str = Form("analyze"),
    prompt_id: Optional[str] = Form(None),
    expected_text: Optional[str] = Form(None),
    custom_text: Optional[str] = Form(None),
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
    save_session(
        result.analysis,
        mode=mode,
        prompt_id=prompt_id,
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

    return templates.TemplateResponse(
        request,
        "partials/analysis_card.html",
        {
            "analysis": result.analysis,
            "coach": result.coach,
            "provider": result.provider,
            "error": result.error,
            "recording_name": recording_name,
        },
    )
