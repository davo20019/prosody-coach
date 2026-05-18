"""Prosody analysis module using Parselmouth (Praat)."""

import logging
import numpy as np
import parselmouth
from parselmouth.praat import call
from dataclasses import dataclass
from pathlib import Path
from typing import List, Tuple, Optional

from config import (
    PITCH_CONFIG,
    VOLUME_CONFIG,
    TEMPO_CONFIG,
    RHYTHM_CONFIG,
    PAUSE_CONFIG,
    ALIGNMENT_CONFIG,
)

logger = logging.getLogger(__name__)


@dataclass
class PitchAnalysis:
    """Results of pitch analysis."""
    score: int  # 1-10
    min_hz: float
    max_hz: float
    mean_hz: float
    range_hz: float
    std_hz: float
    feedback: str


@dataclass
class VolumeAnalysis:
    """Results of volume/intensity analysis."""
    score: int  # 1-10
    min_db: float
    max_db: float
    mean_db: float
    dynamic_range_db: float
    stress_contrast_db: float
    feedback: str


@dataclass
class TempoAnalysis:
    """Results of tempo analysis."""
    score: int  # 1-10
    syllables_per_second: float
    estimated_wpm: float
    variation_percent: float
    feedback: str


@dataclass
class RhythmAnalysis:
    """Results of rhythm analysis."""
    score: int  # 1-10
    pvi: float  # Primary nPVI (vocalic if available, IOI as fallback)
    is_syllable_timed: bool
    feedback: str
    # New fields for vocalic nPVI
    pvi_type: str = "ioi"  # "vocalic" or "ioi"
    pvi_ioi: Optional[float] = None  # Inter-onset interval based nPVI
    pvi_vocalic: Optional[float] = None  # True vocalic nPVI from forced alignment
    vowel_count: Optional[int] = None  # Number of vowels used for vocalic nPVI
    # "syllable-timed", "transitional", "stress-timed", or "unknown"
    timing_class: str = "unknown"


@dataclass
class PauseAnalysis:
    """Results of pause analysis."""
    score: int  # 1-10
    pause_count: int
    total_pause_duration: float
    avg_pause_duration: float
    pause_ratio: float  # Pause time / total time
    pauses: List[Tuple[float, float]]  # (start, end) times
    feedback: str


@dataclass
class ProsodyAnalysis:
    """Complete prosody analysis results."""
    pitch: PitchAnalysis
    volume: VolumeAnalysis
    tempo: TempoAnalysis
    rhythm: RhythmAnalysis
    pauses: PauseAnalysis
    duration: float
    overall_score: float

    def to_dict(self) -> dict:
        """Convert to dictionary for storage."""
        return {
            "pitch_score": self.pitch.score,
            "volume_score": self.volume.score,
            "tempo_score": self.tempo.score,
            "rhythm_score": self.rhythm.score,
            "pause_score": self.pauses.score,
            "overall_score": self.overall_score,
            "duration": self.duration,
        }


def analyze_prosody(
    audio_data: np.ndarray,
    sample_rate: int,
    expected_text: Optional[str] = None,
    audio_path: Optional[Path] = None,
) -> ProsodyAnalysis:
    """
    Perform complete prosody analysis on audio data.

    Args:
        audio_data: Audio samples as numpy array
        sample_rate: Sample rate in Hz
        expected_text: Optional transcript for vocalic nPVI measurement
        audio_path: Optional path to audio file for forced alignment

    Returns:
        ProsodyAnalysis with all component results
    """
    # Create Parselmouth Sound object
    sound = parselmouth.Sound(audio_data, sampling_frequency=sample_rate)
    duration = sound.get_total_duration()

    # Run all analyses
    pitch_result = analyze_pitch(sound)
    volume_result = analyze_volume(sound)
    tempo_result = analyze_tempo(sound)
    rhythm_result = analyze_rhythm_with_alignment(sound, audio_path, expected_text)
    pause_result = analyze_pauses(sound)

    # Calculate overall score (weighted average)
    overall = (
        pitch_result.score * 0.25 +
        volume_result.score * 0.20 +
        tempo_result.score * 0.20 +
        rhythm_result.score * 0.20 +
        pause_result.score * 0.15
    )

    return ProsodyAnalysis(
        pitch=pitch_result,
        volume=volume_result,
        tempo=tempo_result,
        rhythm=rhythm_result,
        pauses=pause_result,
        duration=duration,
        overall_score=round(overall, 1)
    )


def analyze_pitch(sound: parselmouth.Sound) -> PitchAnalysis:
    """Analyze pitch (F0) characteristics."""
    # Extract pitch using autocorrelation method
    pitch = call(sound, "To Pitch", 0.0, 75, 500)

    # Get pitch values (excluding unvoiced frames)
    pitch_values = pitch.selected_array["frequency"]
    voiced_values = pitch_values[pitch_values > 0]

    if len(voiced_values) == 0:
        return PitchAnalysis(
            score=1,
            min_hz=0,
            max_hz=0,
            mean_hz=0,
            range_hz=0,
            std_hz=0,
            feedback="No voiced speech detected. Try speaking louder."
        )

    min_hz = float(np.min(voiced_values))
    max_hz = float(np.max(voiced_values))
    mean_hz = float(np.mean(voiced_values))
    range_hz = max_hz - min_hz
    std_hz = float(np.std(voiced_values))

    # Calculate score based on pitch range
    config = PITCH_CONFIG
    if range_hz >= config["excellent_range"]:
        score = 10
    elif range_hz >= config["good_range"]:
        score = 7 + int((range_hz - config["good_range"]) /
                        (config["excellent_range"] - config["good_range"]) * 3)
    elif range_hz >= 50:
        score = 4 + int((range_hz - 50) / (config["good_range"] - 50) * 3)
    else:
        score = max(1, int(range_hz / 50 * 4))

    score = min(10, max(1, score))

    # Generate feedback
    if range_hz < 50:
        feedback = f"Very monotone. Range: {range_hz:.0f} Hz. Aim for 100+ Hz variation."
    elif range_hz < config["good_range"]:
        feedback = f"Limited variation. Range: {range_hz:.0f} Hz. Native speakers use 100-150 Hz."
    elif range_hz < config["excellent_range"]:
        feedback = f"Good range: {range_hz:.0f} Hz. Push for more variation on key words."
    else:
        feedback = f"Excellent pitch variation: {range_hz:.0f} Hz."

    return PitchAnalysis(
        score=score,
        min_hz=round(min_hz, 1),
        max_hz=round(max_hz, 1),
        mean_hz=round(mean_hz, 1),
        range_hz=round(range_hz, 1),
        std_hz=round(std_hz, 1),
        feedback=feedback
    )


def analyze_volume(sound: parselmouth.Sound) -> VolumeAnalysis:
    """Analyze volume/intensity characteristics."""
    intensity = call(sound, "To Intensity", 75, 0.0, "yes")

    # Get intensity values
    intensity_values = []
    time_step = call(intensity, "Get time step")
    start_time = call(intensity, "Get start time")
    end_time = call(intensity, "Get end time")

    t = start_time
    while t <= end_time:
        value = call(intensity, "Get value at time", t, "cubic")
        if value is not None and not np.isnan(value):
            intensity_values.append(value)
        t += time_step

    if len(intensity_values) == 0:
        return VolumeAnalysis(
            score=1,
            min_db=0,
            max_db=0,
            mean_db=0,
            dynamic_range_db=0,
            stress_contrast_db=0,
            feedback="No intensity data detected."
        )

    intensity_values = np.array(intensity_values)

    # Filter out silence/noise (values below 40 dB are typically background)
    speech_values = intensity_values[intensity_values > 40]
    if len(speech_values) < 10:
        speech_values = intensity_values[intensity_values > np.percentile(intensity_values, 20)]

    if len(speech_values) == 0:
        speech_values = intensity_values

    min_db = float(np.percentile(speech_values, 5))   # 5th percentile to avoid outliers
    max_db = float(np.percentile(speech_values, 95))  # 95th percentile
    mean_db = float(np.mean(speech_values))
    dynamic_range_db = max_db - min_db

    # Estimate stress contrast (difference between high and low quartiles of speech)
    q75 = np.percentile(speech_values, 75)
    q25 = np.percentile(speech_values, 25)
    stress_contrast_db = q75 - q25

    # Calculate score
    config = VOLUME_CONFIG
    if stress_contrast_db >= config["excellent_contrast_db"]:
        score = 10
    elif stress_contrast_db >= config["good_contrast_db"]:
        score = 7 + int((stress_contrast_db - config["good_contrast_db"]) /
                        (config["excellent_contrast_db"] - config["good_contrast_db"]) * 3)
    elif stress_contrast_db >= 3:
        score = 4 + int((stress_contrast_db - 3) / (config["good_contrast_db"] - 3) * 3)
    else:
        score = max(1, int(stress_contrast_db / 3 * 4))

    score = min(10, max(1, score))

    # Generate feedback
    if stress_contrast_db < 3:
        feedback = f"Very flat volume. Stress contrast: {stress_contrast_db:.1f} dB. Aim for 6+ dB."
    elif stress_contrast_db < config["good_contrast_db"]:
        feedback = f"Low stress contrast: {stress_contrast_db:.1f} dB. Emphasize key words more."
    elif stress_contrast_db < config["excellent_contrast_db"]:
        feedback = f"Good volume variation: {stress_contrast_db:.1f} dB. Keep emphasizing key points."
    else:
        feedback = f"Excellent volume dynamics: {stress_contrast_db:.1f} dB."

    return VolumeAnalysis(
        score=score,
        min_db=round(min_db, 1),
        max_db=round(max_db, 1),
        mean_db=round(mean_db, 1),
        dynamic_range_db=round(dynamic_range_db, 1),
        stress_contrast_db=round(stress_contrast_db, 1),
        feedback=feedback
    )


def analyze_tempo(sound: parselmouth.Sound) -> TempoAnalysis:
    """Analyze speaking tempo/rate."""
    # Use intensity to detect syllable nuclei (peaks)
    intensity = call(sound, "To Intensity", 75, 0.0, "yes")

    # Find peaks in intensity (approximate syllable count)
    time_step = 0.01  # 10ms
    start_time = call(intensity, "Get start time")
    end_time = call(intensity, "Get end time")
    duration = end_time - start_time

    intensity_values = []
    times = []
    t = start_time
    while t <= end_time:
        value = call(intensity, "Get value at time", t, "cubic")
        if value is not None and not np.isnan(value):
            intensity_values.append(value)
            times.append(t)
        t += time_step

    if len(intensity_values) < 10:
        return TempoAnalysis(
            score=5,
            syllables_per_second=0,
            estimated_wpm=0,
            variation_percent=0,
            feedback="Audio too short for tempo analysis."
        )

    intensity_values = np.array(intensity_values)
    times = np.array(times)

    # Find peaks (syllable nuclei) using scipy for better detection
    from scipy.signal import find_peaks

    # Minimum distance between syllables: ~100ms (10 samples at 10ms time_step)
    # Syllables in fast speech can be as short as 80-100ms
    min_syllable_gap = int(0.10 / time_step)  # 100ms minimum between syllables

    # Threshold: intensity must be above 30th percentile to count as syllable nucleus
    threshold = np.percentile(intensity_values, 30)

    # Prominence: peak must be slightly higher than surrounding values
    prominence = np.std(intensity_values) * 0.15

    # Find peaks with distance and prominence constraints
    peak_indices, _ = find_peaks(
        intensity_values,
        distance=min_syllable_gap,
        height=threshold,
        prominence=prominence
    )

    syllable_count = len(peak_indices)

    # Calculate inter-syllable intervals
    peaks = list(peak_indices)
    all_intervals = np.diff([times[p] for p in peaks]) if len(peaks) > 1 else np.array([])

    # Speaking rate: syllables per second (simple, reliable)
    syllables_per_second = syllable_count / duration if duration > 0 else 0

    # Estimate WPM: use syllable count directly
    # Average ~1.4 syllables per word in conversational English
    estimated_wpm = (syllables_per_second * 60) / 1.4

    # Calculate tempo variation from valid intervals only
    # Filter out very long gaps (likely pauses) and very short gaps (noise)
    min_interval = 0.1   # 100ms minimum
    max_interval = 0.6   # 600ms maximum (longer = pause, not rhythm)

    speech_intervals = all_intervals[(all_intervals >= min_interval) & (all_intervals <= max_interval)]

    # Coefficient of Variation (CV) - standard measure of tempo consistency
    variation_percent = 0
    if len(speech_intervals) > 2:
        variation_percent = (np.std(speech_intervals) / np.mean(speech_intervals)) * 100
        # Cap at reasonable range (typical is 20-50%)
        variation_percent = min(variation_percent, 100)

    # Calculate score
    config = TEMPO_CONFIG
    wpm_score = 10
    wpm_in_range = True

    if estimated_wpm < config["min_wpm"]:
        # Too slow - steeper penalty
        wpm_score = max(2, int(estimated_wpm / config["min_wpm"] * 6))
        wpm_in_range = False
    elif estimated_wpm > config["max_wpm"]:
        # Too fast - steeper penalty (divide by 15 instead of 30)
        over = estimated_wpm - config["max_wpm"]
        wpm_score = max(2, 8 - int(over / 15))
        wpm_in_range = False
    else:
        # Good WPM range, score based on how close to ideal
        diff = abs(estimated_wpm - config["ideal_wpm"])
        wpm_score = max(7, 10 - int(diff / 20))

    # Variation score - but cap it if WPM is out of range
    variation_score = 5
    if variation_percent >= config["excellent_variation"]:
        variation_score = 10
    elif variation_percent >= config["good_variation"]:
        variation_score = 7
    elif variation_percent >= 5:
        variation_score = 5
    else:
        variation_score = 3

    # WPM is primary (70%), variation is secondary (30%)
    # But if WPM is out of range, cap the final score at 7
    score = int((wpm_score * 0.7 + variation_score * 0.3))
    if not wpm_in_range:
        score = min(score, 7)
    score = min(10, max(1, score))

    # Generate feedback
    feedback_parts = []
    if estimated_wpm < config["min_wpm"]:
        feedback_parts.append(f"Too slow: {estimated_wpm:.0f} WPM. Target: 130-160 WPM.")
    elif estimated_wpm > config["max_wpm"]:
        feedback_parts.append(f"Too fast: {estimated_wpm:.0f} WPM. Slow down for clarity.")
    else:
        feedback_parts.append(f"Good pace: {estimated_wpm:.0f} WPM.")

    if variation_percent < config["good_variation"]:
        feedback_parts.append("Speed too constant. Vary pace for emphasis.")
    elif variation_percent > config["excellent_variation"]:
        feedback_parts.append("Good speed variation.")

    return TempoAnalysis(
        score=score,
        syllables_per_second=round(syllables_per_second, 2),
        estimated_wpm=round(estimated_wpm, 0),
        variation_percent=round(variation_percent, 1),
        feedback=" ".join(feedback_parts)
    )


def calculate_npvi(intervals: List[float]) -> float:
    """
    Calculate normalized Pairwise Variability Index (nPVI).

    Formula: nPVI = 100 × [Σ |dₖ - dₖ₊₁| / ((dₖ + dₖ₊₁)/2)] / (m-1)

    Based on Grabe & Low (2002) methodology.

    Args:
        intervals: List of interval durations (vowel durations or IOIs)

    Returns:
        nPVI value (typically 40-70 for natural speech)
    """
    if len(intervals) < 2:
        return 0.0

    pvi_sum = 0.0
    pairs_used = 0
    for i in range(len(intervals) - 1):
        d1, d2 = intervals[i], intervals[i + 1]
        if d1 + d2 > 0:  # Avoid division by zero
            pvi_sum += abs(d1 - d2) / ((d1 + d2) / 2)
            pairs_used += 1

    return (pvi_sum / pairs_used) * 100 if pairs_used > 0 else 0.0


def _classify_timing(pvi: float, target: float, margin: float) -> Tuple[bool, str]:
    """
    Classify rhythm timing with a buffer around the boundary.

    Returns (is_syllable_timed, timing_class). The boolean preserves the
    legacy binary classification; timing_class adds a "transitional"
    band so borderline values don't flip on tiny changes.
    """
    if pvi < target - margin:
        return True, "syllable-timed"
    if pvi >= target + margin:
        return False, "stress-timed"
    return pvi < target, "transitional"


def rhythm_npvi_target_for_type(npvi_target: float, pvi_type: Optional[str]) -> float:
    """Convert a vocalic-scale level target to the active nPVI measurement scale."""
    if pvi_type != "ioi":
        return npvi_target

    config = RHYTHM_CONFIG
    vocalic_span = config["english_native"] - config["spanish_typical"]
    if vocalic_span <= 0:
        return npvi_target

    progress = (npvi_target - config["spanish_typical"]) / vocalic_span
    return config["ioi_spanish_typical"] + progress * (
        config["ioi_english_native"] - config["ioi_spanish_typical"]
    )


def rhythm_npvi_reference_range(pvi_type: Optional[str]) -> Tuple[float, float]:
    """Return the English target/native nPVI range for a measurement type."""
    config = RHYTHM_CONFIG
    if pvi_type == "ioi":
        return config["ioi_english_target"], config["ioi_english_native"]
    return config["english_target"], config["english_native"]


def analyze_rhythm_vocalic(vowel_durations: List[float], sound: parselmouth.Sound) -> RhythmAnalysis:
    """
    Analyze speech rhythm using true vocalic intervals from forced alignment.

    This is the Grabe & Low (2002) standard methodology using actual vowel
    durations extracted from forced alignment.

    Args:
        vowel_durations: List of vocalic interval durations in seconds.
            Adjacent vowels (V+V hiatus) should already be merged by the
            caller via aligner.extract_vocalic_intervals().
        sound: Parselmouth Sound object for duration

    Returns:
        RhythmAnalysis with vocalic nPVI measurement
    """
    config = RHYTHM_CONFIG
    min_vowels = ALIGNMENT_CONFIG.get("min_vowels_required", 3)

    if len(vowel_durations) < min_vowels:
        return RhythmAnalysis(
            score=5,
            pvi=0,
            is_syllable_timed=False,
            feedback=f"Not enough vowels detected ({len(vowel_durations)}) for vocalic nPVI.",
            pvi_type="vocalic",
            vowel_count=len(vowel_durations),
            timing_class="unknown",
        )

    # Calculate vocalic nPVI
    pvi = calculate_npvi(vowel_durations)

    # Determine timing class with a buffer around the boundary
    is_syllable_timed, timing_class = _classify_timing(
        pvi, config["english_target"], config["transitional_margin"]
    )

    # Calculate score
    if pvi >= config["english_native"]:
        score = 10
    elif pvi >= config["english_target"]:
        score = 7 + int((pvi - config["english_target"]) /
                        (config["english_native"] - config["english_target"]) * 3)
    elif pvi >= config["spanish_typical"]:
        score = 4 + int((pvi - config["spanish_typical"]) /
                        (config["english_target"] - config["spanish_typical"]) * 3)
    else:
        score = max(1, int(pvi / config["spanish_typical"] * 4))

    score = min(10, max(1, score))

    # Generate feedback
    if pvi < config["spanish_typical"]:
        feedback = f"Very syllable-timed (vocalic nPVI: {pvi:.0f}). Compress unstressed vowels more."
    elif pvi < config["english_target"]:
        feedback = f"Spanish rhythm pattern (vocalic nPVI: {pvi:.0f}). Target: {config['english_target']}+. Reduce unstressed vowels."
    elif pvi < config["english_native"]:
        feedback = f"Approaching English rhythm (vocalic nPVI: {pvi:.0f}). Keep practicing vowel contrast."
    else:
        feedback = f"Native-like rhythm (vocalic nPVI: {pvi:.0f}). Excellent stress-timing."

    return RhythmAnalysis(
        score=score,
        pvi=round(pvi, 1),
        is_syllable_timed=is_syllable_timed,
        feedback=feedback,
        pvi_type="vocalic",
        pvi_vocalic=round(pvi, 1),
        vowel_count=len(vowel_durations),
        timing_class=timing_class,
    )


def analyze_rhythm_with_alignment(
    sound: parselmouth.Sound,
    audio_path: Optional[Path] = None,
    expected_text: Optional[str] = None,
) -> RhythmAnalysis:
    """
    Analyze rhythm with optional forced alignment for vocalic nPVI.

    This orchestrator:
    1. Always calculates IOI-based nPVI as fallback
    2. Attempts vocalic nPVI when expected_text is provided
    3. Creates temporary file for alignment if no audio_path given
    4. Falls back gracefully on alignment failure

    Args:
        sound: Parselmouth Sound object
        audio_path: Path to audio file (optional - will create temp file if needed)
        expected_text: Expected transcript (required for alignment)

    Returns:
        RhythmAnalysis with best available nPVI measurement
    """
    import tempfile

    # Always calculate IOI-based nPVI first (as fallback)
    ioi_result = analyze_rhythm_ioi(sound)

    # Check if we should attempt vocalic nPVI
    if not ALIGNMENT_CONFIG.get("enabled", True):
        logger.debug("Alignment disabled in config, using IOI nPVI")
        return ioi_result

    if not expected_text:
        logger.debug("No expected text provided, using IOI nPVI")
        return ioi_result

    # Check audio duration limit
    max_duration = ALIGNMENT_CONFIG.get("max_audio_duration", 30)
    if sound.get_total_duration() > max_duration:
        logger.debug(f"Audio too long ({sound.get_total_duration():.1f}s > {max_duration}s), using IOI nPVI")
        return ioi_result

    # Check if aligner is available before creating temp file
    try:
        from aligner import (
            forced_align,
            extract_vocalic_intervals,
            is_aligner_available,
        )

        available, reason = is_aligner_available()
        if not available:
            logger.debug(f"Forced aligner unavailable: {reason}")
            return ioi_result
    except ImportError:
        logger.debug("Aligner module not available, using IOI nPVI")
        return ioi_result

    # Determine audio path - use provided path or create temporary file
    temp_file = None
    alignment_path = audio_path

    if not alignment_path:
        try:
            # Create temporary WAV file for alignment
            temp_file = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
            temp_file.close()
            alignment_path = Path(temp_file.name)
            sound.save(str(alignment_path), "WAV")
            logger.debug(f"Created temp file for alignment: {alignment_path}")
        except Exception as e:
            logger.warning(f"Failed to create temp file for alignment: {e}")
            return ioi_result

    try:
        # Perform alignment
        alignment = forced_align(
            alignment_path,
            expected_text,
            device=ALIGNMENT_CONFIG.get("device", "cpu"),
        )

        if not alignment.alignment_successful:
            logger.warning(f"Forced alignment failed: {alignment.error_message}")
            return ioi_result

        # Extract Grabe & Low vocalic intervals (merges V+V hiatus)
        vocalic_intervals = extract_vocalic_intervals(alignment)
        min_vowels = ALIGNMENT_CONFIG.get("min_vowels_required", 3)

        if len(vocalic_intervals) < min_vowels:
            logger.debug(f"Too few vocalic intervals ({len(vocalic_intervals)} < {min_vowels}), using IOI nPVI")
            return ioi_result

        # Calculate vocalic nPVI
        vocalic_result = analyze_rhythm_vocalic(vocalic_intervals, sound)

        # Merge with IOI result - vocalic is primary, IOI is backup
        return RhythmAnalysis(
            score=vocalic_result.score,
            pvi=vocalic_result.pvi,  # Primary is vocalic
            is_syllable_timed=vocalic_result.is_syllable_timed,
            feedback=vocalic_result.feedback,
            pvi_type="vocalic",
            pvi_ioi=ioi_result.pvi,  # Store IOI for reference
            pvi_vocalic=vocalic_result.pvi,
            vowel_count=len(vocalic_intervals),
            timing_class=vocalic_result.timing_class,
        )

    except Exception as e:
        logger.warning(f"Alignment error: {e}, using IOI nPVI")
        return ioi_result
    finally:
        # Clean up temporary file
        if temp_file:
            try:
                import os
                os.unlink(temp_file.name)
                logger.debug(f"Cleaned up temp file: {temp_file.name}")
            except Exception:
                pass  # Ignore cleanup errors


def analyze_rhythm_ioi(sound: parselmouth.Sound) -> RhythmAnalysis:
    """
    Analyze speech rhythm using inter-onset intervals (IOI).

    This is an approximation of nPVI using syllable nuclei timing rather than
    true vocalic intervals. Use analyze_rhythm_with_alignment() for true
    vocalic nPVI when transcripts are available.

    Reference values:
    - Syllable-timed languages (Spanish, French): nPVI ~40-50
    - Stress-timed languages (English, German): nPVI ~55-65

    Args:
        sound: Parselmouth Sound object

    Returns:
        RhythmAnalysis with IOI-based nPVI measurement
    """
    from scipy.signal import find_peaks

    # Extract intensity for syllable detection
    intensity = call(sound, "To Intensity", 75, 0.0, "yes")

    time_step = 0.01
    start_time = call(intensity, "Get start time")
    end_time = call(intensity, "Get end time")

    intensity_values = []
    times = []
    t = start_time
    while t <= end_time:
        value = call(intensity, "Get value at time", t, "cubic")
        if value is not None and not np.isnan(value):
            intensity_values.append(value)
            times.append(t)
        t += time_step

    if len(intensity_values) < 20:
        return RhythmAnalysis(
            score=5,
            pvi=0,
            is_syllable_timed=False,
            feedback="Audio too short for rhythm analysis.",
            pvi_type="ioi",
            pvi_ioi=0,
            timing_class="unknown",
        )

    intensity_values = np.array(intensity_values)
    times = np.array(times)

    # Find syllable nuclei using scipy.signal.find_peaks
    # Minimum 100ms between syllables (10 samples at 10ms step)
    min_syllable_gap = int(0.1 / time_step)
    threshold = np.percentile(intensity_values, 40)

    peak_indices, _ = find_peaks(
        intensity_values,
        distance=min_syllable_gap,
        height=threshold
    )
    peaks = list(peak_indices)

    if len(peaks) < 3:
        return RhythmAnalysis(
            score=5,
            pvi=0,
            is_syllable_timed=False,
            feedback="Not enough syllables detected for rhythm analysis.",
            pvi_type="ioi",
            pvi_ioi=0,
            timing_class="unknown",
        )

    # Calculate inter-syllable intervals
    intervals = []
    for i in range(len(peaks) - 1):
        interval = times[peaks[i+1]] - times[peaks[i]]
        if 0.05 < interval < 1.0:  # Filter outliers
            intervals.append(interval)

    if len(intervals) < 2:
        return RhythmAnalysis(
            score=5,
            pvi=0,
            is_syllable_timed=False,
            feedback="Could not calculate rhythm. Try speaking longer.",
            pvi_type="ioi",
            pvi_ioi=0,
            timing_class="unknown",
        )

    # Calculate nPVI using shared function
    pvi = calculate_npvi(intervals)

    # Use IOI-specific thresholds (lower than vocalic for the same speech)
    config = RHYTHM_CONFIG
    spanish_typical = config["ioi_spanish_typical"]
    english_target = config["ioi_english_target"]
    english_native = config["ioi_english_native"]

    is_syllable_timed, timing_class = _classify_timing(
        pvi, english_target, config["transitional_margin"]
    )

    # Calculate score
    if pvi >= english_native:
        score = 10
    elif pvi >= english_target:
        score = 7 + int((pvi - english_target) /
                        (english_native - english_target) * 3)
    elif pvi >= spanish_typical:
        score = 4 + int((pvi - spanish_typical) /
                        (english_target - spanish_typical) * 3)
    else:
        score = max(1, int(pvi / spanish_typical * 4))

    score = min(10, max(1, score))

    # Generate feedback. IOI nPVI is an approximation of vocalic nPVI
    # based on syllable-peak timing, so we soften the rhythm-class
    # claims and flag it as estimated.
    if pvi < spanish_typical:
        feedback = f"Low syllable-timing variability (IOI nPVI: {pvi:.0f}, approximate). Compress unstressed syllables more."
    elif pvi < english_target:
        feedback = f"Approaching stress-timed rhythm (IOI nPVI: {pvi:.0f}, approximate). Reduce unstressed syllables."
    elif pvi < english_native:
        feedback = f"Good stress-timing variability (IOI nPVI: {pvi:.0f}, approximate). Keep practicing stress contrast."
    else:
        feedback = f"Strong stress-timing variability (IOI nPVI: {pvi:.0f}, approximate)."

    return RhythmAnalysis(
        score=score,
        pvi=round(pvi, 1),
        is_syllable_timed=is_syllable_timed,
        feedback=feedback,
        pvi_type="ioi",
        pvi_ioi=round(pvi, 1),
        timing_class=timing_class,
    )


def analyze_rhythm(sound: parselmouth.Sound) -> RhythmAnalysis:
    """
    Analyze speech rhythm using normalized Pairwise Variability Index (nPVI).

    Based on Grabe & Low (2002) methodology.
    This is a legacy function that uses IOI-based nPVI approximation.

    For true vocalic nPVI measurement, use analyze_rhythm_with_alignment()
    when transcripts are available.

    Reference values:
    - Syllable-timed languages (Spanish, French): nPVI ~40-50
    - Stress-timed languages (English, German): nPVI ~55-65

    Args:
        sound: Parselmouth Sound object

    Returns:
        RhythmAnalysis with IOI-based nPVI measurement
    """
    return analyze_rhythm_ioi(sound)


def analyze_pauses(sound: parselmouth.Sound) -> PauseAnalysis:
    """Analyze pause patterns in speech."""
    intensity = call(sound, "To Intensity", 75, 0.0, "yes")
    duration = sound.get_total_duration()

    time_step = 0.01
    start_time = call(intensity, "Get start time")
    end_time = call(intensity, "Get end time")

    intensity_values = []
    times = []
    t = start_time
    while t <= end_time:
        value = call(intensity, "Get value at time", t, "cubic")
        if value is not None and not np.isnan(value):
            intensity_values.append(value)
            times.append(t)
        t += time_step

    if len(intensity_values) < 10:
        return PauseAnalysis(
            score=5,
            pause_count=0,
            total_pause_duration=0,
            avg_pause_duration=0,
            pause_ratio=0,
            pauses=[],
            feedback="Audio too short for pause analysis."
        )

    intensity_values = np.array(intensity_values)
    times = np.array(times)

    # Detect pauses (low intensity regions)
    threshold = np.percentile(intensity_values, 25)
    config = PAUSE_CONFIG
    min_pause = config["min_pause_duration"]

    pauses = []
    in_pause = False
    pause_start = 0

    for i, (t, val) in enumerate(zip(times, intensity_values)):
        if val < threshold:
            if not in_pause:
                in_pause = True
                pause_start = t
        else:
            if in_pause:
                pause_duration = t - pause_start
                if pause_duration >= min_pause:
                    pauses.append((pause_start, t))
                in_pause = False

    # Handle pause at end
    if in_pause:
        pause_duration = times[-1] - pause_start
        if pause_duration >= min_pause:
            pauses.append((pause_start, times[-1]))

    pause_count = len(pauses)
    total_pause_duration = sum(p[1] - p[0] for p in pauses)
    avg_pause_duration = total_pause_duration / pause_count if pause_count > 0 else 0
    pause_ratio = total_pause_duration / duration if duration > 0 else 0

    # Calculate score based on pause rate per 30 seconds
    pauses_per_30s = (pause_count / duration) * 30 if duration > 0 else 0

    if pauses_per_30s >= config["excellent_pause_rate"]:
        score = 10
    elif pauses_per_30s >= config["good_pause_rate"]:
        score = 7 + int((pauses_per_30s - config["good_pause_rate"]) /
                        (config["excellent_pause_rate"] - config["good_pause_rate"]) * 3)
    elif pauses_per_30s >= 1:
        score = 3 + int((pauses_per_30s - 1) / (config["good_pause_rate"] - 1) * 4)
    else:
        score = max(1, int(pauses_per_30s * 3))

    # Penalize if pauses are too long
    if avg_pause_duration > config["max_pause_duration"]:
        score = max(1, score - 2)

    score = min(10, max(1, score))

    # Generate feedback
    if pause_count == 0:
        feedback = "No pauses detected. Add strategic pauses before key points."
    elif pauses_per_30s < config["good_pause_rate"]:
        feedback = f"{pause_count} pause(s) detected. Add more pauses for emphasis and breathing."
    elif avg_pause_duration > config["max_pause_duration"]:
        feedback = f"Pauses too long (avg: {avg_pause_duration:.1f}s). Keep pauses 0.5-1.5s."
    elif pauses_per_30s >= config["excellent_pause_rate"]:
        feedback = f"Excellent pause usage: {pause_count} pauses, avg {avg_pause_duration:.1f}s."
    else:
        feedback = f"Good pause pattern: {pause_count} pauses. Consider adding more before important points."

    return PauseAnalysis(
        score=score,
        pause_count=pause_count,
        total_pause_duration=round(total_pause_duration, 2),
        avg_pause_duration=round(avg_pause_duration, 2),
        pause_ratio=round(pause_ratio, 3),
        pauses=pauses,
        feedback=feedback
    )


def analyze_prosody_slice(
    audio_data: np.ndarray,
    sample_rate: int,
    start_s: float,
    end_s: float,
) -> Optional[ProsodyAnalysis]:
    """Run prosody analysis on a slice of audio.

    Returns None if the slice is shorter than MIN_SLOT_SECONDS, or if start/end
    are out of range or inverted. Otherwise calls analyze_prosody() on the
    sliced numpy view.
    """
    from config import MIN_SLOT_SECONDS

    duration = len(audio_data) / sample_rate
    start_s = max(0.0, start_s)
    end_s = min(duration, end_s)
    if end_s - start_s < MIN_SLOT_SECONDS:
        return None

    start_sample = int(round(start_s * sample_rate))
    end_sample = int(round(end_s * sample_rate))
    if end_sample <= start_sample:
        return None

    slice_data = audio_data[start_sample:end_sample]
    try:
        return analyze_prosody(slice_data, sample_rate)
    except Exception as exc:
        logger.warning("analyze_prosody_slice failed (%.2fs-%.2fs): %s", start_s, end_s, exc)
        return None


def analyze_prosody_per_slot(
    audio_data: np.ndarray,
    sample_rate: int,
    slot_spans: dict,
) -> dict:
    """Run prosody analysis on each slot's audio span.

    Args:
        audio_data: full audio
        sample_rate: Hz
        slot_spans: {slot_id: (start_s, end_s) or None}

    Returns:
        {slot_id: ProsodyAnalysis | None} — None for spans that were missing,
        too short, or failed to analyze.
    """
    results: dict = {}
    for slot_id, span in slot_spans.items():
        if span is None:
            results[slot_id] = None
            continue
        start_s, end_s = span
        results[slot_id] = analyze_prosody_slice(audio_data, sample_rate, start_s, end_s)
    return results
