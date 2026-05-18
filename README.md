# Prosody Coach

A CLI tool to improve English prosody for non-native speakers. Analyzes the 5 key components of prosody using scientific methods (Praat/Parselmouth) and provides AI-powered coaching via Google Gemini.

**Built for Spanish speakers learning English**, but useful for any non-native speaker wanting to improve their spoken English.

## What is Prosody?

Prosody is the "music" of speech - the patterns of rhythm, stress, and intonation that make speech sound natural and engaging. Native English speakers unconsciously use prosody to convey meaning and emotion.

## Features

- **5-Component Analysis**: Pitch, Volume, Tempo, Rhythm (nPVI), and Pauses
- **Scientific Measurements**: Uses Praat algorithms via Parselmouth (gold standard in phonetics)
- **AI Coaching**: Transcription, grammar correction, and personalized tips via Google Gemini or a fully local Whisper + Gemma stack
- **Practice Mode**: Built-in exercises for each prosody component
- **Communication Frameworks**: Practice STAR, PREP, SCQA, SBI, and Story Arc answers with combined structure scoring + delivery measurement, plus an AI-generated "stronger version of your answer" annotated slot by slot
- **Playback**: Hear your recordings to self-assess
- **Progress Tracking**: Save recordings and track improvement over time

## The 5 Components

| Component | What It Measures | Target |
|-----------|------------------|--------|
| **Pitch** | Voice frequency variation (Hz) | 100-150 Hz range |
| **Volume** | Stress contrast between syllables (dB) | 6-10 dB contrast |
| **Tempo** | Speaking rate (WPM) | 130-160 WPM |
| **Rhythm** | Syllable timing pattern (nPVI) | 55-65 (stress-timed) |
| **Pauses** | Strategic silence placement | 3-5 per 30 seconds |

## Web UI

Prosody Coach ships with an optional local web UI. After installing the package, run:

```bash
prosody serve
```

This starts a small local server bound to `127.0.0.1:7860` and opens your browser. Use `--no-browser` to skip the auto-open or `--port` to change the port.

### Requirements
- Everything the CLI needs, plus:
- `ffmpeg` on your `PATH` (used to convert browser-recorded audio to WAV).
  - macOS: `brew install ffmpeg`
  - Debian/Ubuntu: `sudo apt install ffmpeg`
  - Windows: `choco install ffmpeg`

### What's available in the UI
- Practice (with custom text or a chosen prompt)
- Tailored Train sessions driven by your weakness history
- Prompts browser
- **Frameworks** (STAR, PREP, SCQA, SBI, Story Arc — structured speaking practice)
- History (list, detail with audio playback, 30-day stats with chart)
- Rhythm Drills (baseline, level practice, attempts)
- Spaced-repetition Sounds and Words pages
- Read-only Settings (current provider, API key presence, local AI diagnostic)

To change provider or API keys, edit `.env` and restart the server. The Settings page is read-only in v1.

## Installation

### Prerequisites

- Python 3.10+
- A microphone
- (Optional) Google Gemini API key for cloud AI coaching
- (Optional) whisper.cpp and llama.cpp for fully local AI coaching
- (Optional) espeak-ng for accurate vocalic nPVI measurement via forced alignment

### Setup

```bash
# Clone the repository
git clone https://github.com/davo20019/prosody-coach.git
cd prosody-coach

# Install dependencies
pip install -r requirements.txt

# Optional: Install espeak-ng for vocalic nPVI (more accurate rhythm measurement)
# macOS
brew install espeak-ng

# Ubuntu/Debian
sudo apt-get install espeak-ng
```

### Getting a Free Gemini API Key (Optional, for Cloud AI Coaching)

Cloud Gemini coaching requires a Google Gemini API key. You can get one for free:

1. Go to [Google AI Studio](https://aistudio.google.com/apikey)
2. Sign in with your Google account
3. Click "Create API Key"
4. Copy the key and set it as an environment variable:

```bash
# Add to your shell profile (~/.bashrc, ~/.zshrc, etc.) for persistence
export GEMINI_API_KEY=your_api_key_here
```

**Note:** The free tier includes generous limits for personal use. Gemini coaching requires this key. Local coaching does not, but it requires the local runtimes and models below. Basic prosody analysis works without any AI provider.

### Fully Local AI Coaching (Optional)

Local mode keeps audio and coaching on your machine:

1. `whisper.cpp` transcribes the recording.
2. Prosody Coach computes local pitch, volume, tempo, rhythm, and pause metrics.
3. `llama.cpp` serves Gemma through an OpenAI-compatible local HTTP API.
4. Gemma receives only the transcript plus metrics and returns coaching text.

Install the local runtimes:

```bash
brew install whisper-cpp llama.cpp
```

Download a Whisper model. `base.en` is fast; `small.en` or `medium.en` can be more accurate:

```bash
mkdir -p "$HOME/models/whisper"
curl -L -o "$HOME/models/whisper/ggml-base.en.bin" \
  "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-base.en.bin"
```

Download a Gemma model. The repo ships a helper for the common variants:

```bash
./scripts/download-gemma4.sh e4b           # ~2.5 GB, fast scoring (recommended start)
./scripts/download-gemma4.sh 26b           # ~16 GB, 26B MoE with 4B active params (best quality for 48 GB Macs)
./scripts/download-gemma4.sh e2b Q8_0      # smaller still, with explicit quant
```

Start the local servers with the bundled scripts. Each one foregrounds the
process (Ctrl-C to stop) and respects env-var overrides for binary, model,
port, and context size — see the script headers for the full list.

```bash
# Terminal A — keep llama-server resident on port 8090 (matches LOCAL_LLM_BASE_URL).
LLAMA_SERVER_MODEL=/path/to/your-gemma-4.gguf ./scripts/start-local-llm.sh

# Terminal B — keep whisper-server resident on port 9000 (gives word timestamps,
# which enables per-slot delivery scoring in framework practice).
WHISPER_SERVER_MODEL="$HOME/models/whisper/ggml-base.en.bin" \
  ./scripts/start-whisper-server.sh
```

Configure Prosody Coach:

```bash
export PROSODY_COACH_PROVIDER=local
export WHISPER_CPP_BIN="$(which whisper-cli)"
export WHISPER_MODEL="$HOME/models/whisper/ggml-base.en.bin"
export LOCAL_LLM_BASE_URL="http://127.0.0.1:8090/v1"
export LOCAL_LLM_MODEL="gemma-local"   # any tag; matched against the llama-server --alias flag
# Optional: route transcription through the running whisper-server (faster).
# Omit this to fall back to the whisper-cli subprocess on each call.
export LOCAL_WHISPER_SERVER_URL="http://127.0.0.1:9000"
```

Check the setup:

```bash
python3 main.py local doctor
```

Use local coaching:

```bash
python3 main.py analyze --coach --provider local
python3 main.py practice --provider local
python3 main.py train --provider local
```

Gemini remains available:

```bash
python3 main.py analyze --coach --provider gemini
```

Local mode cannot directly listen to audio with Gemma. Whisper handles speech-to-text, and Gemma coaches from the transcript plus measured audio metrics.

## Usage

### Basic Analysis

```bash
# Record and analyze your speech
python3 main.py analyze

# With AI coaching (Gemini by default, or use --provider local)
python3 main.py analyze --coach

# With fully local AI coaching
python3 main.py analyze --coach --provider local

# With playback to hear yourself
python3 main.py analyze --playback

# Save your recording
python3 main.py analyze --save

# All options
python3 main.py analyze --coach --playback --save
```

### Practice Mode

Practice specific prosody components with guided exercises:

```bash
# List all available exercises
python3 main.py practice --list

# Practice by category
python3 main.py practice stress        # Word emphasis
python3 main.py practice intonation    # Question patterns
python3 main.py practice rhythm        # Syllable timing
python3 main.py practice professional  # Meeting scenarios
python3 main.py practice passages      # Longer texts

# Specific exercise
python3 main.py practice --id rhythm_1

# Custom text
python3 main.py practice --text "Your custom text here"

# With playback and save
python3 main.py practice rhythm --playback --save
```

### Frameworks Practice

Practice structured speaking with five communication frameworks: **STAR**,
**PREP**, **SCQA**, **SBI**, and **Story Arc**. Each prompt asks you to give a
short spoken answer (30–120 seconds). Prosody Coach then scores both:

- **Structure** — an LLM tags whether each framework slot (e.g. STAR's
  Situation, Task, Action, Result) was filled, with a quality score and a
  short coaching note per slot. Grammar/idiomaticity flags and cultural
  pragmatic notes (e.g. under-claiming credit in STAR) are included.
- **Delivery** — the existing Praat-based pitch/volume/tempo/rhythm/pauses
  analysis, both aggregate and (when word timestamps are available) per slot.

```bash
# Web UI: visit http://127.0.0.1:7860/frameworks after `prosody serve`
prosody serve

# Or via the CLI:
python3 main.py framework star                      # first STAR prompt
python3 main.py framework prep --prompt-id prep_2
python3 main.py framework story --provider local
```

**Per-slot delivery requires `whisper-server`** with word timestamps
(`response_format=verbose_json`). The CLI `whisper-cli` path does not emit
reliable word-level timestamps, so per-slot prosody is suppressed (with a UI
note) on that path. Aggregate prosody and structure scoring work on every
configured backend, including Gemini-only setups.

To add or extend frameworks, edit `frameworks.py` — it's a plain dict
documented with a contributor schema. PRs welcome.

### Other Commands

```bash
# Learn about the 5 components
python3 main.py info

# Tips for Spanish speakers
python3 main.py tips
```

## Example Output

```
╭─────────────────── PROSODY ANALYSIS ───────────────────╮
│ Duration: 45.2 seconds                                  │
╰─────────────────────────────────────────────────────────╯

┌───────────┬─────────┬─────────────────────┬─────────────────────────┐
│ Component │ Score   │ Details             │ Feedback                │
├───────────┼─────────┼─────────────────────┼─────────────────────────┤
│ Pitch     │ 10/10   │ Range: 81-362 Hz    │ Excellent variation     │
│ Volume    │ 10/10   │ Contrast: 11.9 dB   │ Excellent dynamics      │
│ Tempo     │ 9/10    │ Speed: 116 WPM      │ Good pace               │
│ Rhythm    │ 5/10    │ PVI: 48             │ Spanish pattern (55+)   │
│ Pauses    │ 10/10   │ Count: 22           │ Excellent usage         │
└───────────┴─────────┴─────────────────────┴─────────────────────────┘

                    Overall Score: 8.8/10

Focus on rhythm: Reduce unstressed syllables: 'comfortable' -> 'COMF-ter-ble'
```

## Technical Details

### Libraries Used

- **Parselmouth**: Python wrapper for Praat (gold standard in phonetics research)
- **SciPy**: Signal processing for peak detection
- **NumPy**: Numerical computations
- **Rich**: Beautiful terminal output
- **Typer**: CLI framework
- **Google GenAI**: Gemini API for AI coaching
- **whisper.cpp**: Optional local transcription backend
- **llama.cpp**: Optional local OpenAI-compatible Gemma server

### Measurement Standards

- **Pitch (F0)**: Extracted using Praat's autocorrelation method
- **Volume**: Praat intensity analysis (dB)
- **Tempo**: Syllable detection with validated WPM calculation
- **Rhythm (nPVI)**: Normalized Pairwise Variability Index per [Grabe & Low (2002)](https://www.lfsag.unito.it/ritmo/pvi_en.html)
- **Pauses**: Intensity-based silence detection (>200ms threshold)

### nPVI Measurement Methods

The rhythm component uses nPVI (normalized Pairwise Variability Index) to measure speech timing patterns:

| Method | Description | Accuracy |
|--------|-------------|----------|
| **Vocalic nPVI** | True vowel durations via forced alignment | Most accurate (Grabe & Low standard) |
| **IOI nPVI** | Inter-onset intervals from intensity peaks | Approximation (fallback) |

**Vocalic nPVI** (when available):
- Uses [Bournemouth Forced Aligner](https://pypi.org/project/bournemouth-forced-aligner/) + espeak-ng
- Extracts phoneme-level timestamps from audio
- Calculates true vowel duration variability
- Requires: espeak-ng installed, expected text available, saved recording

**IOI nPVI** (fallback):
- Approximates syllable timing using intensity peaks
- Always available, no external dependencies
- Used when forced alignment unavailable or fails

## For Spanish Speakers

Spanish and English have fundamentally different prosody patterns:

| Aspect | Spanish | English |
|--------|---------|---------|
| Rhythm | Syllable-timed (equal length) | Stress-timed (variable) |
| Typical nPVI | ~40-50 | ~55-65 |
| Vowel reduction | Minimal | Extensive ("schwa") |
| Sentence stress | More uniform | Key words emphasized |

Common issues addressed:
- Monotone speech (flat pitch)
- Equal syllable length (no reduction)
- Missing word stress
- No strategic pauses
- Harsh/angry-sounding intonation

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

MIT License - see [LICENSE](LICENSE) file for details.

## Acknowledgments

- [Praat](https://www.fon.hum.uva.nl/praat/) by Paul Boersma and David Weenink
- [Parselmouth](https://github.com/YannickJadoul/Parselmouth) by Yannick Jadoul
- nPVI methodology by [Grabe & Low (2002)](https://www.lfsag.unito.it/ritmo/pvi_en.html)
