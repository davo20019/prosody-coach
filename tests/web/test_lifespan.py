from fastapi.testclient import TestClient


def test_init_db_called_at_startup(monkeypatch):
    called = []
    monkeypatch.setattr("web.app.init_db", lambda: called.append(True))
    from web.app import create_app
    app = create_app()
    with TestClient(app) as client:
        client.get("/healthz")
    assert called == [True]
