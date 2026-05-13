"""Browse practice prompts; pick one to load into Practice."""

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from prompts import (
    get_all_categories,
    get_prompts_by_category,
    get_random_prompt,
)

router = APIRouter()


@router.get("/prompts", response_class=HTMLResponse)
def list_prompts(request: Request) -> HTMLResponse:
    categories = get_all_categories()
    prompts_by_category = {c: get_prompts_by_category(c) for c in categories}
    templates = request.app.state.templates
    return templates.TemplateResponse(
        request,
        "pages/prompts.html",
        {"categories": categories, "prompts_by_category": prompts_by_category},
    )


@router.get("/prompts/category/{category}", response_class=HTMLResponse)
def list_category(request: Request, category: str) -> HTMLResponse:
    templates = request.app.state.templates
    return templates.TemplateResponse(
        request,
        "pages/prompts.html",
        {
            "categories": [category],
            "prompts_by_category": {category: get_prompts_by_category(category)},
        },
    )


@router.get("/prompts/random", include_in_schema=False)
def random_prompt() -> RedirectResponse:
    p = get_random_prompt()
    return RedirectResponse(url=f"/practice?prompt_id={p['id']}", status_code=307)
