"""Framework structure scoring.

Given a transcript and a framework definition (from frameworks.py), ask the
configured LLM (Gemini or local Gemma) to tag each slot using token-index
ranges over the transcript's tokens. Then compute an overall score and
pass/fail using the rubric.

The contract is text-section output (not JSON) so both Gemini and local
llama.cpp work uniformly via the same parser.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Optional


logger = logging.getLogger(__name__)


@dataclass
class SlotScore:
    """Scoring for a single framework slot."""

    slot_id: str
    present: str  # "yes" | "no" | "partial"
    quality: int  # 0-5
    note: str
    start_index: Optional[int] = None  # token index into transcript.tokens
    end_index: Optional[int] = None    # inclusive


@dataclass
class ModelAnswer:
    """A learner's transcript rewritten through the framework, slot by slot."""
    slots: list[tuple[str, str, str]] = field(default_factory=list)  # (slot_id, slot_name, text)


@dataclass
class FrameworkScore:
    """Full scoring result for one framework attempt."""

    framework_id: str
    slots: list[SlotScore] = field(default_factory=list)
    grammar_notes: list[str] = field(default_factory=list)
    cultural_note: str = ""
    overall_note: str = ""
    raw_response: str = ""

    def slot(self, slot_id: str) -> Optional[SlotScore]:
        for s in self.slots:
            if s.slot_id == slot_id:
                return s
        return None


# --------------------------------------------------------------------------- #
# Prompt building
# --------------------------------------------------------------------------- #

def build_scoring_prompt(framework: dict, tokens: list[str]) -> str:
    """Build a text-section prompt with a numbered-token transcript.

    The LLM returns indices, not verbatim quotes, so slot-to-audio alignment
    is reliable downstream.
    """
    framework_name = framework["name"]
    max_index = max(0, len(tokens) - 1)
    numbered = " ".join(f"[{i}] {tok}" for i, tok in enumerate(tokens))

    slot_lines = []
    for slot in framework["slots"]:
        slot_lines.append(
            f'- "{slot["id"]}" ({slot["name"]}): {slot["description"]}'
        )
    slot_spec = "\n".join(slot_lines)

    output_lines = []
    for slot in framework["slots"]:
        sid = slot["id"]
        output_lines.append(f"SLOT_{sid}_PRESENT: yes | no | partial")
        output_lines.append(f"SLOT_{sid}_START: <integer index or NONE>")
        output_lines.append(f"SLOT_{sid}_END: <integer index or NONE>")
        output_lines.append(f"SLOT_{sid}_QUALITY: <integer 0-5>")
        output_lines.append(f"SLOT_{sid}_NOTE: <one short coaching sentence>")
    output_spec = "\n".join(output_lines)

    rubric = framework.get("scoring_rubric") or {}
    must_metric = rubric.get("must_include_metric")
    self_attr = rubric.get("self_attribution_required", False)

    rubric_hints = []
    if must_metric:
        rubric_hints.append(
            f'- The "{must_metric}" slot should contain a number, percentage, or measurable outcome.'
        )
    if self_attr:
        rubric_hints.append(
            '- Look for first-person attribution ("I led", "I delivered") in action-style slots. '
            'Note in CULTURAL_NOTE if the speaker under-claims credit (only uses "we" or "the team").'
        )
    rubric_text = "\n".join(rubric_hints) if rubric_hints else "(no special rubric)"

    return f"""You are evaluating an ESL learner's spoken response against the {framework_name} framework.

The speaker is a non-native English speaker. Do NOT penalize accent or minor
grammar errors that do not obscure meaning — that leniency applies to FORM only.
Judge CONTENT strictly: vague, tautological, or filler-only answers must score
LOW even when grammatically clean.

Framework slots:
{slot_spec}

Rubric:
{rubric_text}

QUALITY scale (anchor each slot's QUALITY field to this; do not default to 4):
- 5: Specific, concrete, and substantive. Names the situation/actions/outcome
     with detail (who, what, scale, numbers where applicable). A listener
     learns something real.
- 4: Clear and concrete, but a notable specific is missing (e.g., no number,
     no named decision). Still informative.
- 3: Adequate but generic. Reader can tell the slot is addressed, but the
     content could apply to almost any project.
- 2: Vague, tautological ("we delivered what was needed"), filler-heavy, or
     trails off without completing the thought. Slot is technically mentioned
     but conveys little information.
- 1: Barely on-topic; one or two relevant words inside otherwise unrelated
     speech.
- 0: Slot is missing entirely. Set PRESENT to "no" when you assign 0.

Coherence check: if the overall response does not make sense as a connected
answer — sentences contradict, the thought never completes, slots cannot be
located — bias QUALITY downward and call this out in OVERALL_NOTE.

Transcript (each token is numbered; valid indices are 0 to {max_index}):
{numbered}

For each slot, return the inclusive token-index range that covers it. If the
slot is missing, set PRESENT to "no" and START/END to NONE. Indices must be
valid integers in [0, {max_index}] and START <= END.

Return your evaluation in EXACTLY this format, one field per line:

{output_spec}
GRAMMAR_NOTES: <up to 3 brief idiomaticity/grammar flags with corrections, separated by ' | '; or NONE>
CULTURAL_NOTE: <one short pragmatic note if relevant, e.g. under-claiming credit; or NONE>
OVERALL_NOTE: <one or two sentences summarizing how the response landed, including any coherence concern>
"""


# --------------------------------------------------------------------------- #
# Response parsing
# --------------------------------------------------------------------------- #

_PRESENT_RE = re.compile(r"^SLOT_(?P<slot>\w+)_PRESENT:\s*(?P<val>.+)$", re.IGNORECASE)
_START_RE = re.compile(r"^SLOT_(?P<slot>\w+)_START:\s*(?P<val>.+)$", re.IGNORECASE)
_END_RE = re.compile(r"^SLOT_(?P<slot>\w+)_END:\s*(?P<val>.+)$", re.IGNORECASE)
_QUALITY_RE = re.compile(r"^SLOT_(?P<slot>\w+)_QUALITY:\s*(?P<val>.+)$", re.IGNORECASE)
_NOTE_RE = re.compile(r"^SLOT_(?P<slot>\w+)_NOTE:\s*(?P<val>.+)$", re.IGNORECASE)
_GRAMMAR_RE = re.compile(r"^GRAMMAR_NOTES:\s*(?P<val>.+)$", re.IGNORECASE)
_CULTURAL_RE = re.compile(r"^CULTURAL_NOTE:\s*(?P<val>.+)$", re.IGNORECASE)
_OVERALL_RE = re.compile(r"^OVERALL_NOTE:\s*(?P<val>.+)$", re.IGNORECASE)


def parse_scoring_response(text: str, framework: dict, max_index: int) -> FrameworkScore:
    """Parse the text-section LLM output into a FrameworkScore."""
    raw_per_slot: dict[str, dict] = {}
    grammar = ""
    cultural = ""
    overall_note = ""

    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue

        if m := _PRESENT_RE.match(line):
            raw_per_slot.setdefault(m.group("slot").lower(), {})["present"] = m.group("val").strip()
        elif m := _START_RE.match(line):
            raw_per_slot.setdefault(m.group("slot").lower(), {})["start"] = m.group("val").strip()
        elif m := _END_RE.match(line):
            raw_per_slot.setdefault(m.group("slot").lower(), {})["end"] = m.group("val").strip()
        elif m := _QUALITY_RE.match(line):
            raw_per_slot.setdefault(m.group("slot").lower(), {})["quality"] = m.group("val").strip()
        elif m := _NOTE_RE.match(line):
            raw_per_slot.setdefault(m.group("slot").lower(), {})["note"] = m.group("val").strip()
        elif m := _GRAMMAR_RE.match(line):
            grammar = m.group("val").strip()
        elif m := _CULTURAL_RE.match(line):
            cultural = m.group("val").strip()
        elif m := _OVERALL_RE.match(line):
            overall_note = m.group("val").strip()

    slots: list[SlotScore] = []
    for slot_def in framework["slots"]:
        sid = slot_def["id"]
        raw = raw_per_slot.get(sid, {})
        slots.append(_build_slot_score(sid, raw, max_index))

    grammar_list: list[str] = []
    if grammar and grammar.upper() != "NONE":
        grammar_list = [g.strip() for g in grammar.split("|") if g.strip()]

    if cultural.upper() == "NONE":
        cultural = ""

    return FrameworkScore(
        framework_id=framework["id"],
        slots=slots,
        grammar_notes=grammar_list,
        cultural_note=cultural,
        overall_note=overall_note,
        raw_response=text,
    )


def _build_slot_score(slot_id: str, raw: dict, max_index: int) -> SlotScore:
    present = (raw.get("present") or "no").lower()
    if present not in ("yes", "no", "partial"):
        present = "no"

    quality = _safe_int(raw.get("quality"), default=0)
    quality = max(0, min(5, quality))

    note = raw.get("note") or ""

    start = _safe_index(raw.get("start"), max_index)
    end = _safe_index(raw.get("end"), max_index)

    # If either side is invalid (out-of-range, missing, etc.), drop both.
    # resolve_slot_spans() already gates on both being non-None, but pruning
    # here keeps the SlotScore self-consistent and saves callers a check.
    if start is None or end is None:
        start = end = None
    # Reject inverted spans.
    elif start > end:
        logger.debug("Slot %s has start > end (%s > %s); dropping span", slot_id, start, end)
        start = end = None

    # If the slot is marked missing, force the span to None too.
    if present == "no":
        start = end = None

    return SlotScore(
        slot_id=slot_id,
        present=present,
        quality=quality,
        note=note,
        start_index=start,
        end_index=end,
    )


def _safe_int(val, *, default: int) -> int:
    if val is None:
        return default
    val = str(val).strip()
    if val.upper() == "NONE":
        return default
    try:
        return int(re.match(r"-?\d+", val).group(0)) if re.match(r"-?\d+", val) else default
    except (TypeError, ValueError, AttributeError):
        return default


def _safe_index(val, max_index: int) -> Optional[int]:
    if val is None:
        return None
    val = str(val).strip()
    if val.upper() == "NONE" or not val:
        return None
    match = re.match(r"-?\d+", val)
    if not match:
        return None
    try:
        idx = int(match.group(0))
    except ValueError:
        return None
    if idx < 0 or idx > max_index:
        return None
    return idx


# --------------------------------------------------------------------------- #
# Provider dispatch
# --------------------------------------------------------------------------- #

def score_framework(
    framework: dict,
    transcript,
    *,
    provider: str,
) -> FrameworkScore:
    """Score a transcript against a framework using the configured provider."""
    tokens = transcript.tokens
    max_index = max(0, len(tokens) - 1)
    prompt = build_scoring_prompt(framework, tokens)

    if provider == "local":
        raw = _score_with_local(prompt)
    elif provider == "gemini":
        raw = _score_with_gemini(prompt)
    else:
        raise ValueError(f"Unknown framework scoring provider: {provider!r}")

    return parse_scoring_response(raw, framework, max_index)


def _score_with_local(prompt: str) -> str:
    from local_coach import LocalLlmClient
    return LocalLlmClient().complete(
        prompt, temperature=0.2, max_tokens=2048,
        chat_template_kwargs={"enable_thinking": False},
    )


def _score_with_gemini(prompt: str) -> str:
    from google.genai import types
    from coach import get_client, extract_text_from_response
    from config import GEMINI_MODEL

    client = get_client()
    contents = [
        types.Content(
            role="user",
            parts=[types.Part.from_text(text=prompt)],
        ),
    ]
    generate_config = types.GenerateContentConfig(
        temperature=0.2,
        max_output_tokens=2048,
    )
    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=contents,
        config=generate_config,
    )
    return extract_text_from_response(response).strip()


# --------------------------------------------------------------------------- #
# Prompt generation (ephemeral, AI-authored)
# --------------------------------------------------------------------------- #

_PREAMBLE_PATTERNS = [
    # "Here's a prompt:" / "Here is a prompt:" / "Here's: …" etc.
    re.compile(
        r"^here\s*(?:is|'s|’s)?\s+(?:a|one|your|the)?\s*(?:prompt|question|scenario)?\s*:?\s+",
        re.IGNORECASE,
    ),
    re.compile(r"^prompt\s*:?\s*", re.IGNORECASE),
    re.compile(r"^question\s*:?\s*", re.IGNORECASE),
    re.compile(r"^sure[!.,]?\s+", re.IGNORECASE),
    re.compile(r"^certainly[!.,]?\s+", re.IGNORECASE),
    re.compile(r"^okay[!.,]?\s+", re.IGNORECASE),
]


def generate_prompt(framework: dict, *, provider: str) -> str:
    """Ask the configured LLM for ONE fresh prompt matching the framework.

    Returns the cleaned prompt text. Raises RuntimeError if the model output
    is empty after cleanup or fails basic sanity checks.

    The output is intentionally a plain string, not a full prompt dict, so the
    caller controls the ephemeral id (e.g. `generated:<uuid>`).
    """
    if provider not in ("gemini", "local"):
        raise ValueError(f"Unknown prompt-generation provider: {provider!r}")

    instruction = _build_generation_prompt(framework)

    if provider == "local":
        from local_coach import LocalLlmClient
        raw = LocalLlmClient().complete(
            instruction, temperature=0.7, max_tokens=256,
            chat_template_kwargs={"enable_thinking": False},
        )
    else:
        from google.genai import types
        from coach import get_client, extract_text_from_response
        from config import GEMINI_MODEL

        client = get_client()
        contents = [
            types.Content(role="user", parts=[types.Part.from_text(text=instruction)]),
        ]
        config = types.GenerateContentConfig(temperature=0.7, max_output_tokens=256)
        response = client.models.generate_content(
            model=GEMINI_MODEL, contents=contents, config=config,
        )
        raw = extract_text_from_response(response).strip()

    return _clean_generated_prompt(raw)


def _build_generation_prompt(framework: dict) -> str:
    """Few-shot prompt that yields one clean question matching the framework."""
    name = framework["name"]
    description = framework.get("description", "")
    slot_names = " → ".join(s["name"] for s in framework["slots"])
    examples = "\n".join(
        f"- {p['text']}" for p in framework.get("prompts", [])[:3]
    )
    return f"""You are generating practice prompts for spoken English communication
training. The framework is "{name}": {description}

The speaker's answer should follow this structure: {slot_names}.

Examples of good prompts for this framework:
{examples}

Generate ONE new prompt in the same style. Requirements:
- Plausible workplace or professional scenario.
- One sentence, ending in a question mark or period.
- No preamble ("Here is..."), no quoting, no list formatting.
- Do NOT repeat any of the examples above.
- Output ONLY the prompt itself, nothing else.

Prompt:"""


def _clean_generated_prompt(raw: str) -> str:
    """Strip preamble, quotes, and validate the generated prompt."""
    text = (raw or "").strip()
    if not text:
        raise RuntimeError("Model returned an empty prompt.")

    # Keep only the first non-empty line — models sometimes add a trailing
    # explanation or extra "Prompt:" blocks.
    for line in text.splitlines():
        line = line.strip()
        if line:
            text = line
            break

    # Strip surrounding quotes/backticks.
    text = text.strip("`'\"“”‘’ ")

    # Strip common preambles ("Here's a prompt:", "Question:", "Sure! ...").
    for pattern in _PREAMBLE_PATTERNS:
        text = pattern.sub("", text, count=1)

    text = text.strip("`'\"“”‘’ ").strip()
    if not text:
        raise RuntimeError("Prompt was empty after stripping preamble.")

    # Sanity bounds: too short → likely a stub, too long → not a prompt.
    if len(text) < 15:
        raise RuntimeError(f"Generated prompt too short: {text!r}")
    if len(text) > 280:
        raise RuntimeError(f"Generated prompt too long ({len(text)} chars).")

    return text


# --------------------------------------------------------------------------- #
# Model-answer generation (rewrite of the learner's own transcript)
# --------------------------------------------------------------------------- #

_MODEL_ANSWER_RE = re.compile(
    r"^SLOT_(?P<slot>\w+)_TEXT:\s*(?P<val>.+)$", re.IGNORECASE
)


def _build_model_answer_prompt(
    framework: dict, transcript_text: str, prompt_text: str
) -> str:
    name = framework["name"]
    slot_lines = []
    for slot in framework["slots"]:
        slot_lines.append(f'- "{slot["id"]}" ({slot["name"]}): {slot["description"]}')
    slot_spec = "\n".join(slot_lines)

    output_lines = [
        f"SLOT_{slot['id']}_TEXT: <one or two sentences for the {slot['name']} slot>"
        for slot in framework["slots"]
    ]
    output_spec = "\n".join(output_lines)

    return f"""You are coaching an ESL professional speaker. Rewrite their spoken
response through the {name} framework so they have a worked example to learn
from.

Framework slots (rewrite must hit each one, in order):
{slot_spec}

The original practice prompt was:
{prompt_text}

The learner actually said:
{transcript_text}

Rewrite their answer with these rules:
- Keep their domain and content where attainable. If they mentioned a project
  for a government client, the rewrite is about that same project.
- Tighten vague or tautological phrases ("provide the results that they needed").
- Complete any unfinished thoughts and supply one concrete detail per slot
  (a number, a named decision, or a specific action) where the original was
  generic.
- Write in a register an ESL professional speaker can plausibly produce. Avoid
  flowery native idioms.
- Each slot's text is one or two sentences. Do not narrate ("In this slot…").
- Output EXACTLY one line per slot in this format, nothing else:

{output_spec}
"""


def _parse_model_answer_response(text: str, framework: dict) -> ModelAnswer:
    """Parse the text-section response into a ModelAnswer.

    Raises RuntimeError if any slot text is empty after parsing — an empty
    model answer is worse than no model answer.
    """
    raw: dict[str, str] = {}
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        m = _MODEL_ANSWER_RE.match(line)
        if m:
            raw[m.group("slot").lower()] = m.group("val").strip()

    slots: list[tuple[str, str, str]] = []
    for slot_def in framework["slots"]:
        sid = slot_def["id"]
        slot_text = raw.get(sid, "").strip()
        if not slot_text:
            raise RuntimeError(f"Model answer missing or empty for slot {sid!r}.")
        slots.append((sid, slot_def["name"], slot_text))

    return ModelAnswer(slots=slots)


def generate_model_answer(
    framework: dict,
    transcript_text: str,
    prompt_text: str,
    *,
    provider: str,
) -> ModelAnswer:
    """Ask the configured LLM to rewrite the learner's transcript through the framework."""
    if not (transcript_text or "").strip():
        raise RuntimeError("Cannot generate a model answer without a transcript.")
    if provider not in ("gemini", "local"):
        raise ValueError(f"Unknown model-answer provider: {provider!r}")

    instruction = _build_model_answer_prompt(framework, transcript_text, prompt_text)

    if provider == "local":
        from local_coach import LocalLlmClient
        raw = LocalLlmClient().complete(
            instruction, temperature=0.4, max_tokens=512,
            chat_template_kwargs={"enable_thinking": False},
        )
    else:
        from google.genai import types
        from coach import get_client, extract_text_from_response
        from config import GEMINI_MODEL

        client = get_client()
        contents = [
            types.Content(role="user", parts=[types.Part.from_text(text=instruction)]),
        ]
        config = types.GenerateContentConfig(temperature=0.4, max_output_tokens=512)
        response = client.models.generate_content(
            model=GEMINI_MODEL, contents=contents, config=config,
        )
        raw = extract_text_from_response(response).strip()

    return _parse_model_answer_response(raw, framework)


# --------------------------------------------------------------------------- #
# Overall score + pass/fail
# --------------------------------------------------------------------------- #

def compute_overall(score: FrameworkScore, framework: dict) -> tuple[float, bool]:
    """Return (overall_score 0-10, passed)."""
    from config import FRAMEWORK_PASS_THRESHOLD

    slots = score.slots
    if not slots:
        return 0.0, False

    overall = sum(s.quality for s in slots) / (len(slots) * 5.0) * 10.0

    # Rubric deduction: must_include_metric requires a number in that slot's
    # span. We can only check this if we have a transcript-derived hint via
    # the slot note; for v1, the LLM is asked to encode the absence in its
    # note. As a conservative heuristic, deduct 1.0 if the must-metric slot
    # got quality < 4 (i.e. the model was unhappy with it).
    rubric = framework.get("scoring_rubric") or {}
    must_metric = rubric.get("must_include_metric")
    if must_metric:
        must_slot = score.slot(must_metric)
        if must_slot is not None and must_slot.quality < 4:
            overall = max(0.0, overall - 1.0)

    overall = round(overall, 1)
    all_present = all(s.present == "yes" for s in slots)
    passed = all_present and overall >= FRAMEWORK_PASS_THRESHOLD
    return overall, passed


# --------------------------------------------------------------------------- #
# Token-index → audio span resolution
# --------------------------------------------------------------------------- #

def resolve_slot_spans(score: FrameworkScore, transcript) -> dict:
    """Map each slot's token range to an audio span (start_s, end_s).

    Returns {slot_id: (start_s, end_s) | None}. None when timestamps are
    unavailable, the slot is missing, or indices are invalid for the words list.
    """
    spans: dict = {}
    words = transcript.words
    have_words = bool(words)

    for slot in score.slots:
        if not have_words or slot.start_index is None or slot.end_index is None:
            spans[slot.slot_id] = None
            continue
        if slot.start_index >= len(words) or slot.end_index >= len(words):
            spans[slot.slot_id] = None
            continue
        if slot.end_index < slot.start_index:
            spans[slot.slot_id] = None
            continue
        spans[slot.slot_id] = (
            words[slot.start_index].start_s,
            words[slot.end_index].end_s,
        )
    return spans


# --------------------------------------------------------------------------- #
# Per-slot prosody serialization
# --------------------------------------------------------------------------- #

def serialize_slot_prosody(p) -> Optional[dict]:
    """Project a ProsodyAnalysis (or None) to a JSON-safe dict for storage.

    Returns None for None inputs (slots that were missing, too short, or that
    failed to analyze).
    """
    if p is None:
        return None
    return {
        "duration_s": p.duration,
        "overall": p.overall_score,
        "tempo_wpm": p.tempo.estimated_wpm,
        "pitch_mean_hz": p.pitch.mean_hz,
        "pitch_min_hz": p.pitch.min_hz,
        "pitch_max_hz": p.pitch.max_hz,
        "volume_mean_db": p.volume.mean_db,
        "volume_contrast_db": p.volume.stress_contrast_db,
        "rhythm_pvi": p.rhythm.pvi,
        "rhythm_pvi_type": p.rhythm.pvi_type,
        "pause_count": p.pauses.pause_count,
    }
