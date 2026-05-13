# Prosody Coach — Web UI Design

**Date:** 2026-05-12
**Status:** Approved (brainstorming complete; implementation plan pending)
**Author:** Brainstormed with Claude Code

## Goal

Add a local web UI to Prosody Coach that delivers full feature parity with the existing CLI. The UI is a friendlier entry point for users who don't live in the terminal, while the CLI remains the primary surface for power users. The tool stays open-source, single-machine, and installable via `pip`.

## Non-goals

- Hosted multi-user service. The UI binds to `127.0.0.1` only.
- Mobile browsers. Desktop-only for v1.
- Authentication, rate limiting, CSRF, accounts. Local single-user assumption.
- A new database schema. The existing SQLite schema in `storage.py` is reused unchanged.
- Replacing the CLI. Both surfaces ship side-by-side from the same package.

## Stack

- **Backend:** FastAPI + Uvicorn
- **Templates:** Jinja2, server-rendered
- **Interactivity:** HTMX (CDN), three interaction patterns total
- **Styling:** Tailwind via CDN, plus a small `app.css` for anything Tailwind can't cover
- **Charts:** Plotly (CDN)
- **Audio capture:** browser `MediaRecorder` (webm/opus), uploaded to the server and transcoded to WAV with `ffmpeg`
- **Audio playback:** native `<audio controls>` against a server route serving the recording
- **No JS framework, no Node/Vite build step.**

## Architecture & module boundaries

The win: existing modules are already well-factored as pure domain logic. The web layer is a thin HTTP/HTML shell that orchestrates them.

```
prosody-coach/
├── main.py                  # Typer CLI — unchanged, adds new `serve` and `doctor` commands
├── analyzer.py              # reused as-is
├── coach.py / local_coach.py# reused as-is
├── coach_pipeline.py        # NEW — extracts public analyze_parallel(...) entry from coach.py
├── storage.py               # reused as-is (one fix: ensure check_same_thread=False or per-request connections)
├── prompts.py               # reused as-is
├── aligner.py               # reused as-is
├── recorder.py              # only file helpers used; capture happens in browser
├── feedback.py              # NOT used by web — Rich-only terminal renderer
└── web/
    ├── __init__.py
    ├── app.py               # FastAPI app factory, mounts routes/static/templates, lifespan calls init_db()
    ├── deps.py              # FastAPI dependencies (db connection, settings, analyzer/coach injection)
    ├── routes/
    │   ├── practice.py      # GET /practice, POST /practice/analyze
    │   ├── prompts.py       # GET /prompts, GET /prompts/random, GET /prompts/category/{c}
    │   ├── history.py       # GET /history, GET /history/{id}, GET /history/stats
    │   ├── drills.py        # GET /drills, GET /drills/level/{n}, POST /drills/attempt
    │   ├── sounds.py        # GET /sounds, POST /sounds/{name}/practice
    │   ├── words.py         # GET /words, POST /words/{w}/practice
    │   ├── settings.py      # GET/POST /settings
    │   └── audio.py         # GET /audio/{session_id} — serves recorded WAV
    ├── templates/
    │   ├── base.html        # sidebar shell + Tailwind/HTMX/Plotly script tags
    │   ├── partials/        # HTMX-swappable fragments
    │   │   ├── analysis_card.html
    │   │   ├── coach_feedback.html
    │   │   ├── session_detail.html
    │   │   └── error_banner.html
    │   └── pages/           # full pages, one per sidebar section
    │       ├── practice.html
    │       ├── prompts.html
    │       ├── history.html
    │       ├── history_detail.html
    │       ├── stats.html
    │       ├── drills.html
    │       ├── drill_run.html
    │       ├── sounds.html
    │       ├── words.html
    │       └── settings.html
    └── static/
        ├── recorder.js      # MediaRecorder wrapper, ~80 lines
        └── app.css
```

**Boundary rule:** route handlers do orchestration only. They call existing domain functions and pass results to templates. No business logic lives in `web/`. CLI and web stay in lock-step on behavior.

**Justified refactor:** extract `coach_pipeline.py` from `coach.py` (currently 1,813 lines) so the public `analyze_parallel(...)` entry point is on a small clean surface. No other refactoring.

## Pages, routes, and HTMX patterns

| Sidebar item | URL | What it shows | CLI parity |
|---|---|---|---|
| **Practice** | `/` (alias `/practice`) | Current prompt, record button, last-result panel | `practice` / `record` |
| **Prompts** | `/prompts` | Browse by category, click loads into Practice | `prompts list/category` |
| **History** | `/history` | Session list (paginated), filters by mode | `history` |
| **History detail** | `/history/{id}` | One session's full analysis + audio playback | `history show` |
| **Stats** | `/history/stats` | 30-day Plotly charts: scores over time, best/worst | `stats`, `best-worst` |
| **Drills** | `/drills` | Level picker, due drills, current rhythm baseline | `rhythm-drill`, `levels` |
| **Drill run** | `/drills/level/{n}` | Drill prompt + record + result | `rhythm-drill --level n` |
| **Sounds** | `/sounds` | Due sounds (spaced repetition), tracked sounds | `due-sounds`, `sounds` |
| **Words** | `/words` | Due words, tracked words | `due-words`, `words` |
| **Settings** | `/settings` | Provider toggle (Gemini/local), API key entry, espeak status | `config.py` reads |

**Three HTMX interaction patterns — the entire interaction vocabulary:**

1. **Form POST → swap result region.** Recording form submits the WAV blob; server returns rendered `partials/analysis_card.html`, swapped into `#result-region`. Used by Practice and Drill run.
2. **Click → swap detail panel.** History row click loads `partials/session_detail.html` into a side panel. Used by History, Sounds, Words.
3. **Click → load page.** Sidebar nav uses plain `<a>` links — full page loads. No SPA routing.

## Audio capture & analysis flow

End-to-end lifecycle for the core record→analyze interaction.

**Browser side (`web/static/recorder.js`):**
1. User clicks Record. `getUserMedia({ audio: { sampleRate: 16000, channelCount: 1 } })` → `MediaRecorder` with `mimeType: 'audio/webm;codecs=opus'`.
2. Visual state: pulsing red dot, elapsed timer.
3. User clicks Stop. `MediaRecorder.onstop` produces a `Blob`.
4. Blob is `POST`ed via `htmx.ajax` to `/practice/analyze` as `multipart/form-data` with the prompt id and mode.
5. HTMX shows a `hx-indicator` (spinner + "Analyzing…") in `#result-region` while waiting; swaps the response HTML in on completion.

**Server side (`web/routes/practice.py`):**
1. Receive `UploadFile` (webm) + form fields.
2. Transcode to 16-bit mono 16 kHz WAV using `ffmpeg-python`. Save to a tmp file.
3. Run `analyze_prosody(wav_path)` (from `analyzer.py`) and `analyze_parallel(wav_path, prompt_text, mode)` (from `coach_pipeline.py`) **concurrently** via `asyncio.to_thread`. Saves ~1 s of wall time vs sequential.
4. Persist with `save_session(...)` from `storage.py`. Move WAV from tmp into the recordings dir, keyed by session id. Transactional: WAV first, then DB row, with cleanup on failure.
5. Render `partials/analysis_card.html` with the analysis + coaching dict and return as `HTMLResponse`.

**Why server-side transcode (not record WAV in browser):** WAV in the browser requires deprecated `ScriptProcessorNode` or AudioWorklet plumbing (~200+ lines of audio code). webm/opus → ffmpeg → wav on the server is one line and works on every desktop browser. Cost: one ffmpeg system dependency, declared in install instructions.

**Latency budget:**
- Transcode: ~200 ms for a 10 s clip
- `analyze_prosody` (Praat): ~500 ms–1 s
- `analyze_parallel` (Gemini/local): 2–8 s — dominates
- Total: 3–10 s, identical to the CLI today

**No streaming, no progress events.** Spinner with a "this takes a few seconds" hint. If partial results become desirable later, HTMX `hx-trigger="load"` polling can render a two-stage card without introducing WebSockets.

**Concurrency:** single-user local tool, but FastAPI runs requests concurrently. `storage.py` must use `check_same_thread=False` or per-request connections — verify and fix as part of this work if not already correct.

## Error handling & edge cases

For a local single-user tool, "robust" means it doesn't silently swallow problems. Error messages can be technical.

**Browser-side failures (rendered as a red banner in `#result-region`):**
- Mic permission denied → "Browser blocked microphone access. Click the lock icon in the address bar to allow it."
- No mic found → "No microphone detected. Plug one in and refresh."
- Recording too short (< 1 s) → client-side guard, never hits server.

**Upload / server failures (HTTP error → HTMX swaps `partials/error_banner.html`):**
- Transcode failure (ffmpeg missing, corrupt blob) → "Audio could not be processed. Is ffmpeg installed? Run `prosody-coach doctor`."
- Praat failure → surface the `parselmouth` exception text.
- Coach failure (Gemini down, local model not loaded) → render the prosody analysis anyway with a "AI coaching unavailable: <reason>" footer. **Partial results are better than full failure.** The user already recorded; the scientific scores are valid on their own. Session metadata records which provider produced (or failed to produce) the coaching.

**Configuration edge cases:**
- No Gemini API key + no local stack → Settings page shows a yellow warning at the top: "No AI coaching configured. Set GEMINI_API_KEY in .env or install the local stack."
- Provider switch mid-session → session metadata records which provider produced the coaching, so History can show "via Gemini" / "via local Gemma".

**Storage edge cases:**
- Schema migration is already handled by `_ensure_sessions_schema` on startup. `web/app.py` calls `init_db()` once via a FastAPI lifespan handler.
- Disk full / write fails on saving the WAV → return 500 with a clear message. Don't write the session row if the audio failed to persist (transactional WAV-then-DB with cleanup).

**Concurrency edge case:**
- Two browser tabs open, recording simultaneously: both sessions save independently. No locking needed because there's no shared mutable state in-memory. Documented, no work needed.

**Explicitly NOT handled:**
- Auth / rate limiting / CSRF — local-only tool bound to `127.0.0.1`.
- Mobile browsers — desktop only for v1.

## Testing strategy

Three layers, smallest first.

**1. Route handler tests (`tests/web/test_routes_*.py`) — bulk of the work.**
Use `fastapi.testclient.TestClient` against the app factory. For each route, verify status code, content type, and that the right template region is in the body. Fakes for `analyzer` and `coach_pipeline` are passed via FastAPI dependency overrides — tests don't run Praat or call Gemini.
- `tests/web/conftest.py` provides a `client` fixture and a `tmp_db` fixture (in-memory SQLite swapped via dependency override).
- ~one test file per route module, ~5–10 tests each.

**2. Audio pipeline integration test (one test).**
Uploads a tiny real WAV (committed as a fixture, ~50 KB), runs the real `analyze_prosody`, mocks only the AI coach, and asserts the rendered analysis card contains a score. Catches transcoding, Praat, and template-rendering breakage in one shot.

**3. Browser-side smoke (manual checklist, not automated).**
A short checklist in `docs/web-smoke-test.md`: open in Chrome/Firefox/Safari, record 5 s, see results, play back, navigate each sidebar section. Run before each release.

**Explicitly NOT tested:**
- Jinja templates as standalone units — covered by route tests.
- `recorder.js` via JS test runner — too thin to be worth it. Manual smoke catches it.
- Storage internals — already exercised by existing test suites.

**Shape:** ~30 fast unit tests + 1 slow integration test + 1 manual checklist.

## Packaging & launch

**Goal:** a fresh user runs `pip install prosody-coach`, then `prosody-coach serve`, and a browser opens to a working app.

**Dependencies added to `pyproject.toml`:**
```toml
fastapi      = ">=0.110"
uvicorn      = { extras = ["standard"], version = ">=0.27" }
jinja2       = ">=3.1"
python-multipart = ">=0.0.9"   # required for file uploads
ffmpeg-python    = ">=0.2"     # Python wrapper; system ffmpeg still required
```
Tailwind, HTMX, and Plotly load from CDN — no Node, no build step.

**System dependencies (documented in README):**
- `ffmpeg` — required (new). `brew install ffmpeg`, `apt install ffmpeg`, `choco install ffmpeg`.
- `espeak-ng`, `whisper.cpp`, `llama.cpp` — already optional, unchanged.

**`prosody-coach serve` (new Typer command in `main.py`):**
```
prosody-coach serve [--host 127.0.0.1] [--port 7860] [--no-browser] [--reload]
```
- Defaults: bind `127.0.0.1` only (never `0.0.0.0`).
- `--no-browser` skips auto-open (useful for tmux/headless dev).
- `--reload` enables uvicorn autoreload (developer ergonomics).
- Implementation: `uvicorn.run("web.app:create_app", factory=True, ...)` + `webbrowser.open(f"http://{host}:{port}")` after a 500 ms delay so the server is ready.

**`prosody-coach doctor` (new):**
Diagnostic table of what's installed and what isn't. Used by users debugging their setup and referenced in web error messages.
```
✓ Python 3.11.7
✓ ffmpeg 6.0
✗ espeak-ng           (optional — needed for vocalic nPVI)
✓ Gemini API key set
✗ whisper.cpp         (optional — needed for fully local mode)
```

**Distribution:** same PyPI package, same install command. README gets a new "Web UI" section above the existing CLI section. CLI section stays unchanged.

**Explicitly NOT doing:** Docker image, installers, Electron wrapper, PyInstaller single-binary.

## Open questions for implementation

None. All design decisions have been made. The implementation plan can proceed.
