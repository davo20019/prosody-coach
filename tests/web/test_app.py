def test_app_factory_returns_fastapi_instance(app):
    from fastapi import FastAPI
    assert isinstance(app, FastAPI)


def test_health_endpoint_returns_ok(client):
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
