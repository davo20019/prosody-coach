"""Read-only settings/system info page."""

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from config import COACH_PROVIDER, GEMINI_API_KEY
from local_coach import LocalCoachConfig, diagnose_local_setup

router = APIRouter()


@router.get("/settings", response_class=HTMLResponse)
def settings_index(request: Request) -> HTMLResponse:
    checks = diagnose_local_setup()
    has_gemini_key = bool(GEMINI_API_KEY)
    local_ready = all(c.ok for c in checks) if checks else False
    needs_warning = (COACH_PROVIDER == "gemini" and not has_gemini_key) or (
        COACH_PROVIDER == "local" and not local_ready
    )
    local_config = LocalCoachConfig.from_env()
    templates = request.app.state.templates
    return templates.TemplateResponse(
        "pages/settings.html",
        {
            "request": request,
            "provider": COACH_PROVIDER,
            "has_gemini_key": has_gemini_key,
            "checks": checks,
            "needs_warning": needs_warning,
            "local_config": local_config,
        },
    )
