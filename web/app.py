"""FastAPI application factory for the Prosody Coach web UI."""

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from storage import init_db

WEB_DIR = Path(__file__).parent
STATIC_DIR = WEB_DIR / "static"
TEMPLATES_DIR = WEB_DIR / "templates"


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


def create_app() -> FastAPI:
    app = FastAPI(title="Prosody Coach", docs_url=None, redoc_url=None, lifespan=lifespan)

    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
    app.state.templates = Jinja2Templates(directory=TEMPLATES_DIR)

    from web.routes import (
        audio, drills, frameworks, history, practice, prompts, settings, sounds, train, words,
    )
    app.include_router(audio.router)
    app.include_router(practice.router)
    app.include_router(prompts.router)
    app.include_router(history.router)
    app.include_router(drills.router)
    app.include_router(frameworks.router)
    app.include_router(sounds.router)
    app.include_router(words.router)
    app.include_router(train.router)
    app.include_router(settings.router)

    @app.get("/healthz")
    def healthz() -> dict:
        return {"status": "ok"}

    return app
