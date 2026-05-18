# Framework practice: model-answer feature

## Goal

After a framework attempt, show the learner a *stronger version of what they
said* — their own transcript rewritten through the framework, with each slot
visually labeled. Turns each attempt into a worked example, not just a score.

## Decisions

| Question | Decision |
| --- | --- |
| When is the model answer shown? | Always auto-rendered on the attempt result page. |
| What is it based on? | Rewrite of the user's transcript (not a fresh exemplar). |
| Slot annotation | Color-coded inline spans + slot-name labels. |
| Persistence | Not stored; regenerated only on the result page. History detail does not show it (YAGNI). |
| Failure mode | Non-fatal. If generation fails, the rest of the result still renders. |

## Backend

### `framework_scoring.generate_model_answer`

```python
@dataclass
class ModelAnswer:
    slots: list[tuple[str, str, str]]   # (slot_id, slot_name, text), in framework order

def generate_model_answer(
    framework: dict,
    transcript_text: str,
    prompt_text: str,
    *,
    provider: str,
) -> ModelAnswer
```

- Builds a text-section prompt requesting one rewritten span per slot.
- Output format mirrors existing scoring contract:
  ```
  SLOT_<slot_id>_TEXT: <one or two sentences>
  ```
- Empty / whitespace-only slot text is rejected (raises `RuntimeError`).
- Provider dispatch reuses the existing pattern in `framework_scoring.py`:
  - `local` → `LocalLlmClient().complete(...)`
  - `gemini` → `coach.get_client()` + `GenerateContentConfig(temperature=0.4, max_output_tokens=512)`

### Prompt shape (per-slot rewrite)

The instruction tells the model to:
- Keep the learner's domain and content where attainable.
- Tighten vague or tautological phrases; complete unfinished thoughts.
- Add one concrete detail (a number, named decision, or specific action) where
  the learner's version was generic.
- Write in a register an ESL professional speaker can actually produce — not
  flowery native English.
- Emit exactly one `SLOT_<id>_TEXT:` line per slot, in framework order.

### Pipeline integration

`coach_pipeline.analyze_framework_session`:

1. Existing flow: transcript → score → per-slot prosody.
2. Add: after scoring succeeds, attempt `generate_model_answer(framework, transcript.text, prompt['text'], provider=provider)`.
3. Wrap in try/except. On failure, set `model_answer=None` and log a warning.
   The attempt still returns `status='ok'` if scoring succeeded.
4. New field on `FrameworkSessionResult`: `model_answer: Optional[ModelAnswer]`.

### Route

No new endpoint. The existing `POST /frameworks/attempt` returns the result
partial; the partial includes the model-answer block when present.

## Frontend

### New partial: `web/templates/partials/model_answer.html`

Renders only when `model_answer` is present and has non-empty slots.

Structure:

```html
<section class="model-answer">
  <h3>A stronger version of what you said</h3>
  <p class="model-answer__lead">
    Same content, tightened through the {{ framework.name }} structure.
  </p>
  <div class="model-answer__body">
    {% for slot_id, slot_name, text in model_answer.slots %}
    <div class="slot-chip slot-chip--{{ loop.index }}">
      <span class="slot-chip__label">{{ slot_name }}</span>
      <span class="slot-chip__text">{{ text }}</span>
    </div>
    {% endfor %}
  </div>
</section>
```

Embedded in `framework_result.html` after the slot scoring table, before the
aggregate-delivery card.

### CSS additions (`web/static/app.css`)

- Four slot color variables (`--slot-1` … `--slot-4`), muted and AA-contrast on
  the existing dark background.
- `.slot-chip` is a rounded block with a left-border accent in the slot color
  and the label rendered as a small uppercase eyebrow.

## Testing

In `tests/test_framework_scoring.py`:

1. `test_generate_model_answer_prompt_includes_framework_and_transcript` —
   instruction text mentions framework name, includes the user transcript and
   the original prompt, and asks for `SLOT_<id>_TEXT:` lines for each slot in
   the framework.
2. `test_parse_model_answer_response_returns_slots_in_order` — given a stub
   text response, the returned `ModelAnswer.slots` matches framework order.
3. `test_parse_model_answer_rejects_empty_slots` — whitespace-only slot text
   raises.

In `tests/web/test_routes_frameworks.py` (or pipeline-level test):

4. `test_analyze_framework_session_swallows_model_answer_failure` — when the
   generator raises, the result still has `status='ok'` and scoring fields
   populated, with `model_answer is None`.

## Out of scope

- Persisting the model answer to the sessions table.
- Showing it on history detail.
- A "Show another version" regenerate button.
- Voice playback / TTS of the model answer.
