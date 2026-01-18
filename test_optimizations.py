#!/usr/bin/env python3
"""Test script to measure audio optimization improvements."""

import time
import sys
from pathlib import Path

import numpy as np

from recorder import load_audio, trim_silence
from config import SAMPLE_RATE


def test_silence_trimming():
    """Test silence trimming on existing recordings."""
    print("=" * 60)
    print("SILENCE TRIMMING TEST")
    print("=" * 60)

    recordings_dir = Path("data/recordings")
    recordings = list(recordings_dir.glob("*.flac"))[:5]  # Test first 5

    if not recordings:
        print("No recordings found in data/recordings/")
        return

    total_original = 0
    total_trimmed = 0

    for rec_path in recordings:
        audio_data, sr = load_audio(rec_path)
        original_duration = len(audio_data) / sr
        original_samples = len(audio_data)

        trimmed = trim_silence(audio_data, sr)
        trimmed_duration = len(trimmed) / sr
        trimmed_samples = len(trimmed)

        reduction = (1 - trimmed_samples / original_samples) * 100

        print(f"\n{rec_path.name}:")
        print(f"  Original: {original_duration:.2f}s ({original_samples:,} samples)")
        print(f"  Trimmed:  {trimmed_duration:.2f}s ({trimmed_samples:,} samples)")
        print(f"  Reduction: {reduction:.1f}%")

        total_original += original_samples
        total_trimmed += trimmed_samples

    if total_original > 0:
        overall_reduction = (1 - total_trimmed / total_original) * 100
        print(f"\n{'='*60}")
        print(f"OVERALL REDUCTION: {overall_reduction:.1f}%")
        print(f"{'='*60}")


def test_file_size():
    """Test file size difference with trimming."""
    import tempfile
    import soundfile as sf

    print("\n" + "=" * 60)
    print("FILE SIZE TEST")
    print("=" * 60)

    recordings_dir = Path("data/recordings")
    recordings = list(recordings_dir.glob("*.flac"))[:3]

    if not recordings:
        print("No recordings found")
        return

    for rec_path in recordings:
        audio_data, sr = load_audio(rec_path)
        trimmed = trim_silence(audio_data, sr)

        # Save both to temp files and compare
        with tempfile.NamedTemporaryFile(suffix=".flac", delete=False) as f:
            original_path = f.name
            sf.write(original_path, audio_data, sr, format='flac')

        with tempfile.NamedTemporaryFile(suffix=".flac", delete=False) as f:
            trimmed_path = f.name
            sf.write(trimmed_path, trimmed, sr, format='flac')

        original_size = Path(original_path).stat().st_size
        trimmed_size = Path(trimmed_path).stat().st_size
        reduction = (1 - trimmed_size / original_size) * 100

        print(f"\n{rec_path.name}:")
        print(f"  Original: {original_size:,} bytes ({original_size/1024:.1f} KB)")
        print(f"  Trimmed:  {trimmed_size:,} bytes ({trimmed_size/1024:.1f} KB)")
        print(f"  Size reduction: {reduction:.1f}%")

        # Cleanup
        Path(original_path).unlink()
        Path(trimmed_path).unlink()


def test_api_speed():
    """Test API call speed with and without optimizations."""
    import os
    if not os.environ.get("GEMINI_API_KEY"):
        print("\n" + "=" * 60)
        print("API SPEED TEST - SKIPPED (no GEMINI_API_KEY)")
        print("=" * 60)
        return

    print("\n" + "=" * 60)
    print("API SPEED TEST")
    print("=" * 60)

    from analyzer import analyze_prosody
    from coach import analyze_with_coach, analyze_parallel

    recordings_dir = Path("data/recordings")
    recordings = list(recordings_dir.glob("*.flac"))[:1]  # Test 1 recording

    if not recordings:
        print("No recordings found")
        return

    rec_path = recordings[0]
    audio_data, sr = load_audio(rec_path)

    print(f"\nTesting with: {rec_path.name}")
    print(f"Duration: {len(audio_data)/sr:.2f}s")

    # Test SEQUENTIAL (old way): prosody first, then Gemini
    print("\n--- SEQUENTIAL: Prosody then Gemini ---")
    start = time.time()
    prosody = analyze_prosody(audio_data, sr)
    prosody_time = time.time() - start
    print(f"Prosody analysis: {prosody_time:.2f}s")

    gemini_start = time.time()
    result1 = analyze_with_coach(audio_data, sr, prosody)
    gemini_time = time.time() - gemini_start
    sequential_total = time.time() - start

    print(f"Gemini API call:  {gemini_time:.2f}s")
    print(f"TOTAL:            {sequential_total:.2f}s")
    print(f"Transcript: {result1.transcript[:60]}...")

    # Test PARALLEL (new way): prosody and Gemini at the same time
    print("\n--- PARALLEL: Prosody + Gemini simultaneously ---")
    first_chunk_time = None
    chunk_count = 0

    def on_chunk(chunk, accumulated):
        nonlocal first_chunk_time, chunk_count
        chunk_count += 1
        if first_chunk_time is None:
            first_chunk_time = time.time() - start

    start = time.time()
    prosody2, result2 = analyze_parallel(audio_data, sr, on_chunk)
    parallel_total = time.time() - start

    print(f"Time to first chunk: {first_chunk_time:.2f}s")
    print(f"TOTAL:               {parallel_total:.2f}s")
    print(f"Chunks received:     {chunk_count}")
    print(f"Transcript: {result2.transcript[:60]}...")

    # Show both prosody results for comparison
    print("\n--- PROSODY COMPARISON (Local vs AI) ---")
    print(f"{'Metric':<12} {'Local':<10} {'AI':<10}")
    print("-" * 32)

    ai_prosody = result2.ai_prosody or {}
    print(f"{'Pitch':<12} {prosody2.pitch.score:<10} {ai_prosody.get('pitch', {}).get('score', 'N/A'):<10}")
    print(f"{'Volume':<12} {prosody2.volume.score:<10} {ai_prosody.get('volume', {}).get('score', 'N/A'):<10}")
    print(f"{'Tempo':<12} {prosody2.tempo.score:<10} {ai_prosody.get('tempo', {}).get('score', 'N/A'):<10}")
    print(f"{'Rhythm':<12} {prosody2.rhythm.score:<10} {ai_prosody.get('rhythm', {}).get('score', 'N/A'):<10}")
    print(f"{'Pauses':<12} {prosody2.pauses.score:<10} {ai_prosody.get('pauses', {}).get('score', 'N/A'):<10}")

    # Summary
    print("\n--- SUMMARY ---")
    print(f"Sequential total: {sequential_total:.2f}s")
    print(f"Parallel total:   {parallel_total:.2f}s")
    improvement = (sequential_total - parallel_total) / sequential_total * 100
    print(f"Improvement:      {improvement:.1f}% faster")
    print(f"Time to first response: {first_chunk_time:.2f}s (with streaming)")


def main():
    """Run all tests."""
    print("\nPROSODY AUDIO OPTIMIZATION TESTS")
    print("=" * 60)

    test_silence_trimming()
    test_file_size()
    test_api_speed()

    print("\n" + "=" * 60)
    print("TESTS COMPLETE")
    print("=" * 60)


if __name__ == "__main__":
    main()
