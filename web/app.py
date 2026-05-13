"""FastAPI application factory for the Prosody Coach web UI."""

from fastapi import FastAPI


def create_app() -> FastAPI:
    app = FastAPI(title="Prosody Coach", docs_url=None, redoc_url=None)

    @app.get("/healthz")
    def healthz() -> dict:
        return {"status": "ok"}

    return app
