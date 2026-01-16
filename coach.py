"""AI coaching module using Gemini Flash for transcription and feedback."""

import os
import base64
import tempfile
from pathlib import Path
from dataclasses import dataclass
from typing import Optional
import numpy as np
import scipy.io.wavfile as wav

from google import genai
from google.genai import types

from config import GEMINI_API_KEY, GEMINI_MODEL
from analyzer import ProsodyAnalysis


@dataclass
class CoachingResult:
    """Results from AI coaching analysis."""
    transcript: str
    grammar_issues: list[dict]  # [{"original": ..., "corrected": ..., "explanation": ...}]
    suggested_revision: str
    coaching_tips: list[str]
    overall_feedback: str


def get_client() -> genai.Client:
    """Get Gemini client with API key."""
    api_key = os.environ.get("GEMINI_API_KEY") or GEMINI_API_KEY
    if not api_key:
        raise ValueError(
            "GEMINI_API_KEY not set. Either:\n"
            "  1. Set environment variable: export GEMINI_API_KEY=your_key\n"
            "  2. Or update config.py with your key"
        )
    return genai.Client(api_key=api_key)


def audio_to_base64(audio_data: np.ndarray, sample_rate: int) -> str:
    """Convert audio numpy array to base64-encoded WAV."""
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        # Convert to 16-bit PCM
        audio_int16 = (audio_data * 32767).astype(np.int16)
        wav.write(f.name, sample_rate, audio_int16)

        with open(f.name, "rb") as audio_file:
            audio_bytes = audio_file.read()

        # Clean up temp file
        Path(f.name).unlink()

    return base64.b64encode(audio_bytes).decode("utf-8")


def analyze_with_coach(
    audio_data: np.ndarray,
    sample_rate: int,
    prosody: ProsodyAnalysis
) -> CoachingResult:
    """
    Send audio and prosody analysis to Gemini for coaching feedback.

    Args:
        audio_data: Audio samples as numpy array
        sample_rate: Sample rate in Hz
        prosody: Results from prosody analysis

    Returns:
        CoachingResult with transcription, grammar, and coaching tips
    """
    client = get_client()

    # Convert audio to base64
    audio_b64 = audio_to_base64(audio_data, sample_rate)

    # Build the prompt with prosody context
    prompt = build_coaching_prompt(prosody)

    # Create the content with audio
    contents = [
        types.Content(
            role="user",
            parts=[
                types.Part.from_bytes(
                    data=base64.b64decode(audio_b64),
                    mime_type="audio/wav"
                ),
                types.Part.from_text(text=prompt),
            ],
        ),
    ]

    # Configure generation
    generate_config = types.GenerateContentConfig(
        temperature=0.3,  # Lower temperature for more consistent analysis
        max_output_tokens=2048,
    )

    # Call Gemini
    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=contents,
        config=generate_config,
    )

    # Parse the response
    return parse_coaching_response(response.text)


def analyze_with_coach_practice(
    audio_data: np.ndarray,
    sample_rate: int,
    prosody: ProsodyAnalysis,
    expected_text: str
) -> CoachingResult:
    """
    Analyze audio against expected text for practice mode.

    Compares pronunciation and evaluates how well the user read the given text.
    """
    client = get_client()
    audio_b64 = audio_to_base64(audio_data, sample_rate)

    prompt = build_practice_prompt(prosody, expected_text)

    contents = [
        types.Content(
            role="user",
            parts=[
                types.Part.from_bytes(
                    data=base64.b64decode(audio_b64),
                    mime_type="audio/wav"
                ),
                types.Part.from_text(text=prompt),
            ],
        ),
    ]

    generate_config = types.GenerateContentConfig(
        temperature=0.3,
        max_output_tokens=2048,
    )

    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=contents,
        config=generate_config,
    )

    return parse_coaching_response(response.text)


def build_practice_prompt(prosody: ProsodyAnalysis, expected_text: str) -> str:
    """Build prompt for practice mode with expected text comparison."""
    return f"""You are an English speech coach helping a Spanish speaker improve their English communication.

TASK: The user was asked to read the following text aloud. Analyze their reading.

EXPECTED TEXT (what they should have read):
"{expected_text}"

PROSODY ANALYSIS RESULTS (already measured):
- Pitch: {prosody.pitch.score}/10 - {prosody.pitch.feedback}
- Volume: {prosody.volume.score}/10 - {prosody.volume.feedback}
- Tempo: {prosody.tempo.score}/10 - Speed: {prosody.tempo.estimated_wpm:.0f} WPM. {prosody.tempo.feedback}
- Rhythm: {prosody.rhythm.score}/10 - PVI: {prosody.rhythm.pvi:.0f}. {prosody.rhythm.feedback}
- Pauses: {prosody.pauses.score}/10 - {prosody.pauses.feedback}

Please provide your response in this EXACT format:

TRANSCRIPT:
[Write the exact transcription of what the user actually said]

GRAMMAR_ISSUES:
[Compare the transcript to the expected text. List any differences:]
[- Words that were skipped or added]
[- Words that were mispronounced (write: "said X" -> "should be Y" | explanation)]
[- If they read it perfectly, write: None]

SUGGESTED_REVISION:
[If they made mistakes, show the correct text with pronunciation tips]
[If they read it correctly, write: "Excellent! You read the text correctly."]

COACHING_TIPS:
[List 3-5 specific tips based on:]
[1. Pronunciation errors (specific sounds or words that need work)]
[2. The lowest prosody score - how to improve it for THIS specific text]
[3. Word stress patterns in the text they read]
[4. Intonation patterns appropriate for this text]
[5. Where to place pauses in this text]

OVERALL:
[Evaluate their reading: Did they read the correct text? How was their pronunciation? What's the #1 thing to practice?]
"""


def build_coaching_prompt(prosody: ProsodyAnalysis) -> str:
    """Build the coaching prompt with prosody context."""
    return f"""You are an English speech coach helping a Spanish speaker improve their English communication.

TASK: Analyze this audio recording and provide detailed feedback.

PROSODY ANALYSIS RESULTS (already measured):
- Pitch: {prosody.pitch.score}/10 - {prosody.pitch.feedback}
- Volume: {prosody.volume.score}/10 - {prosody.volume.feedback}
- Tempo: {prosody.tempo.score}/10 - Speed: {prosody.tempo.estimated_wpm:.0f} WPM. {prosody.tempo.feedback}
- Rhythm: {prosody.rhythm.score}/10 - PVI: {prosody.rhythm.pvi:.0f}. {prosody.rhythm.feedback}
- Pauses: {prosody.pauses.score}/10 - {prosody.pauses.feedback}

Please provide your response in this EXACT format:

TRANSCRIPT:
[Write the exact transcription of what was said]

GRAMMAR_ISSUES:
[List each grammar issue on a new line in this format: "original text" -> "corrected text" | explanation]
[If no issues, write: None]

SUGGESTED_REVISION:
[Write a polished version of what was said, fixing grammar and making it more natural]

COACHING_TIPS:
[List 3-5 specific, actionable tips based on the prosody scores and the content. Focus on:]
[1. The lowest prosody score area]
[2. Any grammar patterns common for Spanish speakers]
[3. Word choice or phrasing improvements]
[4. Specific moments in the recording that could be improved]

OVERALL:
[One paragraph summary of strengths and the #1 thing to focus on improving]
"""


def parse_coaching_response(response_text: str) -> CoachingResult:
    """Parse Gemini's response into structured CoachingResult."""
    sections = {
        "TRANSCRIPT:": "",
        "GRAMMAR_ISSUES:": "",
        "SUGGESTED_REVISION:": "",
        "COACHING_TIPS:": "",
        "OVERALL:": "",
    }

    current_section = None
    lines = response_text.strip().split("\n")

    for line in lines:
        line_stripped = line.strip()

        # Check if this line starts a new section
        for section_key in sections.keys():
            if line_stripped.startswith(section_key):
                current_section = section_key
                # Get any content on the same line after the section header
                remaining = line_stripped[len(section_key):].strip()
                if remaining:
                    sections[current_section] = remaining + "\n"
                break
        else:
            # Not a section header, add to current section
            if current_section:
                sections[current_section] += line + "\n"

    # Parse grammar issues
    grammar_issues = []
    grammar_text = sections["GRAMMAR_ISSUES:"].strip()
    if grammar_text.lower() != "none" and grammar_text:
        for line in grammar_text.split("\n"):
            line = line.strip()
            if not line or line.startswith("["):
                continue
            if "->" in line:
                try:
                    parts = line.split("->")
                    original = parts[0].strip().strip('"')
                    rest = parts[1]
                    if "|" in rest:
                        corrected, explanation = rest.split("|", 1)
                    else:
                        corrected = rest
                        explanation = ""
                    grammar_issues.append({
                        "original": original,
                        "corrected": corrected.strip().strip('"'),
                        "explanation": explanation.strip()
                    })
                except (ValueError, IndexError):
                    continue

    # Parse coaching tips
    coaching_tips = []
    tips_text = sections["COACHING_TIPS:"].strip()
    for line in tips_text.split("\n"):
        line = line.strip()
        if line and not line.startswith("["):
            # Remove bullet points, numbers, etc.
            if line[0].isdigit() and (line[1] == "." or line[1] == ")"):
                line = line[2:].strip()
            elif line[0] in "-•*":
                line = line[1:].strip()
            if line:
                coaching_tips.append(line)

    return CoachingResult(
        transcript=sections["TRANSCRIPT:"].strip(),
        grammar_issues=grammar_issues,
        suggested_revision=sections["SUGGESTED_REVISION:"].strip(),
        coaching_tips=coaching_tips[:5],  # Limit to 5 tips
        overall_feedback=sections["OVERALL:"].strip(),
    )


def display_coaching(result: CoachingResult, console) -> None:
    """Display coaching results using rich console."""
    from rich.panel import Panel
    from rich.table import Table
    from rich import box

    # Transcript section
    console.print()
    console.print(Panel(
        f"[italic]{result.transcript}[/italic]",
        title="[bold blue]TRANSCRIPT[/bold blue]",
        border_style="blue",
    ))

    # Grammar issues
    if result.grammar_issues:
        console.print()
        console.print("[bold cyan]GRAMMAR ISSUES[/bold cyan]")
        console.print()

        for issue in result.grammar_issues:
            console.print(f"  [red]✗[/red] \"{issue['original']}\"")
            console.print(f"  [green]✓[/green] \"{issue['corrected']}\"")
            if issue['explanation']:
                console.print(f"    [dim]{issue['explanation']}[/dim]")
            console.print()
    else:
        console.print()
        console.print("[green]No grammar issues detected.[/green]")

    # Suggested revision
    if result.suggested_revision:
        console.print()
        console.print(Panel(
            f"[green]{result.suggested_revision}[/green]",
            title="[bold green]SUGGESTED REVISION[/bold green]",
            border_style="green",
        ))

    # Coaching tips
    if result.coaching_tips:
        console.print()
        console.print("[bold yellow]COACHING TIPS[/bold yellow]")
        console.print()
        for i, tip in enumerate(result.coaching_tips, 1):
            console.print(f"  [yellow]{i}.[/yellow] {tip}")

    # Overall feedback
    if result.overall_feedback:
        console.print()
        console.print(Panel(
            result.overall_feedback,
            title="[bold]SUMMARY[/bold]",
            border_style="cyan",
        ))

    console.print()
