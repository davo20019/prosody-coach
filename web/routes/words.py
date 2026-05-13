"""Words page: due-for-practice list."""

import html

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse

from storage import get_due_words, update_word_after_practice

router = APIRouter()


@router.get("/words", response_class=HTMLResponse)
def words_index(request: Request) -> HTMLResponse:
    due = get_due_words(limit=10)
    templates = request.app.state.templates
    return templates.TemplateResponse(
        "pages/words.html", {"request": request, "due": due}
    )


@router.post("/words/{word}/practice", response_class=HTMLResponse)
def practice_word(word: str, was_correct: str = Form("true")) -> HTMLResponse:
    update_word_after_practice(word, was_correct.lower() == "true")
    # `word` is a URL path param — escape before echoing into HTML.
    return HTMLResponse(f"<span class='muted'>Recorded: {html.escape(word)}</span>")
