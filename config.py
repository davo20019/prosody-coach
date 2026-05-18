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
    # Vocalic nPVI targets (Grabe & Low 2002 methodology)
    # Spanish ~40, English ~60
    "spanish_typical": 40,
    "english_target": 55,
    "english_native": 65,
    # IOI nPVI runs lower than vocalic nPVI for the same speech because
    # inter-syllable-peak intervals are more uniform than vowel
    # durations. Shifted thresholds keep the score buckets meaningful
    # when forced alignment is unavailable.
    "ioi_spanish_typical": 33,
    "ioi_english_target": 48,
    "ioi_english_native": 58,
    # Buffer around the syllable-/stress-timed boundary so a borderline
    # pvi doesn't flip the classification on tiny changes.
    "transitional_margin": 5,
}

PAUSE_CONFIG = {
    "min_pause_duration": 0.2,   # Seconds - minimum to count as pause
    "ideal_pause_duration": 0.5, # Seconds - good pause length
    "max_pause_duration": 2.0,   # Seconds - too long
    "good_pause_rate": 3,        # Pauses per 30 seconds
    "excellent_pause_rate": 5
}

# Forced alignment configuration for vocalic nPVI
ALIGNMENT_CONFIG = {
    "enabled": True,             # Set False to always use IOI-based nPVI
    "device": "cpu",             # "cpu" or "cuda" for GPU acceleration
    "max_audio_duration": 30,    # Seconds - skip alignment for longer audio
    "min_vowels_required": 3,    # Minimum vowels needed for vocalic nPVI
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

# Technique explanations for rhythm training
TECHNIQUE_EXPLANATIONS = {
    # Level 1: Word Stress
    "Hyper-pronunciation": "Exaggerate the stressed syllable: make it 2x LONGER, noticeably LOUDER, and HIGHER in pitch. Whisper the unstressed syllables.",
    "Rubber band stretch": "Imagine stretching a rubber band on stressed syllables. Hands together on weak syllables, stretch wide on strong ones.",
    "Front-weighted punch": "Hit the first syllable like a boxer's jab - quick and powerful. Let the rest trail off like an echo.",
    "Mountain pattern": "Pitch rises to the stressed syllable (peak), then falls. Draw a mountain in the air as you speak.",

    # Level 2: Function Word Reduction
    "Backward build-up": "Start from the last word and add words backward: 'do' → 'to do' → 'things to do' → 'lot of things to do'. This builds natural rhythm.",
    "Content vs function contrast": "Content words (nouns, verbs, adjectives) are LOUD and LONG. Function words (the, to, a, of) are quick whispers.",
    "Schwa reduction": "Reduce unstressed vowels to 'uh' (schwa): 'to' → 'tuh', 'the' → 'thuh', 'a' → 'uh'. Almost swallow these words.",

    # Level 3: Compound Stress
    "Contrastive pairs": "Practice pairs to hear the difference: 'BLACKbird' (the bird) vs 'black BIRD' (any bird that's black).",
    "Meaning determines stress": "Ask: Is it a specific thing (compound)? Stress FIRST. Is it describing a thing? Stress SECOND.",

    # Level 4: Thought Groups
    "Phrase chunking": "Group 3-5 words that belong together. Pause briefly between chunks. Each chunk has ONE main stress.",
    "Strategic pausing": "Pause at punctuation, before important info, and between ideas. Pauses give listeners time to process.",
    "Parenthetical insertion": "Lower your pitch and speed up for inserted info (like this), then return to normal.",

    # Level 5: Full Sentence Rhythm
    "Shadowing": "Listen to a model, then speak along 1-2 words behind. Match their rhythm exactly, like a shadow.",
    "Information hierarchy": "Most important words get the most stress. Background info is compressed and quick.",

    # Level 6: Connected Speech
    "Consonant-vowel linking": "When a word ends in a consonant and the next starts with a vowel, blend them: 'an apple' → 'ana-pple'.",
    "Consonant cluster reduction": "When consonants meet, some disappear: 'last time' → 'las time', 'next day' → 'nex day'.",
    "Gonna/wanna patterns": "'Going to' → 'gonna', 'want to' → 'wanna', 'got to' → 'gotta'. These are standard in casual speech.",
}

# Gemini settings (Phase 2)
# Set your API key via environment variable: export GEMINI_API_KEY=your_key
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
GEMINI_MODEL = "gemini-2.5-flash-lite"

# AI coaching provider
# gemini: send audio directly to Gemini for transcription + coaching
# local: use whisper.cpp for transcription and a local OpenAI-compatible LLM
COACH_PROVIDER = os.environ.get("PROSODY_COACH_PROVIDER", "gemini").strip().lower()

# Local AI settings
# WHISPER_CPP_BIN can be "whisper-cli" if it is on PATH, or an absolute path.
# WHISPER_MODEL should point to a whisper.cpp GGML .bin model file.
LOCAL_WHISPER_BIN = os.environ.get("WHISPER_CPP_BIN", "whisper-cli")
LOCAL_WHISPER_MODEL = os.environ.get("WHISPER_MODEL", "")
LOCAL_LLM_BASE_URL = os.environ.get("LOCAL_LLM_BASE_URL", "http://127.0.0.1:8080/v1")
LOCAL_LLM_MODEL = os.environ.get("LOCAL_LLM_MODEL", "gemma-local")
LOCAL_LLM_TIMEOUT = float(os.environ.get("LOCAL_LLM_TIMEOUT", "120"))
# Optional: point to a running whisper.cpp HTTP server (e.g. http://127.0.0.1:9000) to
# skip per-call model loading. When set, the local coach uses WhisperServerTranscriber.
LOCAL_WHISPER_SERVER_URL = os.environ.get("LOCAL_WHISPER_SERVER_URL", "")

# Gemini Live API settings (real-time streaming)
GEMINI_LIVE_MODEL = "gemini-2.0-flash-exp"
REALTIME_FEEDBACK_DELAY = 2.0  # Seconds before next drill
REALTIME_SESSION_TIMEOUT = 900  # 15 min max session
REALTIME_AUDIO_CHUNK_MS = 100  # Audio chunk size in milliseconds
