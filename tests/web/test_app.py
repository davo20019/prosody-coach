def test_app_factory_returns_fastapi_instance(app):
    from fastapi import FastAPI
    assert isinstance(app, FastAPI)


def test_health_endpoint_returns_ok(client):
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_static_assets_are_served(client):
    response = client.get("/static/vendor/htmx.min.js")
    assert response.status_code == 200
    assert "function" in response.text  # JS sanity check


def test_static_css_is_served(client):
    response = client.get("/static/app.css")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/css")
