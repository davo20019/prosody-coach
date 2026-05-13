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
