"""Local AI coaching provider using whisper.cpp and llama.cpp."""

from __future__ import annotations

import json
import mimetypes
import os
import re
import shutil
import subprocess
import tempfile
import urllib.error
import urllib.request
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

import numpy as np
import soundfile as sf

from analyzer import ProsodyAnalysis
from coach import CoachingResult, parse_coaching_response
from config import (
    LOCAL_LLM_BASE_URL,
    LOCAL_LLM_MODEL,
    LOCAL_LLM_TIMEOUT,
    LOCAL_WHISPER_BIN,
    LOCAL_WHISPER_MODEL,
    LOCAL_WHISPER_SERVER_URL,
)


@dataclass
class LocalCoachConfig:
    """Runtime configuration for fully local AI coaching."""

    whisper_bin: str = LOCAL_WHISPER_BIN
    whisper_model: str = LOCAL_WHISPER_MODEL
    whisper_server_url: str = LOCAL_WHISPER_SERVER_URL
    llm_base_url: str = LOCAL_LLM_BASE_URL
    llm_model: str = LOCAL_LLM_MODEL
    llm_timeout: float = LOCAL_LLM_TIMEOUT

    @classmethod
    def from_env(cls) -> "LocalCoachConfig":
        """Load local provider settings from current environment variables."""
        return cls(
            whisper_bin=os.environ.get("WHISPER_CPP_BIN", LOCAL_WHISPER_BIN),
            whisper_model=os.environ.get("WHISPER_MODEL", LOCAL_WHISPER_MODEL),
            whisper_server_url=os.environ.get("LOCAL_WHISPER_SERVER_URL", LOCAL_WHISPER_SERVER_URL),
            llm_base_url=os.environ.get("LOCAL_LLM_BASE_URL", LOCAL_LLM_BASE_URL),
            llm_model=os.environ.get("LOCAL_LLM_MODEL", LOCAL_LLM_MODEL),
            llm_timeout=float(os.environ.get("LOCAL_LLM_TIMEOUT", str(LOCAL_LLM_TIMEOUT))),
        )


@dataclass
class LocalSetupCheck:
    """A single local setup diagnostic check."""

    key: str
    label: str
    ok: bool
    detail: str
    fix: str


class WhisperCppTranscriber:
    """Transcribe audio with the whisper.cpp command-line binary."""

    def __init__(
        self,
        config: Optional[LocalCoachConfig] = None,
        runner: Callable[..., subprocess.CompletedProcess] = subprocess.run,
    ):
        self.config = config or LocalCoachConfig.from_env()
        self.runner = runner

    def transcribe(self, audio_path: Path) -> str:
        """Run whisper.cpp and return cleaned transcript text."""
        audio_path = Path(audio_path)
        if not audio_path.exists():
            raise FileNotFoundError(f"Audio file not found: {audio_path}")

        if not self.config.whisper_model:
            raise ValueError(
                "WHISPER_MODEL is not set. Run `prosody local setup` for setup instructions."
            )

        model_path = Path(os.path.expanduser(self.config.whisper_model))
        if not model_path.exists():
            raise FileNotFoundError(f"Whisper model not found: {model_path}")

        with tempfile.TemporaryDirectory(prefix="prosody-whisper-") as temp_dir:
            output_base = Path(temp_dir) / "transcript"
            command = [
                self.config.whisper_bin,
                "-m",
                str(model_path),
                "-f",
                str(audio_path),
                "-otxt",
                "-of",
                str(output_base),
                "--no-timestamps",
            ]

            try:
                completed = self.runner(
                    command,
                    check=True,
                    capture_output=True,
                    text=True,
                )
            except FileNotFoundError as exc:
                raise RuntimeError(
                    f"whisper.cpp binary not found: {self.config.whisper_bin}"
                ) from exc
            except subprocess.CalledProcessError as exc:
                stderr = (exc.stderr or exc.stdout or "").strip()
                raise RuntimeError(f"whisper.cpp transcription failed: {stderr}") from exc

            transcript_path = output_base.with_suffix(".txt")
            if transcript_path.exists():
                transcript = transcript_path.read_text(encoding="utf-8", errors="replace")
            else:
                transcript = getattr(completed, "stdout", "") or ""

        transcript = _clean_whisper_text(transcript)
        if not transcript:
            raise RuntimeError("whisper.cpp returned an empty transcript.")
        return transcript


class WhisperServerTranscriber:
    """Transcribe audio via whisper.cpp HTTP server (keeps model resident)."""

    def __init__(
        self,
        config: Optional[LocalCoachConfig] = None,
        opener: Callable[..., object] = urllib.request.urlopen,
    ):
        self.config = config or LocalCoachConfig.from_env()
        if not self.config.whisper_server_url:
            raise ValueError(
                "LOCAL_WHISPER_SERVER_URL is not set. Start `whisper-server` and set the URL."
            )
        self.opener = opener

    def transcribe(self, audio_path: Path) -> str:
        audio_path = Path(audio_path)
        if not audio_path.exists():
            raise FileNotFoundError(f"Audio file not found: {audio_path}")

        url = self.config.whisper_server_url.rstrip("/") + "/inference"
        boundary = f"----prosody{uuid.uuid4().hex}"
        body = _encode_multipart_audio(audio_path, boundary)
        request = urllib.request.Request(
            url,
            data=body,
            headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
            method="POST",
        )
        try:
            with self.opener(request, timeout=self.config.llm_timeout) as response:
                payload = response.read()
        except urllib.error.URLError as exc:
            raise RuntimeError(f"whisper-server not reachable at {url}: {exc}") from exc

        raw = payload.decode("utf-8", errors="replace").strip()
        if raw.startswith("{"):
            try:
                raw = json.loads(raw).get("text", "")
            except json.JSONDecodeError:
                pass
        transcript = _clean_whisper_text(raw)
        if not transcript:
            raise RuntimeError("whisper-server returned an empty transcript.")
        return transcript


def _encode_multipart_audio(audio_path: Path, boundary: str) -> bytes:
    mime = mimetypes.guess_type(audio_path.name)[0] or "application/octet-stream"
    crlf = b"\r\n"
    parts = [
        f"--{boundary}".encode(),
        f'Content-Disposition: form-data; name="file"; filename="{audio_path.name}"'.encode(),
        f"Content-Type: {mime}".encode(),
        b"",
        audio_path.read_bytes(),
        f"--{boundary}".encode(),
        b'Content-Disposition: form-data; name="response_format"',
        b"",
        b"text",
        f"--{boundary}--".encode(),
        b"",
    ]
    return crlf.join(parts)


class LocalLlmClient:
    """OpenAI-compatible chat client for a local llama.cpp server."""

    def __init__(
        self,
        config: Optional[LocalCoachConfig] = None,
        opener: Callable[..., object] = urllib.request.urlopen,
    ):
        self.config = config or LocalCoachConfig.from_env()
        self.opener = opener

    def complete(
        self,
        prompt: str,
        temperature: float = 0.3,
        max_tokens: int = 8192,
    ) -> str:
        """Send a chat completion request to the local LLM server."""
        payload = {
            "model": self.config.llm_model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        request = urllib.request.Request(
            _chat_completions_url(self.config.llm_base_url),
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with self.opener(request, timeout=self.config.llm_timeout) as response:
                data = json.loads(response.read().decode("utf-8"))
        except urllib.error.URLError as exc:
            raise RuntimeError(
                f"Local LLM server is not reachable at {self.config.llm_base_url}: {exc}"
            ) from exc
        except json.JSONDecodeError as exc:
            raise RuntimeError("Local LLM server returned invalid JSON.") from exc

        try:
            return data["choices"][0]["message"]["content"].strip()
        except (KeyError, IndexError, TypeError) as exc:
            raise RuntimeError(f"Unexpected local LLM response: {data}") from exc


class LocalCoachProvider:
    """End-to-end local coaching: Whisper transcript + metrics + local LLM."""

    def __init__(
        self,
        config: Optional[LocalCoachConfig] = None,
        transcriber=None,
        llm_client: Optional[LocalLlmClient] = None,
    ):
        self.config = config or LocalCoachConfig.from_env()
        if transcriber is not None:
            self.transcriber = transcriber
        elif self.config.whisper_server_url:
            self.transcriber = WhisperServerTranscriber(self.config)
        else:
            self.transcriber = WhisperCppTranscriber(self.config)
        self.llm_client = llm_client or LocalLlmClient(self.config)

    def analyze(
        self,
        audio_path: Optional[Path],
        audio_data: Optional[np.ndarray],
        sample_rate: int,
        prosody: ProsodyAnalysis,
        expected_text: Optional[str] = None,
    ) -> CoachingResult:
        """Analyze a recording with the local provider."""
        transient_path = None
        if audio_path is None:
            if audio_data is None:
                raise ValueError("audio_data is required when audio_path is not provided.")
            transient_path = _write_temp_audio(audio_data, sample_rate)
            audio_path = transient_path
        else:
            audio_path = Path(audio_path)

        try:
            transcript = self.transcriber.transcribe(audio_path)
            prompt = build_local_coaching_prompt(
                prosody=prosody,
                transcript=transcript,
                expected_text=expected_text,
            )
            response_text = self.llm_client.complete(prompt)
            result = parse_coaching_response(response_text)
            if _transcript_is_missing(result.transcript):
                result.transcript = transcript
            return result
        finally:
            if transient_path is not None:
                transient_path.unlink(missing_ok=True)


def analyze_with_local_coach(
    audio_data: np.ndarray,
    sample_rate: int,
    prosody: ProsodyAnalysis,
    audio_path: Optional[Path] = None,
    expected_text: Optional[str] = None,
) -> CoachingResult:
    """Convenience wrapper for local coaching."""
    return LocalCoachProvider().analyze(
        audio_path=audio_path,
        audio_data=audio_data,
        sample_rate=sample_rate,
        prosody=prosody,
        expected_text=expected_text,
    )


def build_local_coaching_prompt(
    prosody: ProsodyAnalysis,
    transcript: str,
    expected_text: Optional[str] = None,
) -> str:
    """Build a coaching prompt for a text-only local LLM."""
    practice_block = ""
    task = (
        "Use the local ASR transcript and measured prosody metrics to coach the speaker."
    )
    transcript_instruction = (
        "Use the LOCAL ASR TRANSCRIPT as the source of what was said. "
        "Do not invent words that are not in the transcript."
    )

    if expected_text:
        task = (
            "The user was asked to read the expected text aloud. Compare the local "
            "ASR transcript with that expected text and coach the speaker."
        )
        practice_block = f"""
EXPECTED TEXT:
"{expected_text}"
"""
        transcript_instruction = (
            "Use the LOCAL ASR TRANSCRIPT as what the user actually said. "
            "Compare it to EXPECTED TEXT for skipped, added, or misread words."
        )

    return f"""You are an English speech coach helping a Spanish speaker improve their English communication.

TASK: {task}

LOCAL ASR TRANSCRIPT:
"{transcript}"
{practice_block}
{transcript_instruction}

PROSODY ANALYSIS RESULTS (already measured locally):
- Pitch: {prosody.pitch.score}/10 - {prosody.pitch.feedback}
- Volume: {prosody.volume.score}/10 - {prosody.volume.feedback}
- Tempo: {prosody.tempo.score}/10 - Speed: {prosody.tempo.estimated_wpm:.0f} WPM. {prosody.tempo.feedback}
- Rhythm: {prosody.rhythm.score}/10 - PVI: {prosody.rhythm.pvi:.0f}. {prosody.rhythm.feedback}
- Pauses: {prosody.pauses.score}/10 - {prosody.pauses.feedback}

You cannot listen to the audio directly. For vocal quality, confidence, fluency, rhythm, and pronunciation, combine the transcript with the measured prosody metrics. Be explicit when feedback is based on metrics rather than direct hearing.

Please provide your response in this EXACT format:

TRANSCRIPT:
[Repeat the local ASR transcript, lightly correcting only obvious transcription punctuation]

GRAMMAR_ISSUES:
[List each grammar or pronunciation issue on a new line in this format:]
["original text" -> "corrected text" | explanation]
[If this is reading practice, compare transcript to expected text here]
[If no issues, write: None]

SUGGESTED_REVISION:
[Write a polished version of what was said, or the correct expected text for reading practice]

COACHING_TIPS:
[List 3-5 specific, actionable tips based on:]
[1. The lowest prosody score area]
[2. Transcript grammar or word choice]
[3. Spanish-speaker patterns such as rhythm, reductions, word-final consonants, v/b, or th]
[4. Where to slow down, stress key words, or pause]

VOCAL_CONFIDENCE:
[Rate likely confidence from 1-10 using transcript and metrics]
[Format: SCORE | explanation]

FILLER_WORDS:
[Count filler words in the transcript: um, uh, er, like, you know, so, basically, I mean, kind of, sort of]
[Format: COUNT | list each filler word with its count]
[If no filler words, write: 0 | None detected]

PRONUNCIATION_ISSUES:
[List likely pronunciation sounds to practice only when transcript or expected text supports it]
[Format each as: SOUND | example word | tip for improvement]
[If pronunciation cannot be inferred or is clear, write: None - pronunciation was clear]

FLUENCY:
[Rate fluency from 1-10 using tempo, pauses, and transcript]
[Format: SCORE | explanation]

AI_PROSODY:
[Metrics-informed prosody assessment. Do not claim direct audio listening.]
[Format each line as: CATEGORY: SCORE/10 | observation]
- PITCH: [Score 1-10] | [Use measured pitch score and feedback]
- VOLUME: [Score 1-10] | [Use measured volume score and feedback]
- TEMPO: [Score 1-10] | [Use measured WPM and tempo feedback]
- RHYTHM: [Score 1-10] | [Use measured rhythm score and PVI]
- PAUSES: [Score 1-10] | [Use measured pause score and feedback]
- NATURALNESS: [Score 1-10] | [Overall estimate from transcript plus metrics]

OVERALL:
[One paragraph summary of strengths and the #1 thing to focus on improving]
"""


def generate_local_tailored_prompt(
    weaknesses: dict,
    due_sounds: Optional[list[dict]] = None,
    due_words: Optional[list[dict]] = None,
    llm_client: Optional[LocalLlmClient] = None,
) -> dict:
    """Generate tailored practice material with the local text LLM."""
    focus_areas = weaknesses.get("focus_areas", [])
    difficulty = weaknesses.get("difficulty", "intermediate")
    recurring_sounds = weaknesses.get("recurring_sounds", [])

    focus_descriptions = []
    target_words = []
    target_sounds = []

    if due_words:
        for word_data in due_words[:5]:
            word = word_data.get("word", "")
            ipa = word_data.get("ipa", "")
            if word:
                target_words.append({"word": word, "ipa": ipa})
        if target_words:
            words = ", ".join(word["word"] for word in target_words)
            focus_descriptions.append(f"MUST INCLUDE WORDS: {words}")

    if due_sounds:
        for sound_data in due_sounds[:3]:
            sound = sound_data.get("sound", "")
            ipa = sound_data.get("ipa", "")
            if sound:
                target_sounds.append({"sound": sound, "ipa": ipa})
        if target_sounds:
            sounds = ", ".join(sound["sound"] for sound in target_sounds)
            focus_descriptions.append(f"PRIORITY SOUNDS: {sounds}")

    prosody_focuses = [f["area"] for f in focus_areas if f.get("type") == "prosody"]
    if prosody_focuses:
        focus_descriptions.append(f"Prosody: {', '.join(prosody_focuses)}")

    pron_sounds = [f["sound"] for f in focus_areas if f.get("type") == "pronunciation"]
    if not pron_sounds and recurring_sounds:
        pron_sounds = [sound[0] for sound in recurring_sounds[:3]]

    existing_sounds = {sound["sound"] for sound in target_sounds}
    for sound in pron_sounds:
        if sound and sound not in existing_sounds:
            target_sounds.append({"sound": sound, "ipa": ""})

    if pron_sounds:
        focus_descriptions.append(f"Sounds: {', '.join(pron_sounds)}")
    if any(f.get("type") == "confidence" for f in focus_areas):
        focus_descriptions.append("Build confidence with clear declarative sentences")
    if any(f.get("type") == "fluency" for f in focus_areas):
        focus_descriptions.append("Improve fluency with connected speech")
    if any(f.get("type") == "filler_words" for f in focus_areas):
        focus_descriptions.append("Reduce fillers with direct statements")

    focus_text = "\n".join(f"- {item}" for item in focus_descriptions) or "- General practice"
    prompt = f"""You are an English pronunciation coach creating practice material for a Spanish speaker.

Generate a short practice text tailored to the learner.

DIFFICULTY LEVEL: {difficulty}

FOCUS AREAS:
{focus_text}

REQUIREMENTS:
1. Write 2-3 natural, meaningful sentences.
2. Include target words and sounds if listed.
3. Include natural pause points if rhythm or pauses are a focus.
4. Avoid tongue twisters and artificial lists.

Respond in this exact format:

TEXT:
The practice sentences go here.

KEY_SOUNDS:
word1 /IPA1/, word2 /IPA2/, word3 /IPA3/
"""

    client = llm_client or LocalLlmClient()
    response_text = client.complete(prompt, temperature=0.7, max_tokens=2048)
    text, key_sounds = _parse_tailored_prompt_response(response_text)

    return {
        "text": text,
        "key_sounds": key_sounds,
        "focus_areas": [f["description"] for f in focus_areas if "description" in f],
        "difficulty": difficulty,
        "id": f"tailored_{difficulty}",
        "target_sounds": target_sounds,
        "target_words": target_words,
    }


def diagnose_local_setup(
    config: Optional[LocalCoachConfig] = None,
    which: Callable[[str], Optional[str]] = shutil.which,
    llm_checker: Optional[Callable[[LocalCoachConfig], tuple[bool, str]]] = None,
) -> list[LocalSetupCheck]:
    """Return local AI setup diagnostics."""
    config = config or LocalCoachConfig.from_env()
    llm_checker = llm_checker or check_llama_server
    checks = []

    binary = os.path.expanduser(config.whisper_bin)
    if os.sep in binary:
        binary_path = Path(binary)
        binary_ok = binary_path.exists() and os.access(binary_path, os.X_OK)
        binary_detail = str(binary_path) if binary_ok else f"{binary_path} is not executable or missing"
    else:
        found = which(binary)
        binary_ok = found is not None
        binary_detail = found or f"{binary} is not on PATH"

    checks.append(
        LocalSetupCheck(
            key="whisper_binary",
            label="whisper.cpp binary",
            ok=binary_ok,
            detail=binary_detail,
            fix="Install with `brew install whisper-cpp` or set WHISPER_CPP_BIN.",
        )
    )

    if config.whisper_model:
        model_path = Path(os.path.expanduser(config.whisper_model))
        model_ok = model_path.exists()
        model_detail = str(model_path) if model_ok else f"{model_path} does not exist"
    else:
        model_ok = False
        model_detail = "WHISPER_MODEL is not set"

    checks.append(
        LocalSetupCheck(
            key="whisper_model",
            label="Whisper model",
            ok=model_ok,
            detail=model_detail,
            fix="Download a whisper.cpp GGML model and set WHISPER_MODEL.",
        )
    )

    llm_ok, llm_detail = llm_checker(config)
    checks.append(
        LocalSetupCheck(
            key="llama_server",
            label="llama.cpp server",
            ok=llm_ok,
            detail=llm_detail,
            fix="Start `llama-server` with a GGUF model, then set LOCAL_LLM_BASE_URL.",
        )
    )

    if config.whisper_server_url:
        ws_ok, ws_detail = check_whisper_server(config)
        checks.append(
            LocalSetupCheck(
                key="whisper_server",
                label="whisper.cpp server",
                ok=ws_ok,
                detail=ws_detail,
                fix="Start `whisper-server -m <model> --host 127.0.0.1 --port 9000`.",
            )
        )

    return checks


def check_whisper_server(config: LocalCoachConfig) -> tuple[bool, str]:
    """Check whether the whisper.cpp HTTP server is reachable."""
    base = config.whisper_server_url.rstrip("/")
    request = urllib.request.Request(base + "/", method="GET")
    try:
        with urllib.request.urlopen(request, timeout=2) as response:
            getattr(response, "status", 200)
        return True, f"reachable at {base}"
    except urllib.error.HTTPError:
        return True, f"reachable at {base}"
    except Exception as exc:
        return False, str(exc)


def check_llama_server(config: LocalCoachConfig) -> tuple[bool, str]:
    """Check whether the local OpenAI-compatible server is reachable."""
    url = _models_url(config.llm_base_url)
    request = urllib.request.Request(url, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=3) as response:
            status = getattr(response, "status", 200)
            if status < 400:
                return True, f"reachable at {url}"
            return False, f"{url} returned HTTP {status}"
    except Exception as exc:
        return False, str(exc)


def _clean_whisper_text(text: str) -> str:
    lines = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        line = re.sub(r"^\[[^\]]+\]\s*", "", line).strip()
        if line:
            lines.append(line)
    return " ".join(lines).strip()


def _write_temp_audio(audio_data: np.ndarray, sample_rate: int) -> Path:
    temp_file = tempfile.NamedTemporaryFile(
        prefix="prosody-local-",
        suffix=".flac",
        delete=False,
    )
    temp_path = Path(temp_file.name)
    temp_file.close()
    sf.write(temp_path, audio_data, sample_rate, format="flac")
    return temp_path


def _transcript_is_missing(transcript: str) -> bool:
    normalized = (transcript or "").strip().lower()
    return normalized in {"", "same as above", "[same as above]", "[transcript]"}


def _chat_completions_url(base_url: str) -> str:
    base = base_url.rstrip("/")
    if base.endswith("/v1/chat/completions") or base.endswith("/chat/completions"):
        return base
    if base.endswith("/v1"):
        return f"{base}/chat/completions"
    return f"{base}/v1/chat/completions"


def _models_url(base_url: str) -> str:
    base = base_url.rstrip("/")
    if base.endswith("/chat/completions"):
        base = base.rsplit("/chat/completions", 1)[0]
    if not base.endswith("/v1"):
        base = f"{base}/v1"
    return f"{base}/models"


def _parse_tailored_prompt_response(response_text: str) -> tuple[str, str]:
    text_lines = []
    key_lines = []
    section = None

    for line in response_text.splitlines():
        stripped = line.strip()
        upper = stripped.upper()
        if upper.startswith("TEXT:"):
            section = "text"
            content = stripped[5:].strip()
            if content:
                text_lines.append(content)
        elif upper.startswith("KEY_SOUNDS:") or upper.startswith("KEY SOUNDS:"):
            section = "keys"
            content = re.sub(r"^KEY[_ ]SOUNDS:\s*", "", stripped, flags=re.IGNORECASE)
            if content:
                key_lines.append(content)
        elif stripped and section == "text" and not stripped.startswith("["):
            text_lines.append(stripped)
        elif stripped and section == "keys" and not stripped.startswith("["):
            key_lines.append(stripped)

    text = " ".join(text_lines).strip() or response_text.strip().strip("\"'")
    key_sounds = ", ".join(key_lines).strip()

    for header in ("TEXT:", "KEY_SOUNDS:", "KEY SOUNDS:"):
        text = re.sub(re.escape(header), "", text, flags=re.IGNORECASE).strip()

    if text and text[-1] not in ".!?":
        last_end = max(text.rfind("."), text.rfind("!"), text.rfind("?"))
        if last_end > len(text) // 2:
            text = text[: last_end + 1]

    return text, key_sounds
