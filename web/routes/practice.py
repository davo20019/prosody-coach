"""Practice page — pick a prompt (or enter custom text), record, see results."""

from typing import Optional

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from prompts import get_prompt_by_id

router = APIRouter()


@router.get("/", include_in_schema=False)
def root() -> RedirectResponse:
    return RedirectResponse(url="/practice", status_code=307)


@router.get("/practice", response_class=HTMLResponse)
def get_practice(request: Request, prompt_id: Optional[str] = None) -> HTMLResponse:
    prompt = get_prompt_by_id(prompt_id) if prompt_id else None
    templates = request.app.state.templates
    return templates.TemplateResponse(
        "pages/practice.html",
        {"request": request, "prompt": prompt},
    )
