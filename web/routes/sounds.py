"""Sounds page: due-for-practice and tracked-sounds list."""

import html

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse

from storage import (
    get_all_tracked_sounds,
    get_due_sounds,
    update_sound_after_practice,
)

router = APIRouter()


@router.get("/sounds", response_class=HTMLResponse)
def sounds_index(request: Request) -> HTMLResponse:
    due = get_due_sounds(limit=10)
    tracked = get_all_tracked_sounds()
    templates = request.app.state.templates
    return templates.TemplateResponse(
        request,
        "pages/sounds.html",
        {"due": due, "tracked": tracked},
    )


@router.post("/sounds/{sound}/practice", response_class=HTMLResponse)
def practice_sound(sound: str, was_correct: str = Form("true")) -> HTMLResponse:
    update_sound_after_practice(sound, was_correct.lower() == "true")
    # `sound` is a URL path param — escape before echoing into HTML.
    return HTMLResponse(f"<span class='muted'>Recorded: {html.escape(sound)}</span>")
