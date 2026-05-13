"""History list, detail, and stats pages."""

from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse

from storage import get_best_and_worst, get_history, get_session, get_stats

router = APIRouter()


@router.get("/history", response_class=HTMLResponse)
def list_history(request: Request, mode: Optional[str] = None) -> HTMLResponse:
    sessions = get_history(limit=50, mode=mode)
    templates = request.app.state.templates
    return templates.TemplateResponse(
        "pages/history.html",
        {"request": request, "sessions": sessions, "mode_filter": mode},
    )


@router.get("/history/stats", response_class=HTMLResponse)
def stats_page(request: Request) -> HTMLResponse:
    stats = get_stats(days=30)
    bw = get_best_and_worst()
    # get_stats returns averages=None on a fresh database (zero sessions);
    # normalize to a zeros dict so template format strings don't blow up.
    averages = stats.get("averages") or {
        "pitch": 0.0, "volume": 0.0, "tempo": 0.0,
        "rhythm": 0.0, "pause": 0.0, "overall": 0.0,
    }
    component_labels = ["pitch", "volume", "tempo", "rhythm", "pause"]
    component_values = [averages.get(c, 0) for c in component_labels]
    best = bw.get("best") or ("-", 0.0)
    worst = bw.get("worst") or ("-", 0.0)
    templates = request.app.state.templates
    return templates.TemplateResponse(
        "pages/stats.html",
        {
            "request": request,
            "stats": stats,
            "averages": averages,
            "has_data": stats.get("total_sessions", 0) > 0,
            "component_labels": component_labels,
            "component_values": component_values,
            "best_component": best[0],
            "best_score": best[1],
            "worst_component": worst[0],
            "worst_score": worst[1],
        },
    )


@router.get("/history/{sid}", response_class=HTMLResponse)
def session_detail(request: Request, sid: int) -> HTMLResponse:
    session = get_session(sid)
    if session is None:
        raise HTTPException(status_code=404)
    recording_name = None
    if session.get("recording_path"):
        recording_name = Path(session["recording_path"]).name
    templates = request.app.state.templates
    return templates.TemplateResponse(
        "pages/history_detail.html",
        {"request": request, "session": session, "recording_name": recording_name},
    )
