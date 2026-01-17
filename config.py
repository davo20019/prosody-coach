"""Configuration and thresholds for prosody analysis."""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env file from project root
load_dotenv(Path(__file__).parent / ".env")

# Audio settings
SAMPLE_RATE = 16000  # 16kHz is optimal for speech (captures 80-8000 Hz range)
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

# Rhythm training level configuration
# Each level has specific nPVI and rhythm score targets for mastery
# min_unique_drills: minimum different drills that must be passed
# require_priority_1: all priority 1 (essential) drills must be passed
RHYTHM_LEVEL_CONFIG = {
    1: {
        "name": "Word Stress",
        "description": "Learn basic word stress patterns",
        "npvi_target": 45,
        "min_rhythm_score": 5,
        "consecutive_passes": 3,
        "min_unique_drills": 6,
        "require_priority_1": True,
        "techniques": ["Hyper-pronunciation", "Rubber band stretch on stressed syllables"],
    },
    2: {
        "name": "Function Word Reduction",
        "description": "Reduce unstressed function words (to→tuh, the→thuh)",
        "npvi_target": 50,
        "min_rhythm_score": 6,
        "consecutive_passes": 3,
        "min_unique_drills": 5,
        "require_priority_1": True,
        "techniques": ["Schwa reduction", "Backward build-up"],
    },
    3: {
        "name": "Compound Stress",
        "description": "Master compound word stress (HOT dog vs hot DOG)",
        "npvi_target": 53,
        "min_rhythm_score": 6,
        "consecutive_passes": 3,
        "min_unique_drills": 4,
        "require_priority_1": True,
        "techniques": ["Contrastive pairs", "Meaning-based stress"],
    },
    4: {
        "name": "Thought Groups",
        "description": "Group words into natural phrases with pauses",
        "npvi_target": 55,
        "min_rhythm_score": 7,
        "consecutive_passes": 3,
        "min_unique_drills": 4,
        "require_priority_1": True,
        "techniques": ["Phrase chunking", "Strategic pausing"],
    },
    5: {
        "name": "Full Sentence Rhythm",
        "description": "Apply stress-timing to complete sentences",
        "npvi_target": 58,
        "min_rhythm_score": 7,
        "consecutive_passes": 3,
        "min_unique_drills": 5,
        "require_priority_1": True,
        "techniques": ["Shadowing", "Content vs function word contrast"],
    },
    6: {
        "name": "Connected Speech",
        "description": "Master natural reductions (gonna, wanna) and linking",
        "npvi_target": 60,
        "min_rhythm_score": 8,
        "consecutive_passes": 3,
        "min_unique_drills": 4,
        "require_priority_1": True,
        "techniques": ["Contractions", "Linking sounds", "Elision"],
    },
}

# Gemini settings (Phase 2)
# Set your API key via environment variable: export GEMINI_API_KEY=your_key
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
GEMINI_MODEL = "gemini-3-flash-preview"

# Gemini Live API settings (real-time streaming)
GEMINI_LIVE_MODEL = "gemini-2.0-flash-exp"
REALTIME_FEEDBACK_DELAY = 2.0  # Seconds before next drill
REALTIME_SESSION_TIMEOUT = 900  # 15 min max session
REALTIME_AUDIO_CHUNK_MS = 100  # Audio chunk size in milliseconds
