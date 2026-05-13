def test_prompts_page_lists_categories(client, monkeypatch):
    monkeypatch.setattr("web.routes.prompts.get_all_categories", lambda: ["stress", "intonation"])
    monkeypatch.setattr(
        "web.routes.prompts.get_prompts_by_category",
        lambda c: [{"id": f"{c}-1", "text": f"{c} prompt", "category": c}],
    )
    response = client.get("/prompts")
    assert response.status_code == 200
    assert "stress" in response.text
    assert "intonation" in response.text


def test_prompts_category_page_filters(client, monkeypatch):
    monkeypatch.setattr("web.routes.prompts.get_all_categories", lambda: ["stress"])
    monkeypatch.setattr(
        "web.routes.prompts.get_prompts_by_category",
        lambda c: [{"id": "s-1", "text": "STRESS PROMPT TEXT", "category": "stress"}],
    )
    response = client.get("/prompts/category/stress")
    assert response.status_code == 200
    assert "STRESS PROMPT TEXT" in response.text


def test_prompts_random_redirects_to_practice(client, monkeypatch):
    monkeypatch.setattr(
        "web.routes.prompts.get_random_prompt",
        lambda: {"id": "x-9", "text": "random one", "category": "stress"},
    )
    response = client.get("/prompts/random", follow_redirects=False)
    assert response.status_code in (302, 307)
    assert response.headers["location"] == "/practice?prompt_id=x-9"
