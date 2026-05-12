"""Forced alignment module for extracting phoneme-level timestamps.

Uses Bournemouth Forced Aligner (BFA) to align audio with transcript,
enabling true vocalic nPVI measurement based on vowel durations.

Reference: Grabe & Low (2002) methodology for vocalic interval measurement.
"""

import logging
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple

logger = logging.getLogger(__name__)

# ARPABET vowel phonemes (including stressed variants with digit suffixes)
# These are the phonemes BFA outputs for English vowels
ENGLISH_VOWELS = {
    # Monophthongs
    "AA", "AA0", "AA1", "AA2",  # odd, father
    "AE", "AE0", "AE1", "AE2",  # at, bat
    "AH", "AH0", "AH1", "AH2",  # hut, but (also schwa when unstressed)
    "AO", "AO0", "AO1", "AO2",  # ought, bought
    "EH", "EH0", "EH1", "EH2",  # ed, bet
    "ER", "ER0", "ER1", "ER2",  # hurt, bird (r-colored)
    "IH", "IH0", "IH1", "IH2",  # it, bit
    "IY", "IY0", "IY1", "IY2",  # eat, beat
    "UH", "UH0", "UH1", "UH2",  # hood, book
    "UW", "UW0", "UW1", "UW2",  # two, boot
    # Diphthongs
    "AW", "AW0", "AW1", "AW2",  # out, cow
    "AY", "AY0", "AY1", "AY2",  # my, buy
    "EY", "EY0", "EY1", "EY2",  # ate, say
    "OW", "OW0", "OW1", "OW2",  # oat, show
    "OY", "OY0", "OY1", "OY2",  # boy, toy
}


@dataclass
class PhonemeAlignment:
    """A single phoneme with its time boundaries."""
    phoneme: str
    start: float  # seconds
    end: float    # seconds

    @property
    def duration(self) -> float:
        """Duration of the phoneme in seconds."""
        return self.end - self.start

    @property
    def is_vowel(self) -> bool:
        """Check if this phoneme is a vowel."""
        # Strip any stress markers (0, 1, 2) for base phoneme check
        base_phoneme = self.phoneme.rstrip("012")
        return base_phoneme in ENGLISH_VOWELS or self.phoneme in ENGLISH_VOWELS


@dataclass
class WordAlignment:
    """A word with its phoneme alignments."""
    word: str
    start: float
    end: float
    phonemes: List[PhonemeAlignment]


@dataclass
class AlignmentResult:
    """Result of forced alignment containing word and phoneme timings."""
    words: List[WordAlignment]
    phonemes: List[PhonemeAlignment]
    audio_duration: float
    alignment_successful: bool
    error_message: Optional[str] = None

    @property
    def vowel_phonemes(self) -> List[PhonemeAlignment]:
        """Get only the vowel phonemes."""
        return [p for p in self.phonemes if p.is_vowel]

    @property
    def vowel_durations(self) -> List[float]:
        """Get durations of all vowels in seconds."""
        return [p.duration for p in self.vowel_phonemes]


def is_aligner_available() -> Tuple[bool, str]:
    """
    Check if Bournemouth Forced Aligner and its dependencies are available.

    Returns:
        Tuple of (is_available, reason_if_not)
    """
    # Check for espeak-ng
    if not shutil.which("espeak-ng"):
        return False, "espeak-ng not installed (brew install espeak-ng)"

    # Check for BFA
    try:
        __import__("bfa")
        return True, ""
    except ImportError:
        return False, "bournemouth-forced-aligner not installed"
    except Exception as e:
        return False, f"BFA import error: {e}"


def forced_align(
    audio_path: Path,
    text: str,
    device: str = "cpu",
) -> AlignmentResult:
    """
    Perform forced alignment using Bournemouth Forced Aligner.

    Args:
        audio_path: Path to the audio file
        text: Expected transcript text
        device: Device to run on ("cpu" or "cuda")

    Returns:
        AlignmentResult with phoneme and word alignments
    """
    # Check availability first
    available, reason = is_aligner_available()
    if not available:
        return AlignmentResult(
            words=[],
            phonemes=[],
            audio_duration=0.0,
            alignment_successful=False,
            error_message=reason,
        )

    try:
        from bfa import force_align

        # BFA returns a list of word alignments with phoneme details
        # Format: [{"word": "hello", "start": 0.1, "end": 0.5, "phonemes": [...]}, ...]
        alignment = force_align(
            str(audio_path),
            text,
            device=device,
        )

        words = []
        all_phonemes = []

        for word_data in alignment:
            word_phonemes = []

            for phoneme_data in word_data.get("phonemes", []):
                phoneme = PhonemeAlignment(
                    phoneme=phoneme_data["phoneme"],
                    start=phoneme_data["start"],
                    end=phoneme_data["end"],
                )
                word_phonemes.append(phoneme)
                all_phonemes.append(phoneme)

            word = WordAlignment(
                word=word_data["word"],
                start=word_data["start"],
                end=word_data["end"],
                phonemes=word_phonemes,
            )
            words.append(word)

        # Get audio duration
        audio_duration = 0.0
        if all_phonemes:
            audio_duration = max(p.end for p in all_phonemes)

        return AlignmentResult(
            words=words,
            phonemes=all_phonemes,
            audio_duration=audio_duration,
            alignment_successful=True,
        )

    except Exception as e:
        logger.warning(f"Forced alignment failed: {e}")
        return AlignmentResult(
            words=[],
            phonemes=[],
            audio_duration=0.0,
            alignment_successful=False,
            error_message=str(e),
        )


def extract_vowel_durations(alignment: AlignmentResult) -> List[float]:
    """
    Extract vocalic interval durations from alignment result.

    These are the durations needed for true vocalic nPVI calculation
    per Grabe & Low (2002).

    Args:
        alignment: AlignmentResult from forced_align()

    Returns:
        List of vowel durations in seconds
    """
    if not alignment.alignment_successful:
        return []

    return alignment.vowel_durations


def get_alignment_summary(alignment: AlignmentResult) -> dict:
    """
    Get a summary of the alignment for logging/debugging.

    Args:
        alignment: AlignmentResult from forced_align()

    Returns:
        Dictionary with alignment statistics
    """
    vowel_durations = alignment.vowel_durations

    return {
        "successful": alignment.alignment_successful,
        "word_count": len(alignment.words),
        "phoneme_count": len(alignment.phonemes),
        "vowel_count": len(vowel_durations),
        "audio_duration": alignment.audio_duration,
        "mean_vowel_duration": sum(vowel_durations) / len(vowel_durations) if vowel_durations else 0,
        "error": alignment.error_message,
    }
