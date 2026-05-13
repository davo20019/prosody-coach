# Prosody Coach — Web UI Design

**Date:** 2026-05-12
**Status:** Approved (brainstorming complete; implementation plan pending)
**Revision:** 2 (addresses code review of revision 1)

## Goal

Add a local web UI to Prosody Coach that delivers full feature parity with the existing CLI surface. The UI is a friendlier entry point for users who don't live in the terminal, while the CLI remains the primary surface for power users. The tool stays open-source, single-machine, and installable via `pip`.

## Non-goals

- Hosted multi-user service. The UI binds to `127.0.0.1` only.
- Mobile browsers. Desktop-only for v1.
- Authentication, rate limiting, CSRF, accounts. Local single-user assumption.
- Replacing the CLI. Both surfaces ship side-by-side from the same package.
- Real-time streaming feedback (`rhythm --realtime`). Out of v1 scope; consistent with the "no streaming" decision.
- Editable settings via the web UI. Settings page is read-only system info in v1; users edit `.env` and restart to change provider/keys.

## Stack

- **Backend:** FastAPI + Uvicorn
- **Templates:** Jinja2, server-rendered
- **Interactivity:** HTMX (vendored, ~50 KB), three interaction patterns total
- **Styling:** Hand-rolled `app.css` (~10 pages of mostly forms and tables — no Tailwind, no Node, no build step)
- **Charts:** Chart.js (vendored, ~200 KB)
- **Audio capture:** browser `MediaRecorder` (webm/opus), uploaded to the server and transcoded to WAV with `ffmpeg`
- **Audio playback:** native `<audio controls>` against a server route serving the recording
- **No CDN scripts.** Local tool that handles API keys should not ping third-party CDNs on each page load.

## CLI surface to cover (v1 parity scope)

Mapping every existing CLI command to a web destination. Anything not listed is intentionally out of scope.

| CLI command | Web destination |
|---|---|
| `prosody record` (default analyze) | Practice page, with prompt cleared |
| `prosody practice [--id ID] [--text TEXT] [--list]` | Practice page (prompt picker + custom-text textarea + record) |
| `prosody prompts list/category` | Prompts page |
| `prosody history [--mode]` | History page |
| `prosody history show ID` (implicit via menu) | History detail page |
| `prosody stats` | Stats page |
| `prosody best-worst` | Stats page (best/worst panel) |
| `prosody info` | Settings page (system info section) |
| `prosody tips` | Practice page sidebar (tips drawer) |
| `prosody train` (tailored from weaknesses) | **Train page** (NEW) — picks prompts using `get_user_weaknesses()` |
| `prosody rhythm --baseline` | Drills page → "Set baseline" button |
| `prosody rhythm --status` | Drills page → status panel (rendered on load) |
| `prosody rhythm --level N` | Drill run page |
| `prosody rhythm --realtime` | **OUT OF SCOPE** for v1 |
| `prosody local setup` | Settings page → Local AI section (renders setup commands) |
| `prosody local config` | Settings page → Local AI section (renders current config table) |
| `prosody local doctor` | Settings page → Local AI section (renders diagnostic table) |
| `prosody progress`, `prosody due-sounds`, `prosody due-words`, `prosody sounds`, `prosody words` | Sounds and Words pages |

## Architecture & module boundaries

The win: existing modules are well-factored as pure domain logic. The web layer is a thin HTTP/HTML shell that orchestrates them.

```
prosody-coach/
├── main.py                  # Typer CLI — unchanged, adds new `serve` command
├── analyzer.py              # reused as-is — signature is (audio_data, sample_rate, expected_text=None, audio_path=None)
├── coach.py / local_coach.py# reused as-is for their primitives
├── coach_pipeline.py        # NEW — provider-aware orchestrator the web layer calls (see below)
├── storage.py               # reused; SESSION_COLUMN_DEFINITIONS gets 3 new additive columns
├── prompts.py               # reused as-is
├── aligner.py               # reused as-is
├── recorder.py              # only file helpers used; capture happens in browser
├── feedback.py              # NOT used by web — Rich-only terminal renderer
└── web/
    ├── __init__.py
    ├── app.py               # FastAPI app factory, lifespan calls init_db()
    ├── deps.py              # FastAPI dependencies (db, settings, pipeline injection)
    ├── routes/
    │   ├── practice.py      # GET /practice, POST /practice/analyze
    │   ├── train.py         # GET /train, POST /train/analyze
    │   ├── prompts.py       # GET /prompts, GET /prompts/random, GET /prompts/category/{c}
    │   ├── history.py       # GET /history, GET /history/{id}, GET /history/stats
    │   ├── drills.py        # GET /drills, GET /drills/level/{n}, POST /drills/baseline, POST /drills/attempt
    │   ├── sounds.py        # GET /sounds, POST /sounds/{name}/practice
    │   ├── words.py         # GET /words, POST /words/{w}/practice
    │   ├── settings.py      # GET /settings (read-only)
    │   └── audio.py         # GET /audio/{uuid} — serves recorded WAV
    ├── templates/
    │   ├── base.html        # sidebar shell, vendored script tags
    │   ├── partials/        # HTMX-swappable fragments
    │   │   ├── analysis_card.html
    │   │   ├── coach_feedback.html
    │   │   ├── session_detail.html
    │   │   └── error_banner.html
    │   └── pages/           # full pages, one per sidebar section
    │       ├── practice.html
    │       ├── train.html
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
        ├── recorder.js          # MediaRecorder wrapper, ~80 lines
        ├── app.css              # hand-rolled
        └── vendor/
            ├── htmx.min.js
            ├── chart.umd.min.js
            └── UPDATE.md        # versions and refresh procedure
```

**Boundary rule:** route handlers do orchestration only. They call existing domain functions and `coach_pipeline.py`. No business logic lives in `web/`.

### `coach_pipeline.py` — NEW module (not just an extraction)

The web layer needs an entry point that the current CLI doesn't have. Today, `coach.analyze_parallel(audio_data, sample_rate, on_chunk)` is Gemini-only and takes no prompt/mode/provider. The new pipeline wraps both providers behind one signature:

```python
def analyze_session(
    audio_data: np.ndarray,
    sample_rate: int,
    *,
    expected_text: str | None,   # set in practice mode for vocalic nPVI
    mode: str,                   # 'analyze' | 'practice' | 'train' | 'drill'
    provider: str,               # 'gemini' | 'local'
    audio_path: Path | None,     # for forced alignment
) -> SessionResult:
    ...
```

`SessionResult` carries the `ProsodyAnalysis` plus coach output (`transcript`, `tips`, `grammar_issues`, `summary`, …) AND `provider` / `coach_status` / `coach_error` — the exact fields the new schema columns persist.

The function dispatches to either `coach.analyze_parallel(...)` (Gemini path) or the local-coach path (built on `local_coach.py` primitives). The CLI is free to migrate to this same entry over time, but doesn't have to as part of this work.

## Pages, routes, and HTMX patterns

| Sidebar item | URL | What it shows |
|---|---|---|
| **Practice** | `/` (alias `/practice`) | Prompt picker + custom-text textarea + record button + last-result panel |
| **Train** | `/train` | Tailored session driven by `get_user_weaknesses()` |
| **Prompts** | `/prompts` | Browse by category, click loads into Practice |
| **History** | `/history` | Session list (paginated), filters by mode |
| **History detail** | `/history/{id}` | One session's full analysis, audio playback, provider/status badge |
| **Stats** | `/history/stats` | Chart.js line/bar charts: scores over time, best/worst |
| **Drills** | `/drills` | Level picker, due drills, baseline button, status panel |
| **Drill run** | `/drills/level/{n}` | Drill prompt + record + result |
| **Sounds** | `/sounds` | Due sounds (spaced repetition), tracked sounds |
| **Words** | `/words` | Due words, tracked words |
| **Settings** | `/settings` | Read-only system info: provider, paths, env presence, espeak/whisper/llama install status, plus rendered `local setup` commands |

**Three HTMX interaction patterns — the entire interaction vocabulary:**

1. **Form POST → swap result region.** Recording form submits the audio blob; server returns rendered `partials/analysis_card.html`, swapped into `#result-region`. Used by Practice, Train, and Drill run.
2. **Click → swap detail panel.** History row click loads `partials/session_detail.html` into a side panel. Used by History, Sounds, Words.
3. **Click → load page.** Sidebar nav uses plain `<a>` links — full page loads. No SPA routing.

## Audio capture & analysis flow

End-to-end lifecycle for the core record→analyze interaction.

**Browser side (`web/static/recorder.js`):**
1. User clicks Record. `getUserMedia({ audio: { sampleRate: 16000, channelCount: 1 } })` → `MediaRecorder` with `mimeType: 'audio/webm;codecs=opus'`.
2. Visual state: pulsing red dot, elapsed timer.
3. User clicks Stop. `MediaRecorder.onstop` produces a `Blob`.
4. Blob is `POST`ed via `htmx.ajax` to `/practice/analyze` (or `/train/analyze`, `/drills/attempt`) as `multipart/form-data` with the prompt id and mode.
5. HTMX shows a `hx-indicator` (spinner + "Analyzing…") in `#result-region` while waiting; swaps the response HTML in on completion.

**Server side (`web/routes/practice.py`):**
1. Receive `UploadFile` (webm) + form fields.
2. Transcode to 16-bit mono 16 kHz WAV with `ffmpeg-python`. Save to `recordings/<uuid>.wav` (UUID name, not session id — see Storage section). Save is atomic: write to `<uuid>.wav.tmp`, then rename.
3. Load the WAV into memory: `audio_data, sample_rate = soundfile.read(wav_path)`.
4. Run `coach_pipeline.analyze_session(audio_data, sample_rate, expected_text=..., mode=..., provider=..., audio_path=wav_path)`. Inside, prosody analysis runs first, then the AI coach call. The two cannot be concurrent because both `coach.analyze_with_coach` (Gemini) and `local_coach.analyze_with_local_coach` accept the analysis as input. Cost: ~0.5-1s of analyzer time before the long-running AI call begins.
5. Persist with `save_session(...)`, passing the new `coach_provider`, `coach_status`, `coach_error` fields, and `recording_path=str(uuid_path)`. Returns the session id.
6. Render `partials/analysis_card.html` with the result and return as `HTMLResponse`.

**Why server-side transcode (not record WAV in browser):** WAV in the browser requires deprecated `ScriptProcessorNode` or AudioWorklet plumbing (~200+ lines). webm/opus → ffmpeg → wav on the server is one line and works on every desktop browser. Cost: one ffmpeg system dependency, declared in install instructions.

**Why UUID filenames (not session-id-keyed):** `save_session` returns the id only after the row is inserted. To name a file by id, we'd need either a two-step insert/update or rename-after-insert. UUID names sidestep both: the WAV exists on disk before the row, the row references it by path, no rename, no transaction, no race.

**Latency budget:**
- Transcode: ~200 ms for a 10 s clip
- Prosody analysis (Praat): ~500 ms–1 s
- Coach (Gemini/local): 2–8 s — dominates
- Total: 3–10 s, identical to the CLI today

**Concurrency:** single-user local tool, but FastAPI runs requests concurrently. `storage.get_db()` must work across threads — verify and fix with `check_same_thread=False` or per-request connections as part of this work if not already correct.

## Storage changes

Three additive columns to `SESSION_COLUMN_DEFINITIONS` in `storage.py`:

| Column | Type | Meaning |
|---|---|---|
| `coach_provider` | TEXT | `'gemini'` or `'local'` — which provider produced (or attempted) coaching |
| `coach_status` | TEXT | `'ok'` or `'failed'` |
| `coach_error` | TEXT (nullable) | Error message if `coach_status = 'failed'` |

The existing `_ensure_sessions_schema()` machinery handles `ALTER TABLE ADD COLUMN` automatically when new keys appear in the definitions dict, so no separate migration script is needed. `save_session()` gains three optional kwargs of the same names.

History detail and Stats pages display a small badge indicating provider, and a yellow strip + error message for failed coaching sessions.

## Error handling & edge cases

For a local single-user tool, "robust" means it doesn't silently swallow problems. Error messages can be technical.

**Browser-side failures (rendered as a red banner in `#result-region`):**
- Mic permission denied → "Browser blocked microphone access. Click the lock icon in the address bar to allow it."
- No mic found → "No microphone detected. Plug one in and refresh."
- Recording too short (< 1 s) → client-side guard, never hits server.

**Upload / server failures (HTTP error → HTMX swaps `partials/error_banner.html`):**
- Transcode failure (ffmpeg missing, corrupt blob) → "Audio could not be processed. Is ffmpeg installed? Run `prosody local doctor`."
- Praat failure → surface the `parselmouth` exception text.
- Coach failure (Gemini down, local model not loaded) → render the prosody analysis anyway with an "AI coaching unavailable: <reason>" footer. **Partial results are better than full failure.** The session is still saved with `coach_status='failed'` and `coach_error=<message>`, so History reflects what happened.

**Configuration edge cases:**
- No Gemini API key + no local stack → Settings page shows a yellow warning at the top: "No AI coaching configured. Set GEMINI_API_KEY in .env and restart, or install the local stack."
- Provider switch requires `.env` edit + restart in v1 (settings page is read-only).

**Storage edge cases:**
- Schema migration is handled by `_ensure_sessions_schema()` on startup. `web/app.py` calls `init_db()` once via a FastAPI lifespan handler.
- Disk full / write fails on the WAV → return 500 with a clear message; do not insert a session row when the WAV write failed.
- WAV write succeeded but DB insert failed → orphan WAV file. Acceptable in v1; a `prosody cleanup-orphans` CLI command can be added later if it ever matters.

**Concurrency edge case:**
- Two browser tabs open, recording simultaneously: both sessions save independently. UUID filenames mean no path collision. Documented, no work needed.

**Explicitly NOT handled:**
- Auth / rate limiting / CSRF — local-only tool bound to `127.0.0.1`.
- Mobile browsers — desktop only for v1.

## Testing strategy

Three layers, smallest first.

**1. Route handler tests (`tests/web/test_routes_*.py`) — bulk of the work.**
Use `fastapi.testclient.TestClient` against the app factory. For each route, verify status code, content type, and that the right template region is in the body. Fakes for `coach_pipeline.analyze_session` are passed via FastAPI dependency overrides — tests don't run Praat or call Gemini.
- `tests/web/conftest.py` provides a `client` fixture and a `tmp_db` fixture (in-memory SQLite swapped via dependency override).
- ~one test file per route module, ~5–10 tests each.

**2. Audio pipeline integration test (one test).**
Uploads a tiny real WAV (committed as a fixture, ~50 KB), runs the real `analyze_prosody` via the new `coach_pipeline`, mocks only the AI coach, and asserts the rendered analysis card contains a score AND that the persisted row has `coach_provider`/`coach_status` set. Catches transcoding, Praat, schema, and template-rendering breakage in one shot.

**3. Browser-side smoke (manual checklist).**
A short checklist in `docs/web-smoke-test.md`: open in Chrome/Firefox/Safari, record 5 s, see results, play back, navigate each sidebar section, verify Settings shows accurate doctor output. Run before each release.

**Explicitly NOT tested:**
- Jinja templates as standalone units — covered by route tests.
- `recorder.js` via JS test runner — too thin to be worth it.
- Storage internals — already exercised by existing test suites.

**Shape:** ~30 fast unit tests + 1 slow integration test + 1 manual checklist.

## Packaging & launch

**Goal:** a fresh user runs `pip install prosody-coach`, then `prosody serve`, and a browser opens to a working app.

**`pyproject.toml` changes:**
```toml
[project]
dependencies = [
    # ... existing ...
    "fastapi>=0.110",
    "uvicorn[standard]>=0.27",
    "jinja2>=3.1",
    "python-multipart>=0.0.9",   # required for file uploads
    "ffmpeg-python>=0.2",        # Python wrapper; system ffmpeg still required
]

[tool.setuptools]
py-modules = ["main", "analyzer", "coach", "coach_pipeline", "config", "feedback", "local_coach", "prompts", "recorder", "storage", "realtime"]

[tool.setuptools.packages.find]
include = ["web*"]

[tool.setuptools.package-data]
web = ["templates/**/*.html", "static/**/*", "static/vendor/*"]
```

This combines the existing flat `py-modules` list with explicit package discovery for `web/` and its template/static/vendor data. Verified that `setuptools` supports both in the same project.

**System dependencies (documented in README):**
- `ffmpeg` — required (new). `brew install ffmpeg`, `apt install ffmpeg`, `choco install ffmpeg`.
- `espeak-ng`, `whisper.cpp`, `llama.cpp` — already optional, unchanged.

**`prosody serve` (new Typer command in `main.py`):**
```
prosody serve [--port 7860] [--no-browser] [--reload]
```
- Hardcoded bind: `127.0.0.1`. **There is intentionally no `--host` flag.** The security model (no auth, no CSRF, API keys readable from the rendered settings page) only holds for a localhost-bound server.
- `--no-browser` skips auto-open.
- `--reload` enables uvicorn autoreload (developer ergonomics).
- Implementation: `uvicorn.run("web.app:create_app", host="127.0.0.1", factory=True, ...)` + `webbrowser.open(f"http://127.0.0.1:{port}")` after a 500 ms delay.

**Doctor reuse:** the existing `prosody local doctor` command already covers the "what's installed?" diagnostic. Web error messages refer to it. No new `doctor` command is added.

**Vendored assets:** `web/static/vendor/UPDATE.md` documents the pinned versions of HTMX and Chart.js plus a one-line `curl` command to refresh them. Refresh is a manual maintenance task, not part of build.

**Distribution:** same PyPI package, same install command. README gets a new "Web UI" section above the existing CLI section. CLI section stays unchanged.

**Explicitly NOT doing:** Docker image, installers, Electron wrapper, PyInstaller single-binary, Tailwind, Plotly, CDN script tags.

## Open questions for implementation

None. All design decisions have been made. The implementation plan can proceed.
