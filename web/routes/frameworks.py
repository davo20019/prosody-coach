"""Communication-framework practice page and endpoints.

Mirrors web/routes/drills.py: an index page (`/frameworks`) plus a per-prompt
run page (`/frameworks/{framework}`), with a POST endpoint that records
attempts and renders the result partial inline.
"""

from pathlib import Path
from typing import Optional
from uuid import uuid4

import soundfile as sf
from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse

from config import COACH_PROVIDER, RECORDINGS_DIR
from coach_pipeline import analyze_framework_session
from frameworks import FRAMEWORKS, get_framework, get_prompt, list_frameworks
from framework_scoring import generate_prompt
from storage import (
    get_due_framework_prompts,
    get_framework_progress,
    save_framework_attempt,
)
from web.audio_io import TranscodeError, transcode_to_wav

router = APIRouter()


GENERATED_PROMPT_PREFIX = "generated:"


def _pick_next_prompt(framework: dict) -> Optional[dict]:
    """Pick the least-recently-practiced prompt for this framework.

    Order: prompts that have never been attempted first, then by
    `last_attempted` ascending (oldest first). Stable when ties occur (falls
    back to declaration order in `frameworks.py`).
    """
    prompts = framework.get("prompts") or []
    if not prompts:
        return None

    progress = get_framework_progress(framework["id"]) or {}
    prompt_progress = progress.get("prompt_progress", []) or []
    last_seen = {p["prompt_id"]: p.get("last_attempted") for p in prompt_progress}

    def sort_key(p):
        last = last_seen.get(p["id"])
        # Unseen prompts (no row in framework_prompt_progress) come first.
        return (0, "") if last is None else (1, last)

    return sorted(prompts, key=sort_key)[0]


def _enrich_due(due_rows: list[dict]) -> list[dict]:
    """Resolve prompt text/framework name for each due-row."""
    enriched = []
    for row in due_rows or []:
        framework_id = row.get("framework_id")
        prompt_id = row.get("prompt_id")
        framework = get_framework(framework_id) or {}
        prompt = get_prompt(framework_id, prompt_id) or {}
        enriched.append({
            "framework_id": framework_id,
            "framework_name": framework.get("name", framework_id),
            "prompt_id": prompt_id,
            "prompt_text": prompt.get("text", ""),
            "last_attempted": row.get("last_attempted"),
            "last_score": row.get("last_score"),
        })
    return enriched


@router.get("/frameworks", response_class=HTMLResponse)
def frameworks_index(request: Request) -> HTMLResponse:
    progress = get_framework_progress()  # {framework_id: {...}}
    due = _enrich_due(get_due_framework_prompts(limit=5))
    templates = request.app.state.templates
    return templates.TemplateResponse(
        request,
        "pages/frameworks.html",
        {
            "frameworks": list_frameworks(),
            "progress": progress,
            "due": due,
        },
    )


@router.get("/frameworks/{framework_id}", response_class=HTMLResponse)
def framework_run(
    request: Request,
    framework_id: str,
    prompt_id: Optional[str] = None,
) -> HTMLResponse:
    framework = get_framework(framework_id)
    if framework is None:
        raise HTTPException(status_code=404, detail=f"Unknown framework: {framework_id}")

    prompt = None
    if prompt_id:
        prompt = get_prompt(framework_id, prompt_id)
    if prompt is None:
        prompt = _pick_next_prompt(framework)
    if prompt is None:
        raise HTTPException(status_code=404, detail=f"No prompts for framework: {framework_id}")

    templates = request.app.state.templates
    return templates.TemplateResponse(
        request,
        "pages/framework_run.html",
        {"framework": framework, "prompt": prompt, "is_generated": False},
    )


@router.get("/frameworks/{framework_id}/generate", response_class=HTMLResponse)
def framework_generate(request: Request, framework_id: str) -> HTMLResponse:
    """Generate a one-shot AI prompt for this framework and render the run page.

    The prompt is ephemeral: practiced once, recorded in `sessions`, but never
    added to `framework_prompt_progress` (so it doesn't pollute spaced
    repetition with throwaway ids).
    """
    framework = get_framework(framework_id)
    if framework is None:
        raise HTTPException(status_code=404, detail=f"Unknown framework: {framework_id}")

    templates = request.app.state.templates
    try:
        text = generate_prompt(framework, provider=COACH_PROVIDER)
    except Exception as exc:
        return templates.TemplateResponse(
            request,
            "partials/error_banner.html",
            {"message": f"Could not generate a prompt: {exc}"},
        )

    prompt = {
        "id": f"{GENERATED_PROMPT_PREFIX}{uuid4().hex[:12]}",
        "text": text,
        "category": "ai-generated",
    }
    return templates.TemplateResponse(
        request,
        "pages/framework_run.html",
        {"framework": framework, "prompt": prompt, "is_generated": True},
    )


@router.post("/frameworks/attempt", response_class=HTMLResponse)
async def framework_attempt(
    request: Request,
    audio: UploadFile = File(...),
    framework_id: str = Form(...),
    prompt_id: str = Form(...),
    prompt_text: Optional[str] = Form(None),
) -> HTMLResponse:
    templates = request.app.state.templates

    framework = get_framework(framework_id)
    if framework is None:
        return templates.TemplateResponse(
            request,
            "partials/error_banner.html",
            {"message": f"Unknown framework: {framework_id}"},
        )

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

    # For curated prompts, look up via the catalog. For ephemeral AI-generated
    # ones (prompt_id starts with `generated:`), there is no catalog entry —
    # use the prompt_text the form passed through.
    is_ephemeral = prompt_id.startswith(GENERATED_PROMPT_PREFIX)
    if is_ephemeral:
        prompt = {"id": prompt_id, "text": prompt_text or "", "category": "ai-generated"}
    else:
        prompt = get_prompt(framework_id, prompt_id) or {
            "id": prompt_id, "text": prompt_text or "",
        }

    result = analyze_framework_session(
        audio_data, sr,
        framework=framework, prompt=prompt,
        provider=COACH_PROVIDER, audio_path=wav_path,
    )

    transcript_text = result.transcript.text if result.transcript else None

    # Persist even on partial failure so the prosody attempt is recoverable.
    save_framework_attempt(
        analysis=result.analysis,
        framework_id=framework_id,
        prompt_id=prompt_id,
        structure=result.structure,
        per_slot_prosody=result.per_slot_prosody,
        overall_score=result.overall_score,
        passed=result.passed,
        transcript=transcript_text,
        recording_path=str(wav_path),
        coach_provider=COACH_PROVIDER,
        coach_status=result.status,
        coach_error=result.error,
    )

    return templates.TemplateResponse(
        request,
        "partials/framework_result.html",
        {
            "framework": framework,
            "prompt": prompt,
            "analysis": result.analysis,
            "structure": result.structure,
            "per_slot_prosody": result.per_slot_prosody,
            "per_slot_prosody_available": result.per_slot_prosody_available,
            "overall_score": result.overall_score,
            "passed": result.passed,
            "pass_label": "PASS" if result.passed else "Keep practicing",
            "transcript_text": transcript_text,
            "recording_name": recording_name,
            "provider": COACH_PROVIDER,
            "status": result.status,
            "error": result.error,
            "model_answer": result.model_answer,
        },
    )
