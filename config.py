"""Configuration and thresholds for prosody analysis."""

import os
from pathlib import Path

# Audio settings
SAMPLE_RATE = 44100
CHANNELS = 1

# Recording settings
DEFAULT_DURATION = 30  # Max recording duration in seconds

# Prosody target ranges (calibrated for natural English speech)
PITCH_CONFIG = {
    "min_target": 75,      # Hz - lower bound for healthy range
    "max_target": 250,     # Hz - upper bound for expressive speech
    "good_range": 100,     # Hz - minimum pitch variation for good score
    "excellent_range": 150 # Hz - pitch variation for excellent score
}

VOLUME_CONFIG = {
    "good_contrast_db": 6,      # dB difference between stressed/unstressed
    "excellent_contrast_db": 10,
    "min_dynamic_range": 15     # dB - minimum for expressive speech
}

TEMPO_CONFIG = {
    "min_wpm": 100,        # Too slow below this
    "max_wpm": 180,        # Too fast above this
    "ideal_wpm": 140,      # Target speaking rate
    "good_variation": 15,  # % variation in speed
    "excellent_variation": 25
}

RHYTHM_CONFIG = {
    # Pairwise Variability Index targets
    # Spanish ~40, English ~60
    "spanish_typical": 40,
    "english_target": 55,
    "english_native": 65
}

PAUSE_CONFIG = {
    "min_pause_duration": 0.2,   # Seconds - minimum to count as pause
    "ideal_pause_duration": 0.5, # Seconds - good pause length
    "max_pause_duration": 2.0,   # Seconds - too long
    "good_pause_rate": 3,        # Pauses per 30 seconds
    "excellent_pause_rate": 5
}

# Paths
DATA_DIR = Path(__file__).parent / "data"
RECORDINGS_DIR = DATA_DIR / "recordings"
DB_PATH = DATA_DIR / "progress.db"

# Ensure directories exist
DATA_DIR.mkdir(exist_ok=True)
RECORDINGS_DIR.mkdir(exist_ok=True)

# Gemini settings (Phase 2)
# Set your API key via environment variable: export GEMINI_API_KEY=your_key
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
GEMINI_MODEL = "gemini-2.0-flash"
