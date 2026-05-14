# Content Feedback and Polished Revision on /practice

Date: 2026-05-14
Status: Draft (pending implementation plan)

## Motivation

The /practice page today gives prosody scores, pronunciation issues, and free-form coaching tips. The AI coach *already* produces a `suggested_revision` and a list of `grammar_issues`, but neither is rendered in the UI — they are silently saved to the database and never seen.

Users practicing free speech (analyze mode) want feedback on *what* they said, not only *how* they said it: was the idea clear, was it concise, did the tone match the situation, and how would a fluent speaker have phrased it. This spec adds that surface.

## Scope

In scope:
- Render existing `grammar_issues` and `suggested_revision` on the practice results card.
- Add a richer "content critique" — clarity, conciseness, tone/register — and a one-line rationale tied to the polished revision.
- Free-speech (`mode == "analyze"`) only.

Out of scope:
- Framework practice, drills, train, sounds, words pages — no UI changes.
- Numerical content scores in history charts or aggregates.
- A separate "regenerate polish" button.
- Latency optimizations such as parallel or follow-up LLM calls.

## User experience

When a user records free speech and the analysis returns successfully, the results card adds a "Content" section between the existing AI coach tips block and the audio player. The section contains up to three sub-blocks; each sub-block hides itself when its data is missing.

```
┌─ Content ───────────────────────────────────────┐
│ Clarity      8/10  easy to follow               │
│ Conciseness  6/10  "kind of" / "you know" pad   │
│ Tone         7/10  slightly casual for a meeting│
│                                                 │
│ Grammar fixes                                   │
│   ✗ "he don't"  →  "he doesn't"                 │
│       subject/verb agreement                    │
│                                                 │
│ Polished version                                │
│   "He doesn't agree with the proposal."         │
│   Why: trims hedges, fixes agreement.           │
└─────────────────────────────────────────────────┘
```

The section is rendered only when `mode == "analyze"`. In `practice` mode (reading a fixed prompt), the section is suppressed even if the LLM happened to produce content; reading a fixed prompt is about prosody, not content rewriting.

## Architecture

### Data flow

```
coach.py LLM prompt
  ├── adds CONTENT_FEEDBACK section
  └── parse_coaching_response
        └── CoachingResult.content_feedback : Optional[dict]

coach_pipeline._normalize_coaching
  └── adds "content_feedback" key to the flat coach dict

web/routes/practice.py
  ├── save_session(content_feedback=…)
  └── TemplateResponse(..., {"content_feedback": …, "mode": …,
                              "grammar_issues": …, "suggested_revision": …})

storage.py
  └── content_feedback TEXT column (JSON-encoded)

web/templates/partials/analysis_card.html
  └── includes partials/content_feedback.html when mode == "analyze"
```

### `CoachingResult` field

Add one optional attribute:

```python
content_feedback: Optional[dict] = None
# {
#   "clarity":      {"score": int 1-10, "note": str},
#   "conciseness":  {"score": int 1-10, "note": str},
#   "tone":         {"score": int 1-10, "note": str},
#   "revision_rationale": str
# }
```

Any sub-key may be missing (parser drops malformed lines rather than fabricating). The whole field is `None` when the model returns `None` or when parsing produces an empty dict — so the UI gate is simply `{% if content_feedback %}`.

### Prompt change

The new section is appended to both `build_coaching_prompt` and `build_coaching_prompt_standalone` in `coach.py`, after `SUGGESTED_REVISION:` and before `COACHING_TIPS:`:

```
CONTENT_FEEDBACK:
[Critique the *content* of what was said, independent of pronunciation/prosody.]
[If the speaker was reading a fixed prompt (not their own words), write: None]
[Otherwise output each line exactly:]
CLARITY: <1-10> | <one sentence: is the idea easy to follow?>
CONCISENESS: <1-10> | <one sentence: any padding, repetition, or rambling?>
TONE: <1-10> | <one sentence: register/tone appropriate? too stiff/too casual?>
RATIONALE: <one sentence on why your SUGGESTED_REVISION is an improvement>
```

The "fixed prompt" cue is included in both prompt variants. The practice-mode prompt (`build_practice_prompt`, when `expected_text` is set) appends the same section so the model can reliably emit `None` — wasted tokens are minimized when the user is reading a fixed sentence.

### Parser

In `parse_coaching_response`:
- Add `"CONTENT_FEEDBACK:"` to the `sections` dict.
- New helper `_parse_content_feedback(text: str) -> Optional[dict]`:
  - Strip; if empty or `text.strip().lower() == "none"` return `None`.
  - For each non-empty line, match `^(CLARITY|CONCISENESS|TONE):\s*(\d+)\s*\|\s*(.+)$` (case-insensitive); clamp score to 1–10; store `{ "score": int, "note": str }` under the lowercased key.
  - For `RATIONALE:` capture text after the colon as `revision_rationale`.
  - Ignore unrecognized lines (forward-compatible).
  - If the resulting dict is empty, return `None`.
- Pass the result to `CoachingResult(..., content_feedback=_parse_content_feedback(sections["CONTENT_FEEDBACK:"]))`.

### Local provider (`local_coach.py`)

`local_coach` parses its own LLM output through a separate path. If its model is also asked the same prompt template, no additional code is needed; if it diverges, the field defaults to `None` and the UI degrades gracefully. We do not add work here in this iteration — the local provider continues to produce existing fields, plus `None` for `content_feedback`. A follow-up can wire it in symmetrically.

### Pipeline

`coach_pipeline._normalize_coaching` adds one line:

```python
"content_feedback": getattr(coaching, "content_feedback", None),
```

### Storage

`SESSION_COLUMN_DEFINITIONS["content_feedback"] = "TEXT"`. The existing `_ensure_sessions_schema` migration logic adds the column to existing databases.

`save_session(...)` accepts `content_feedback: Optional[dict] = None`, JSON-encodes it on write (mirroring `grammar_issues` / `pronunciation_issues`). `get_session` JSON-decodes it on read.

### Route

`web/routes/practice.py` `analyze`:
- Forward `content_feedback=coach.get("content_feedback")` to `save_session`.
- Add to the template context: `mode`, `grammar_issues`, `suggested_revision`, `content_feedback` (the existing context already has `coach`, `provider`, `analysis`, `recording_name`, `session_id`).

`web/routes/history.py` (detail page) does not need changes for first cut — the existing transcript / coach summary is enough. A follow-up may surface the new block on `history_detail.html`.

### Templates

New partial: `web/templates/partials/content_feedback.html`. Three sub-blocks, each guarded:
1. Critique table (clarity / conciseness / tone rows) — only when `content_feedback` has at least one of those keys.
2. Grammar fixes — only when `grammar_issues` is non-empty.
3. Polished version + rationale — only when `suggested_revision` is set.

`analysis_card.html` includes the partial:

```jinja
{% if mode == "analyze" and (content_feedback or grammar_issues or suggested_revision) %}
  {% include "partials/content_feedback.html" %}
{% endif %}
```

Placed between the existing `coach` block and the `<audio>` element.

## Error handling and edge cases

- **Model omits the section.** Parser returns `None`. Partial not rendered. No banner.
- **Model returns malformed scores.** Lines that fail the regex are skipped. Surviving rows render. Empty dict → partial not rendered.
- **Practice mode (fixed prompt).** Even if the model emitted content critique, the template gate suppresses the whole partial.
- **Provider failure (`coach is None`).** Existing warning banner path still fires; no new field to render.
- **Old DB rows.** Column is `NULL`; reads return `None`; nothing renders.
- **Local provider.** Returns no `content_feedback` field; `getattr(..., None)` yields `None`; nothing renders.

## Testing

New / updated tests:

1. `tests/test_coach_parsing.py` (new or extend existing) — `_parse_content_feedback` covering:
   - Full happy path (all four lines present).
   - `None` payload returns `None`.
   - Missing `RATIONALE` line still returns the three critique entries.
   - Out-of-range score (`12`) clamped to 10.
   - Malformed line (no `|`) skipped without raising.
   - Section absent in response → field is `None`.

2. `tests/web/test_coach_pipeline.py` — extend the existing CoachingResult fixture: when `content_feedback` is populated on the dataclass, `_normalize_coaching` exposes it under the `"content_feedback"` key.

3. `tests/web/test_routes_practice.py` — two new assertions:
   - POST `/practice/analyze` with custom_text (no `prompt_id`) renders the Content partial; HTML contains "Polished version".
   - POST `/practice/analyze` with `prompt_id` set does *not* render the Content partial.

4. `tests/test_storage.py` (or wherever `save_session` is tested) — round-trip: write a session with `content_feedback`, read it back, expect dict equality.

## Risks and mitigations

- **LLM ignores the new section.** The parser tolerates this. UI degrades by hiding the partial.
- **Token / latency cost.** Adding ~10 prompt lines and ~4 output lines is negligible relative to existing coach output. No new round-trip.
- **Schema migration on running DBs.** `_ensure_sessions_schema` already handles `ALTER TABLE ADD COLUMN` for new fields — same path used by the other coach fields.
- **Subjective scores.** Clarity / conciseness / tone are inherently fuzzy. Mitigated by keeping them out of aggregate dashboards and presenting them with short prose notes.

## Out of scope, follow-ups

- Surfacing the same partial on `history_detail.html`.
- Wiring `local_coach` to populate `content_feedback`.
- Tracking content trend lines (would require splitting the JSON into numeric columns).
- "Regenerate polish" button.
