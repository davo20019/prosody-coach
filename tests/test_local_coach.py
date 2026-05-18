import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace


def _analysis_stub():
    return SimpleNamespace(
        pitch=SimpleNamespace(score=7, feedback="pitch ok"),
        volume=SimpleNamespace(score=8, feedback="volume ok"),
        tempo=SimpleNamespace(score=6, estimated_wpm=135, feedback="tempo ok"),
        rhythm=SimpleNamespace(score=5, pvi=48, feedback="rhythm ok"),
        pauses=SimpleNamespace(score=9, feedback="pauses ok"),
    )


def _valid_coaching_response(transcript: str = "hello world") -> str:
    return f"""
TRANSCRIPT:
{transcript}

GRAMMAR_ISSUES:
None

SUGGESTED_REVISION:
{transcript}

COACHING_TIPS:
- Keep your pace steady.

VOCAL_CONFIDENCE:
7 | steady

FILLER_WORDS:
0 | None detected

PRONUNCIATION_ISSUES:
None - pronunciation was clear

FLUENCY:
7 | smooth

AI_PROSODY:
- PITCH: 7/10 | varied

OVERALL:
Good work.
"""


def test_whisper_cpp_transcriber_writes_and_reads_text_output(tmp_path):
    from local_coach import LocalCoachConfig, WhisperCppTranscriber

    audio_path = tmp_path / "sample.flac"
    audio_path.write_bytes(b"fake audio")
    model_path = tmp_path / "ggml-base.en.bin"
    model_path.write_bytes(b"fake model")
    calls = []

    def fake_runner(args, check, capture_output, text):
        calls.append(args)
        output_base = Path(args[args.index("-of") + 1])
        output_base.with_suffix(".txt").write_text("hello world\n")
        return SimpleNamespace(stdout="", stderr="")

    config = LocalCoachConfig(
        whisper_bin="whisper-cli",
        whisper_model=str(model_path),
    )

    transcript = WhisperCppTranscriber(config, runner=fake_runner).transcribe(audio_path)

    assert transcript == "hello world"
    assert calls
    assert calls[0][:2] == ["whisper-cli", "-m"]
    assert str(model_path) in calls[0]
    assert str(audio_path) in calls[0]
    assert "-otxt" in calls[0]
    assert "--no-timestamps" in calls[0]


def test_local_llm_client_posts_openai_compatible_chat_request():
    from local_coach import LocalCoachConfig, LocalLlmClient

    captured = {}

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self):
            return json.dumps(
                {"choices": [{"message": {"content": "coaching text"}}]}
            ).encode("utf-8")

    def fake_opener(request, timeout):
        captured["url"] = request.full_url
        captured["timeout"] = timeout
        captured["payload"] = json.loads(request.data.decode("utf-8"))
        return FakeResponse()

    config = LocalCoachConfig(
        llm_base_url="http://127.0.0.1:8080",
        llm_model="gemma-local",
        llm_timeout=12,
    )

    text = LocalLlmClient(config, opener=fake_opener).complete("Coach this")

    assert text == "coaching text"
    assert captured["url"] == "http://127.0.0.1:8080/v1/chat/completions"
    assert captured["timeout"] == 12
    assert captured["payload"]["model"] == "gemma-local"
    assert captured["payload"]["messages"] == [{"role": "user", "content": "Coach this"}]
    assert captured["payload"]["temperature"] == 0.3


def test_local_coach_provider_uses_whisper_transcript_when_llm_omits_it(tmp_path):
    from local_coach import LocalCoachProvider

    audio_path = tmp_path / "sample.flac"
    audio_path.write_bytes(b"fake audio")
    captured = {}

    class FakeTranscriber:
        def transcribe(self, path):
            captured["audio_path"] = path
            return "hello world"

    class FakeLlm:
        def complete(self, prompt, **kwargs):
            captured["prompt"] = prompt
            return _valid_coaching_response(transcript="")

    provider = LocalCoachProvider(transcriber=FakeTranscriber(), llm_client=FakeLlm())

    result = provider.analyze(
        audio_path=audio_path,
        audio_data=None,
        sample_rate=16000,
        prosody=_analysis_stub(),
    )

    assert captured["audio_path"] == audio_path
    assert "LOCAL ASR TRANSCRIPT" in captured["prompt"]
    assert "hello world" in captured["prompt"]
    assert result.transcript == "hello world"
    assert result.coaching_tips == ["Keep your pace steady."]


def test_diagnose_local_setup_reports_binary_model_and_server(tmp_path):
    from local_coach import LocalCoachConfig, diagnose_local_setup

    missing_model = tmp_path / "missing.bin"
    config = LocalCoachConfig(
        whisper_bin="whisper-cli",
        whisper_model=str(missing_model),
        llm_base_url="http://127.0.0.1:8080/v1",
    )

    checks = diagnose_local_setup(
        config,
        which=lambda name: "/opt/homebrew/bin/whisper-cli" if name == "whisper-cli" else None,
        llm_checker=lambda cfg: (False, "server is not responding"),
    )

    by_key = {check.key: check for check in checks}

    assert by_key["whisper_binary"].ok is True
    assert by_key["whisper_model"].ok is False
    assert str(missing_model) in by_key["whisper_model"].detail
    assert by_key["llama_server"].ok is False
    assert by_key["llama_server"].detail == "server is not responding"


def test_local_setup_command_prints_model_setup_instructions():
    result = subprocess.run(
        [sys.executable, "main.py", "local", "setup"],
        check=True,
        capture_output=True,
        text=True,
    )

    assert "brew install whisper-cpp llama.cpp" in result.stdout
    assert "WHISPER_MODEL" in result.stdout
    assert "llama-server" in result.stdout


# --------------------------------------------------------------------------- #
# Local LLM endpoint auto-detection
# --------------------------------------------------------------------------- #

def _make_models_response(*model_ids):
    """Stub urlopen response returning an OpenAI-compatible /v1/models body."""
    body = json.dumps({
        "object": "list",
        "data": [{"id": mid} for mid in model_ids],
    }).encode("utf-8")

    class _Resp:
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def read(self): return body
    return _Resp()


def test_detect_local_llm_url_returns_first_endpoint_with_models():
    """Detection must skip endpoints that respond but have no models loaded."""
    import urllib.error
    from local_coach import detect_local_llm_url

    def fake_opener(request, timeout):
        url = request.full_url
        if url.endswith("11434/v1/models"):
            # Reachable but no models — Ollama before `ollama pull`.
            class _Empty(_make_models_response().__class__):
                def read(self_inner):
                    return json.dumps({"object": "list", "data": None}).encode("utf-8")
            return _Empty()
        if url.endswith("8080/v1/models"):
            return _make_models_response("qwen2.5-7b-instruct")
        # All others refused.
        raise urllib.error.URLError("Connection refused")

    best, probes = detect_local_llm_url(
        candidates=[
            "http://127.0.0.1:11434/v1",
            "http://127.0.0.1:8080/v1",
            "http://127.0.0.1:8090/v1",
        ],
        timeout=0.1,
        opener=fake_opener,
    )

    assert best == "http://127.0.0.1:8080/v1"
    # Probes preserved in candidate order so callers can render diagnostics.
    assert [p.base_url for p in probes] == [
        "http://127.0.0.1:11434/v1",
        "http://127.0.0.1:8080/v1",
        "http://127.0.0.1:8090/v1",
    ]
    assert probes[0].reachable and not probes[0].has_models
    assert probes[1].reachable and probes[1].has_models
    assert probes[1].models == ["qwen2.5-7b-instruct"]
    assert probes[2].reachable is False


def test_detect_local_llm_url_returns_none_when_nothing_usable():
    """When no candidate has models loaded, best_url is None and all probes are
    still returned for diagnostics."""
    import urllib.error
    from local_coach import detect_local_llm_url

    def all_refused(request, timeout):
        raise urllib.error.URLError("Connection refused")

    best, probes = detect_local_llm_url(
        candidates=["http://127.0.0.1:8090/v1"],
        timeout=0.1, opener=all_refused,
    )
    assert best is None
    assert len(probes) == 1
    assert probes[0].reachable is False
    assert "Connection refused" in (probes[0].error or "")


def test_whisper_server_error_hint_when_port_is_closed(monkeypatch):
    """When nothing is listening on the configured port, the error hint should
    say so plainly and offer the whisper-cli fallback path."""
    import urllib.error
    from local_coach import LocalCoachConfig, WhisperServerTranscriber
    import pytest

    # TCP probe: nothing listening anywhere.
    monkeypatch.setattr("local_coach._probe_tcp", lambda host, port, timeout=0.3: False)

    def fake_opener(request, timeout):
        raise urllib.error.URLError("[Errno 61] Connection refused")

    config = LocalCoachConfig(
        whisper_server_url="http://127.0.0.1:9000",
        whisper_bin="/opt/homebrew/bin/whisper-cli",
        whisper_model="/models/ggml-medium.en.bin",
        llm_timeout=1,
    )
    # transcribe() opens the audio file before calling the opener, so we need
    # a real path. tmp file is overkill — point at an existing file.
    import sys
    audio = Path(sys.executable)  # any existing file; opener is faked anyway
    with pytest.raises(RuntimeError) as exc_info:
        WhisperServerTranscriber(config, opener=fake_opener).transcribe(audio)

    msg = str(exc_info.value)
    assert "not reachable" in msg
    assert "Nothing is listening on 127.0.0.1:9000" in msg
    # Concrete fallback advice using the user's existing whisper-cli config.
    assert "unset LOCAL_WHISPER_SERVER_URL" in msg
    assert "ggml-medium.en.bin" in msg


def test_whisper_server_error_hint_when_port_is_open_but_unresponsive(monkeypatch):
    """When the port IS open but the HTTP request fails (RemoteDisconnected or
    similar), the hint should diagnose a crashed server rather than a missing one."""
    import urllib.error
    from local_coach import LocalCoachConfig, WhisperServerTranscriber
    import pytest

    monkeypatch.setattr("local_coach._probe_tcp", lambda host, port, timeout=0.3: True)

    def fake_opener(request, timeout):
        # Mimic http.client.RemoteDisconnected, which arrives as OSError.
        raise ConnectionResetError("Remote end closed connection without response")

    config = LocalCoachConfig(
        whisper_server_url="http://127.0.0.1:9000",
        whisper_bin="/opt/homebrew/bin/whisper-cli",
        whisper_model="/models/ggml-medium.en.bin",
        llm_timeout=1,
    )
    import sys
    audio = Path(sys.executable)
    with pytest.raises(RuntimeError) as exc_info:
        WhisperServerTranscriber(config, opener=fake_opener).transcribe(audio)

    msg = str(exc_info.value)
    assert "TCP port 9000 is open" in msg
    assert "crashed mid-request" in msg or "OOM" in msg
    # Original failure preserved.
    assert "Remote end closed connection without response" in msg


def test_local_llm_client_error_includes_alternative_endpoint_hint():
    """When the configured URL refuses, the error message must point the user
    at a reachable OpenAI-compatible alternative if one was found."""
    import urllib.error
    from local_coach import LocalCoachConfig, LocalLlmClient
    import pytest

    def fake_opener(request, timeout):
        url = request.full_url
        # The actual completion POST refuses.
        if "chat/completions" in url:
            raise urllib.error.URLError("Connection refused")
        # The probe sees an alternative working server on 11434.
        if url.endswith("11434/v1/models"):
            return _make_models_response("llama3.2:3b")
        raise urllib.error.URLError("Connection refused")

    config = LocalCoachConfig(
        llm_base_url="http://127.0.0.1:8090/v1",
        llm_model="gemma-local", llm_timeout=1,
    )
    with pytest.raises(RuntimeError) as exc_info:
        LocalLlmClient(config, opener=fake_opener).complete("Coach this")

    msg = str(exc_info.value)
    # Original failure still reported.
    assert "http://127.0.0.1:8090/v1" in msg
    # And a concrete pointer to the working alternative.
    assert "11434" in msg
    assert "llama3.2:3b" in msg
    assert "LOCAL_LLM_BASE_URL=" in msg
