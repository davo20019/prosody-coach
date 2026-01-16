# Prosody Coach

A CLI tool to improve English prosody for non-native speakers. Analyzes the 5 key components of prosody using scientific methods (Praat/Parselmouth) and provides AI-powered coaching via Google Gemini.

**Built for Spanish speakers learning English**, but useful for any non-native speaker wanting to improve their spoken English.

## What is Prosody?

Prosody is the "music" of speech - the patterns of rhythm, stress, and intonation that make speech sound natural and engaging. Native English speakers unconsciously use prosody to convey meaning and emotion.

## Features

- **5-Component Analysis**: Pitch, Volume, Tempo, Rhythm (nPVI), and Pauses
- **Scientific Measurements**: Uses Praat algorithms via Parselmouth (gold standard in phonetics)
- **AI Coaching**: Transcription, grammar correction, and personalized tips via Google Gemini
- **Practice Mode**: Built-in exercises for each prosody component
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

## Installation

### Prerequisites

- Python 3.10+
- A microphone
- (Optional) Google Gemini API key for AI coaching

### Setup

```bash
# Clone the repository
git clone https://github.com/davo20019/prosody-coach.git
cd prosody-coach

# Install dependencies
pip install -r requirements.txt
```

### Getting a Free Gemini API Key (Optional, for AI Coaching)

The AI coaching feature requires a Google Gemini API key. You can get one for free:

1. Go to [Google AI Studio](https://aistudio.google.com/apikey)
2. Sign in with your Google account
3. Click "Create API Key"
4. Copy the key and set it as an environment variable:

```bash
# Add to your shell profile (~/.bashrc, ~/.zshrc, etc.) for persistence
export GEMINI_API_KEY=your_api_key_here
```

**Note:** The free tier includes generous limits for personal use. The AI coaching features (transcription, grammar correction, personalized tips) require this key. Basic prosody analysis works without it.

## Usage

### Basic Analysis

```bash
# Record and analyze your speech
python3 main.py analyze

# With AI coaching (requires Gemini API key)
python3 main.py analyze --coach

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

### Measurement Standards

- **Pitch (F0)**: Extracted using Praat's autocorrelation method
- **Volume**: Praat intensity analysis (dB)
- **Tempo**: Syllable detection with validated WPM calculation
- **Rhythm (nPVI)**: Normalized Pairwise Variability Index per [Grabe & Low (2002)](https://www.lfsag.unito.it/ritmo/pvi_en.html)
- **Pauses**: Intensity-based silence detection (>200ms threshold)

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
