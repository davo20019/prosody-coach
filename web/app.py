"""FastAPI application factory for the Prosody Coach web UI."""

from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

WEB_DIR = Path(__file__).parent
STATIC_DIR = WEB_DIR / "static"
TEMPLATES_DIR = WEB_DIR / "templates"


def create_app() -> FastAPI:
    app = FastAPI(title="Prosody Coach", docs_url=None, redoc_url=None)

    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
    app.state.templates = Jinja2Templates(directory=TEMPLATES_DIR)

    from web.routes import audio, history, practice, prompts
    app.include_router(audio.router)
    app.include_router(practice.router)
    app.include_router(prompts.router)
    app.include_router(history.router)

    @app.get("/healthz")
    def healthz() -> dict:
        return {"status": "ok"}

    return app
