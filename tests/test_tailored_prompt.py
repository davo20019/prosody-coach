from types import SimpleNamespace


def test_generate_tailored_prompt_parses_word_level_ipa(monkeypatch):
    import coach

    captured = {}

    class FakeModels:
        def generate_content(self, **kwargs):
            captured["prompt"] = kwargs["contents"][0].parts[0].text
            return SimpleNamespace(text="""
TEXT:
Although the findings improved.

KEY_SOUNDS:
although /ɔlˈðoʊ/, findings /ˈfaɪndɪŋz/

WORD_IPA:
Although /ɔlˈðoʊ/
the /ðə/
findings /ˈfaɪndɪŋz/
improved /ɪmˈpruːvd/
""")

    monkeypatch.setattr(
        coach,
        "get_client",
        lambda: SimpleNamespace(models=FakeModels()),
    )

    result = coach.generate_tailored_prompt(
        {
            "focus_areas": [
                {"type": "prosody", "area": "rhythm", "description": "Improve rhythm"},
            ],
            "difficulty": "intermediate",
        }
    )

    assert "WORD_IPA:" in captured["prompt"]
    assert result["word_ipa"] == [
        {"word": "Although", "ipa": "ɔlˈðoʊ"},
        {"word": "the", "ipa": "ðə"},
        {"word": "findings", "ipa": "ˈfaɪndɪŋz"},
        {"word": "improved.", "ipa": "ɪmˈpruːvd"},
    ]


def test_generate_tailored_prompt_ignores_malformed_word_ipa_lines(monkeypatch):
    import coach

    class FakeModels:
        def generate_content(self, **kwargs):
            return SimpleNamespace(text="""
TEXT:
Try this line.

KEY_SOUNDS:
try /traɪ/

WORD_IPA:
Try /traɪ/
missing slash
this //
line /laɪn/
""")

    monkeypatch.setattr(
        coach,
        "get_client",
        lambda: SimpleNamespace(models=FakeModels()),
    )

    result = coach.generate_tailored_prompt({"focus_areas": [], "difficulty": "beginner"})

    assert result["word_ipa"] == [
        {"word": "Try", "ipa": "traɪ"},
        {"word": "line.", "ipa": "laɪn"},
    ]


def test_generate_tailored_prompt_requires_context_sensitive_heteronym_ipa(monkeypatch):
    import coach

    captured = {}

    class FakeModels:
        def generate_content(self, **kwargs):
            captured["prompt"] = kwargs["contents"][0].parts[0].text
            return SimpleNamespace(text="""
TEXT:
The project will project confidence.

KEY_SOUNDS:
project /ˈprɑːdʒekt/, project /prəˈdʒekt/

WORD_IPA:
The /ðə/
project /ˈprɑːdʒekt/
will /wɪl/
project /prəˈdʒekt/
confidence /ˈkɑːnfɪdəns/
""")

    monkeypatch.setattr(
        coach,
        "get_client",
        lambda: SimpleNamespace(models=FakeModels()),
    )

    coach.generate_tailored_prompt({"focus_areas": [], "difficulty": "intermediate"})

    prompt = captured["prompt"]
    assert "context-sensitive" in prompt
    assert "heteronyms" in prompt
    assert "project (noun)" in prompt
    assert "/ˈprɑːdʒekt/" in prompt
    assert "project (verb)" in prompt
    assert "/prəˈdʒekt/" in prompt


def test_generate_tailored_prompt_preserves_sentence_punctuation_in_word_ipa(monkeypatch):
    import coach

    captured = {}

    class FakeModels:
        def generate_content(self, **kwargs):
            captured["prompt"] = kwargs["contents"][0].parts[0].text
            return SimpleNamespace(text="""
TEXT:
The project improved. We agree.

KEY_SOUNDS:
project /ˈprɑːdʒekt/, improved /ɪmˈpruːvd/

WORD_IPA:
The /ðə/
project /ˈprɑːdʒekt/
improved /ɪmˈpruːvd/
We /wi/
agree /əˈɡri/
""")

    monkeypatch.setattr(
        coach,
        "get_client",
        lambda: SimpleNamespace(models=FakeModels()),
    )

    result = coach.generate_tailored_prompt({"focus_areas": [], "difficulty": "intermediate"})

    assert [item["word"] for item in result["word_ipa"]] == [
        "The",
        "project",
        "improved.",
        "We",
        "agree.",
    ]
    assert "visible punctuation" in captured["prompt"]
    assert "sentence boundaries" in captured["prompt"]


def test_generate_tailored_prompt_parses_connected_speech_chunks(monkeypatch):
    import coach

    captured = {}

    class FakeModels:
        def generate_content(self, **kwargs):
            captured["prompt"] = kwargs["contents"][0].parts[0].text
            captured["config"] = kwargs["config"]
            return SimpleNamespace(text="""
TEXT:
I think the weather will be warm.

KEY_SOUNDS:
think /θɪŋk/, weather /ˈweðər/

WORD_IPA:
I /aɪ/
think /θɪŋk/
the /ðə/
weather /ˈweðər/
will /wɪl/
be /bi/
warm /wɔːrm/

CONNECTED_SPEECH:
I think the weather /aɪ θɪŋk ðə ˈweðər/ | Keep "the" light and unstressed before "weather".
will be warm /wəl bi wɔːrm/ | Reduce "will" toward /wəl/ in fast natural speech.
""")

    monkeypatch.setattr(
        coach,
        "get_client",
        lambda: SimpleNamespace(models=FakeModels()),
    )

    result = coach.generate_tailored_prompt({"focus_areas": [], "difficulty": "intermediate"})

    assert "CONNECTED_SPEECH:" in captured["prompt"]
    assert "phrase chunks" in captured["prompt"]
    assert "plain-English note" in captured["prompt"]
    assert "not replace WORD_IPA" in captured["prompt"]
    assert captured["config"].max_output_tokens >= 3072
    assert result["connected_speech"] == [
        {
            "phrase": "I think the weather",
            "ipa": "aɪ θɪŋk ðə ˈweðər",
            "note": 'Keep "the" light and unstressed before "weather".',
        },
        {
            "phrase": "will be warm",
            "ipa": "wəl bi wɔːrm",
            "note": 'Reduce "will" toward /wəl/ in fast natural speech.',
        },
    ]
