# Web UI smoke test

Run before each release. Takes ~5 minutes.

## Setup
- [ ] `pip install -e .`
- [ ] `ffmpeg -version` prints a version
- [ ] `prosody serve` opens a browser to http://127.0.0.1:7860

## Per browser (Chrome, Firefox, Safari)
- [ ] Practice page loads, sidebar shows all sections
- [ ] Click Record, speak ~5 seconds, click Stop
- [ ] Spinner shows "Analyzing..." then results card renders
- [ ] Component scores are present, AI coach paragraph is present
- [ ] Audio playback control plays the recording
- [ ] Navigate to History — the new session appears at the top
- [ ] Click into the session — detail page renders with the same scores
- [ ] Stats page renders trend chart without console errors
- [ ] Prompts page lists categories; clicking a prompt loads Practice with the prompt text shown
- [ ] Drills page shows status; "Set baseline" form accepts a number
- [ ] Settings page shows current provider and the local doctor table

## Failure modes
- [ ] Deny mic permission → red banner explains how to re-enable
- [ ] With ffmpeg uninstalled → red banner says "Run `prosody local doctor`"
- [ ] With no GEMINI_API_KEY and provider=gemini → Settings shows yellow warning
