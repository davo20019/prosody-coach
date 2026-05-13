"""Rhythm drills page and endpoints.

Uses the existing rhythm-coaching primitives from coach.py and the rhythm
progress storage from storage.py. Pass criterion mirrors the CLI
(main.py:1299-1311): when AI rhythm coaching ran (Gemini path), trust
rhythm_result.level_passed; otherwise apply the measured rule —
prosody.rhythm.score >= level_config['min_rhythm_score'] AND nPVI >=
level_config['npvi_target']. Both config keys are scalars in
config.RHYTHM_LEVEL_CONFIG[level], surfaced via progress.levels[level].config.
Mastery evaluation (evaluate_mastery_with_ai) is out of v1 scope.
"""

from pathlib import Path
from typing import Optional
from uuid import uuid4

import soundfile as sf
from fastapi import APIRouter, File, Form, Request, UploadFile
from fastapi.responses import HTMLResponse

from analyzer import analyze_prosody
from config import COACH_PROVIDER, RECORDINGS_DIR
from prompts import get_random_rhythm_drill, get_rhythm_drill
from storage import (
    get_available_levels,
    get_due_rhythm_drills,
    get_rhythm_progress,
    save_rhythm_drill_attempt,
    save_session,
    set_rhythm_baseline,
    update_rhythm_progress,
)
from web.audio_io import TranscodeError, transcode_to_wav

router = APIRouter()


def _passed(prosody, level_config: dict, ai_rhythm_result=None) -> bool:
    """Per-level pass criterion. Mirrors main.py:1299-1311 in the CLI.

    Only the Gemini path returns a RhythmCoachingResult with `level_passed` —
    the local path returns a plain CoachingResult, which has no such field.
    Use AI judgment ONLY when the field is actually present; otherwise fall
    back to the measured rule (rhythm score >= min_rhythm_score AND nPVI >=
    npvi_target). Both config keys are scalars in RHYTHM_LEVEL_CONFIG[level].
    """
    if ai_rhythm_result is not None and hasattr(ai_rhythm_result, "level_passed"):
        return bool(ai_rhythm_result.level_passed)
    npvi_target = level_config.get("npvi_target", 45)
    min_rhythm = level_config.get("min_rhythm_score", 5)
    npvi = getattr(prosody.rhythm, "pvi", 0)
    return prosody.rhythm.score >= min_rhythm and npvi >= npvi_target


def _enrich_due(due_rows: list[dict]) -> list[dict]:
    """Resolve drill text/focus/technique for each due-rhythm-drill row.

    Storage's get_due_rhythm_drills() returns rows from the rhythm_drills
    table — drill_id, level, last_attempted, etc. — but no text. CLI
    main.py:1225 resolves a due drill_id via prompts.get_rhythm_drill().
    Mirror that here so the page can show what the user is being asked to read.
    """
    enriched = []
    for row in due_rows or []:
        drill = get_rhythm_drill(row.get("drill_id", "")) or {}
        enriched.append({
            "drill_id": row.get("drill_id"),
            "level": row.get("level"),
            "last_attempted": row.get("last_attempted") or row.get("last_practiced"),
            "text": drill.get("text", ""),
            "focus": drill.get("focus", ""),
        })
    return enriched


@router.get("/drills", response_class=HTMLResponse)
def drills_index(request: Request) -> HTMLResponse:
    levels = get_available_levels()
    progress = get_rhythm_progress()
    due = _enrich_due(get_due_rhythm_drills(limit=5))
    templates = request.app.state.templates
    return templates.TemplateResponse(
        "pages/drills.html",
        {"request": request, "levels": levels, "progress": progress, "due": due},
    )


@router.get("/drills/level/{level}", response_class=HTMLResponse)
def drill_run(
    request: Request,
    level: int,
    drill_id: Optional[str] = None,
) -> HTMLResponse:
    """Run a specific drill if drill_id is supplied (clicking a due-drill row);
    otherwise pick a random drill from the level."""
    drill = None
    if drill_id:
        drill = get_rhythm_drill(drill_id)
    if drill is None:
        drill = get_random_rhythm_drill(level)
    templates = request.app.state.templates
    return templates.TemplateResponse(
        "pages/drill_run.html", {"request": request, "drill": drill}
    )


@router.post("/drills/baseline", response_class=HTMLResponse)
def baseline(npvi: float = Form(...)) -> HTMLResponse:
    set_rhythm_baseline(npvi)
    return HTMLResponse(f"<p>Baseline set to {npvi:.1f}</p>")


@router.post("/drills/attempt", response_class=HTMLResponse)
async def attempt(
    request: Request,
    audio: UploadFile = File(...),
    drill_id: str = Form(...),
    level: int = Form(...),
    expected_text: Optional[str] = Form(""),
    drill_focus: str = Form(""),
    drill_technique: str = Form(""),
    mode: str = Form("drill"),
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
            "partials/error_banner.html",
            {"request": request, "message": f"Audio could not be processed. {exc}"},
        )
    finally:
        tmp_in.unlink(missing_ok=True)

    audio_data, sr = sf.read(wav_path, dtype="float32")

    # 1) Analyze prosody (with expected text for forced alignment).
    try:
        prosody = analyze_prosody(audio_data, sr, expected_text or None, wav_path)
    except Exception as exc:
        return templates.TemplateResponse(
            "partials/error_banner.html",
            {"request": request, "message": f"Audio analysis failed: {exc}"},
        )

    # 2) Run rhythm-specific AI coaching (Gemini path; the local provider has
    #    no rhythm-specialized prompt today, so we fall back to the standard
    #    coach for it).
    coach_status = "ok"
    coach_error: Optional[str] = None
    rhythm_coaching = None
    try:
        if COACH_PROVIDER == "gemini":
            from coach import analyze_rhythm_with_coach
            rhythm_coaching = analyze_rhythm_with_coach(
                audio_data, sr, prosody,
                expected_text=expected_text or "",
                level=level,
                drill_focus=drill_focus,
                drill_technique=drill_technique,
            )
        else:
            from local_coach import analyze_with_local_coach
            rhythm_coaching = analyze_with_local_coach(
                audio_data, sr, prosody,
                audio_path=wav_path, expected_text=expected_text or "",
            )
    except Exception as exc:
        coach_status = "failed"
        coach_error = str(exc)

    # 3) Normalize coaching output. Two possible shapes reach this code:
    #      - RhythmCoachingResult (Gemini path): rhythm_score, level_passed,
    #        encouragement, technique_tip
    #      - CoachingResult (local fallback path): coaching_tips, overall_feedback
    #    Build a single dict the template + save_session can use, AND extract
    #    the AI's rhythm score when available so the right number gets saved.
    if rhythm_coaching is None:
        coach_for_template = None
        ai_rhythm_score = None
        ai_summary = None
        ai_tips = None
    elif hasattr(rhythm_coaching, "level_passed"):
        # RhythmCoachingResult (Gemini path).
        ai_rhythm_score = getattr(rhythm_coaching, "rhythm_score", None)
        ai_summary = getattr(rhythm_coaching, "encouragement", None)
        tip = getattr(rhythm_coaching, "technique_tip", "")
        ai_tips = [tip] if tip else None
        coach_for_template = {
            "transcript": getattr(rhythm_coaching, "transcript", None),
            "summary": ai_summary,
            "tips": ai_tips or [],
        }
    else:
        # CoachingResult (local path) — different attribute names.
        ai_rhythm_score = None  # local path doesn't compute one
        ai_summary = getattr(rhythm_coaching, "overall_feedback", None)
        ai_tips = list(getattr(rhythm_coaching, "coaching_tips", []) or [])
        coach_for_template = {
            "transcript": getattr(rhythm_coaching, "transcript", None),
            "summary": ai_summary,
            "tips": ai_tips,
        }

    # 4) Determine pass; persist progress. Use AI rhythm score when available;
    #    otherwise the measured score. Mirrors main.py:1306,1380 in the CLI.
    progress = get_rhythm_progress()
    level_config = (progress.get("levels") or {}).get(level, {}).get("config", {})
    passed = _passed(prosody, level_config, ai_rhythm_result=rhythm_coaching)
    npvi = getattr(prosody.rhythm, "pvi", 0)
    persisted_rhythm = ai_rhythm_score if ai_rhythm_score is not None else prosody.rhythm.score
    update_rhythm_progress(level=level, npvi=npvi, rhythm_score=persisted_rhythm, passed=passed)
    save_rhythm_drill_attempt(
        drill_id=drill_id, level=level,
        npvi=npvi, rhythm_score=persisted_rhythm, passed=passed,
    )

    # 5) Persist the session row.
    save_session(
        prosody,
        mode=mode,
        prompt_id=drill_id,
        recording_path=str(wav_path),
        transcript=(coach_for_template or {}).get("transcript"),
        ai_summary=ai_summary,
        ai_tips=ai_tips,
        coach_provider=COACH_PROVIDER,
        coach_status=coach_status,
        coach_error=coach_error,
    )

    # 6) Render analysis_card with pass/fail context. The template displays a
    #    PASS or "Keep practicing" badge when `passed` is provided.
    return templates.TemplateResponse(
        "partials/analysis_card.html",
        {
            "request": request,
            "analysis": prosody,
            "coach": coach_for_template,
            "provider": COACH_PROVIDER,
            "error": coach_error,
            "recording_name": recording_name,
            "passed": passed,
            "pass_label": "PASS" if passed else "Keep practicing",
        },
    )
