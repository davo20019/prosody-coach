"""AI coaching module using Gemini Flash for transcription and feedback."""

import os
import re
import base64
import tempfile
from pathlib import Path
from dataclasses import dataclass
from typing import Optional
import numpy as np
import soundfile as sf

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
    confidence_score: int = 0  # 1-10 scale of how confident the speaker sounds
    confidence_feedback: str = ""  # Explanation of confidence assessment
    filler_word_count: int = 0  # Count of um, uh, like, you know, etc.
    filler_words_detail: str = ""  # Details about filler words used
    pronunciation_issues: list[dict] = None  # [{"sound": "th", "example": "think", "ipa": "/θ/", "tip": "..."}]
    fluency_score: int = 0  # 1-10 scale for smoothness/flow
    fluency_feedback: str = ""  # Explanation of fluency assessment
    # AI-perceived prosody analysis (from listening to audio)
    ai_prosody: dict = None  # {"pitch": {"score": 7, "feedback": "..."}, "rhythm": {...}, ...}


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


def extract_text_from_response(response) -> str:
    """Extract text content from Gemini response, filtering out thinking parts."""
    # Manually extract text from parts to avoid SDK warning about thought_signature
    text_parts = []
    try:
        if hasattr(response, 'candidates') and response.candidates:
            for part in response.candidates[0].content.parts:
                if hasattr(part, 'text') and part.text:
                    text_parts.append(part.text)
        if text_parts:
            return "".join(text_parts)
    except Exception:
        pass

    # Fallback: suppress stdout/stderr and use .text
    import sys
    import io
    old_stdout, old_stderr = sys.stdout, sys.stderr
    sys.stdout = sys.stderr = io.StringIO()
    try:
        if hasattr(response, 'text'):
            return response.text
        return ""
    finally:
        sys.stdout, sys.stderr = old_stdout, old_stderr


def audio_to_base64(audio_data: np.ndarray, sample_rate: int) -> str:
    """Convert audio numpy array to base64-encoded FLAC (compressed, lossless)."""
    with tempfile.NamedTemporaryFile(suffix=".flac", delete=False) as f:
        temp_path = f.name
        # Save as FLAC (50-60% smaller than WAV, lossless quality)
        sf.write(temp_path, audio_data, sample_rate, format='flac')

        with open(temp_path, "rb") as audio_file:
            audio_bytes = audio_file.read()

        # Clean up temp file
        Path(temp_path).unlink()

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
                    mime_type="audio/flac"
                ),
                types.Part.from_text(text=prompt),
            ],
        ),
    ]

    # Configure generation
    generate_config = types.GenerateContentConfig(
        temperature=0.3,  # Lower temperature for more consistent analysis
        max_output_tokens=4096,
    )

    # Call Gemini
    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=contents,
        config=generate_config,
    )

    # Parse the response
    return parse_coaching_response(extract_text_from_response(response))


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
                    mime_type="audio/flac"
                ),
                types.Part.from_text(text=prompt),
            ],
        ),
    ]

    generate_config = types.GenerateContentConfig(
        temperature=0.3,
        max_output_tokens=4096,
    )

    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=contents,
        config=generate_config,
    )

    return parse_coaching_response(extract_text_from_response(response))


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
[- Words that were mispronounced - format: "said X" -> "should be Y" /IPA/ | explanation]
[- Include IPA pronunciation in slashes for mispronounced words, e.g., "thought" /θɔːt/]
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

VOCAL_CONFIDENCE:
[Rate how confident the speaker sounds from 1-10, where:]
[1-3 = Nervous/hesitant (shaky voice, many fillers, trailing off)]
[4-6 = Somewhat confident (occasional hesitation, some uncertainty)]
[7-9 = Confident (steady voice, good projection, deliberate)]
[10 = Very confident (commanding, assured, natural authority)]
[Format: SCORE | explanation of what specific vocal qualities led to this score]
[Consider: voice steadiness, filler words (um, uh, like), upspeak, volume projection, hesitations, pace control]

FILLER_WORDS:
[Count filler words/hesitation markers: um, uh, er, like, you know, so, basically, I mean, kind of, sort of]
[Format: COUNT | list each filler word heard with its count, e.g., "um (3), like (2)"]
[If no filler words, write: 0 | None detected]

PRONUNCIATION_ISSUES:
[List specific sounds that need work, especially common issues for Spanish speakers:]
[Format each as: SOUND | example word /IPA/ | tip for improvement]
[Common issues: th /θ/, v vs b, short vs long vowels, word-final consonants, consonant clusters]
[If pronunciation is clear, write: None - pronunciation was clear]

FLUENCY:
[Rate speaking fluency from 1-10, where:]
[1-3 = Choppy (frequent stops, restarts, long pauses mid-sentence)]
[4-6 = Moderate (some hesitations, occasional restarts)]
[7-9 = Fluent (smooth flow, natural rhythm, minimal hesitation)]
[10 = Native-like fluency (effortless, natural speech flow)]
[Format: SCORE | explanation of fluency assessment]

AI_PROSODY:
[Analyze the audio directly and provide YOUR perception of these prosody elements (independent of the algorithmic scores above):]
[Format each line as: CATEGORY: SCORE/10 | your observation]
- PITCH: [Score 1-10] | [Is there enough pitch variation? Does intonation sound natural for English? Rising/falling patterns?]
- VOLUME: [Score 1-10] | [Is volume appropriate? Good stress contrast between emphasized and unstressed syllables?]
- TEMPO: [Score 1-10] | [Is the pace natural? Too fast/slow? Good variation for emphasis?]
- RHYTHM: [Score 1-10] | [Does it have English stress-timed rhythm? Or syllable-timed like Spanish? Word stress correct?]
- PAUSES: [Score 1-10] | [Are pauses placed naturally at phrase boundaries? Too many/few pauses?]
- NATURALNESS: [Score 1-10] | [Overall, how natural does this sound to a native English ear?]
[Add a brief note if your perception differs significantly from the algorithmic scores above]

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
[List each grammar or pronunciation issue on a new line in this format:]
["original text" -> "corrected text" /IPA/ | explanation]
[Include IPA pronunciation in slashes for mispronounced words, e.g., "think" /θɪŋk/]
[If no issues, write: None]

SUGGESTED_REVISION:
[Write a polished version of what was said, fixing grammar and making it more natural]

COACHING_TIPS:
[List 3-5 specific, actionable tips based on the prosody scores and the content. Focus on:]
[1. The lowest prosody score area]
[2. Any grammar patterns common for Spanish speakers]
[3. Word choice or phrasing improvements]
[4. Specific moments in the recording that could be improved]

VOCAL_CONFIDENCE:
[Rate how confident the speaker sounds from 1-10, where:]
[1-3 = Nervous/hesitant (shaky voice, many fillers, trailing off)]
[4-6 = Somewhat confident (occasional hesitation, some uncertainty)]
[7-9 = Confident (steady voice, good projection, deliberate)]
[10 = Very confident (commanding, assured, natural authority)]
[Format: SCORE | explanation of what specific vocal qualities led to this score]
[Consider: voice steadiness, filler words (um, uh, like), upspeak, volume projection, hesitations, pace control]

FILLER_WORDS:
[Count filler words/hesitation markers: um, uh, er, like, you know, so, basically, I mean, kind of, sort of]
[Format: COUNT | list each filler word heard with its count, e.g., "um (3), like (2)"]
[If no filler words, write: 0 | None detected]

PRONUNCIATION_ISSUES:
[List specific sounds that need work, especially common issues for Spanish speakers:]
[Format each as: SOUND | example word /IPA/ | tip for improvement]
[Common issues: th /θ/, v vs b, short vs long vowels, word-final consonants, consonant clusters]
[If pronunciation is clear, write: None - pronunciation was clear]

FLUENCY:
[Rate speaking fluency from 1-10, where:]
[1-3 = Choppy (frequent stops, restarts, long pauses mid-sentence)]
[4-6 = Moderate (some hesitations, occasional restarts)]
[7-9 = Fluent (smooth flow, natural rhythm, minimal hesitation)]
[10 = Native-like fluency (effortless, natural speech flow)]
[Format: SCORE | explanation of fluency assessment]

AI_PROSODY:
[Analyze the audio directly and provide YOUR perception of these prosody elements (independent of the algorithmic scores above):]
[Format each line as: CATEGORY: SCORE/10 | your observation]
- PITCH: [Score 1-10] | [Is there enough pitch variation? Does intonation sound natural for English? Rising/falling patterns?]
- VOLUME: [Score 1-10] | [Is volume appropriate? Good stress contrast between emphasized and unstressed syllables?]
- TEMPO: [Score 1-10] | [Is the pace natural? Too fast/slow? Good variation for emphasis?]
- RHYTHM: [Score 1-10] | [Does it have English stress-timed rhythm? Or syllable-timed like Spanish? Word stress correct?]
- PAUSES: [Score 1-10] | [Are pauses placed naturally at phrase boundaries? Too many/few pauses?]
- NATURALNESS: [Score 1-10] | [Overall, how natural does this sound to a native English ear?]
[Add a brief note if your perception differs significantly from the algorithmic scores above]

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
        "VOCAL_CONFIDENCE:": "",
        "FILLER_WORDS:": "",
        "PRONUNCIATION_ISSUES:": "",
        "FLUENCY:": "",
        "AI_PROSODY:": "",
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

    # Parse confidence score
    confidence_score = 0
    confidence_feedback = ""
    confidence_text = sections["VOCAL_CONFIDENCE:"].strip()
    if confidence_text:
        # Format expected: "SCORE | explanation" or just text with a number
        if "|" in confidence_text:
            parts = confidence_text.split("|", 1)
            try:
                confidence_score = int(parts[0].strip())
                confidence_feedback = parts[1].strip()
            except ValueError:
                # Try to extract number from the first part
                numbers = re.findall(r'\d+', parts[0])
                if numbers:
                    confidence_score = min(10, max(1, int(numbers[0])))
                confidence_feedback = parts[1].strip() if len(parts) > 1 else ""
        else:
            # Try to extract score from text
            numbers = re.findall(r'\b(\d+)\b', confidence_text)
            if numbers:
                confidence_score = min(10, max(1, int(numbers[0])))
            confidence_feedback = confidence_text

    # Parse filler words
    filler_word_count = 0
    filler_words_detail = ""
    filler_text = sections["FILLER_WORDS:"].strip()
    if filler_text:
        if "|" in filler_text:
            parts = filler_text.split("|", 1)
            try:
                filler_word_count = int(parts[0].strip())
            except ValueError:
                numbers = re.findall(r'\d+', parts[0])
                if numbers:
                    filler_word_count = int(numbers[0])
            filler_words_detail = parts[1].strip() if len(parts) > 1 else ""
        else:
            numbers = re.findall(r'\b(\d+)\b', filler_text)
            if numbers:
                filler_word_count = int(numbers[0])
            filler_words_detail = filler_text

    # Parse pronunciation issues
    pronunciation_issues = []
    pron_text = sections["PRONUNCIATION_ISSUES:"].strip()
    if pron_text and pron_text.lower() not in ["none", "none - pronunciation was clear"]:
        for line in pron_text.split("\n"):
            line = line.strip()
            if not line or line.startswith("[") or line.lower().startswith("none"):
                continue
            if "|" in line:
                parts = line.split("|")
                if len(parts) >= 2:
                    sound = parts[0].strip()
                    example = parts[1].strip() if len(parts) > 1 else ""
                    tip = parts[2].strip() if len(parts) > 2 else ""
                    # Extract IPA from example if present
                    ipa = ""
                    ipa_match = re.search(r'/([^/]+)/', example)
                    if ipa_match:
                        ipa = ipa_match.group(1)
                    pronunciation_issues.append({
                        "sound": sound,
                        "example": example,
                        "ipa": ipa,
                        "tip": tip
                    })

    # Parse fluency score
    fluency_score = 0
    fluency_feedback = ""
    fluency_text = sections["FLUENCY:"].strip()
    if fluency_text:
        if "|" in fluency_text:
            parts = fluency_text.split("|", 1)
            try:
                fluency_score = int(parts[0].strip())
            except ValueError:
                numbers = re.findall(r'\d+', parts[0])
                if numbers:
                    fluency_score = min(10, max(1, int(numbers[0])))
            fluency_feedback = parts[1].strip() if len(parts) > 1 else ""
        else:
            numbers = re.findall(r'\b(\d+)\b', fluency_text)
            if numbers:
                fluency_score = min(10, max(1, int(numbers[0])))
            fluency_feedback = fluency_text

    # Parse AI prosody analysis
    ai_prosody = {}
    ai_prosody_text = sections["AI_PROSODY:"].strip()
    if ai_prosody_text:
        prosody_categories = ["PITCH", "VOLUME", "TEMPO", "RHYTHM", "PAUSES", "NATURALNESS"]
        for line in ai_prosody_text.split("\n"):
            line = line.strip()
            if not line or line.startswith("["):
                continue
            # Remove leading dash/bullet
            if line.startswith("-"):
                line = line[1:].strip()
            # Check for each category
            for category in prosody_categories:
                if line.upper().startswith(category):
                    # Format: "CATEGORY: SCORE | feedback" or "CATEGORY: SCORE/10 | feedback"
                    rest = line[len(category):].strip()
                    if rest.startswith(":"):
                        rest = rest[1:].strip()
                    score = 0
                    feedback = rest
                    if "|" in rest:
                        score_part, feedback = rest.split("|", 1)
                        feedback = feedback.strip()
                        # Extract number from score part
                        numbers = re.findall(r'\d+', score_part)
                        if numbers:
                            score = min(10, max(1, int(numbers[0])))
                    else:
                        numbers = re.findall(r'\b(\d+)\b', rest)
                        if numbers:
                            score = min(10, max(1, int(numbers[0])))
                    ai_prosody[category.lower()] = {
                        "score": score,
                        "feedback": feedback
                    }
                    break

    return CoachingResult(
        transcript=sections["TRANSCRIPT:"].strip(),
        grammar_issues=grammar_issues,
        suggested_revision=sections["SUGGESTED_REVISION:"].strip(),
        coaching_tips=coaching_tips[:5],  # Limit to 5 tips
        overall_feedback=sections["OVERALL:"].strip(),
        confidence_score=confidence_score,
        confidence_feedback=confidence_feedback,
        filler_word_count=filler_word_count,
        filler_words_detail=filler_words_detail,
        pronunciation_issues=pronunciation_issues,
        fluency_score=fluency_score,
        fluency_feedback=fluency_feedback,
        ai_prosody=ai_prosody if ai_prosody else None,
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

    # Vocal confidence
    if result.confidence_score > 0:
        console.print()
        # Color based on score
        if result.confidence_score >= 7:
            color = "green"
            label = "Confident"
        elif result.confidence_score >= 4:
            color = "yellow"
            label = "Moderate"
        else:
            color = "red"
            label = "Needs Work"

        console.print(Panel(
            f"[bold {color}]{result.confidence_score}/10[/bold {color}] - {label}\n\n{result.confidence_feedback}",
            title="[bold magenta]VOCAL CONFIDENCE[/bold magenta]",
            border_style="magenta",
        ))

    # Fluency score
    if result.fluency_score > 0:
        console.print()
        if result.fluency_score >= 7:
            color = "green"
            label = "Fluent"
        elif result.fluency_score >= 4:
            color = "yellow"
            label = "Moderate"
        else:
            color = "red"
            label = "Choppy"

        console.print(Panel(
            f"[bold {color}]{result.fluency_score}/10[/bold {color}] - {label}\n\n{result.fluency_feedback}",
            title="[bold blue]FLUENCY[/bold blue]",
            border_style="blue",
        ))

    # Filler words
    if result.filler_word_count > 0:
        console.print()
        if result.filler_word_count <= 2:
            color = "green"
        elif result.filler_word_count <= 5:
            color = "yellow"
        else:
            color = "red"

        console.print(Panel(
            f"[bold {color}]{result.filler_word_count} filler words[/bold {color}]\n\n{result.filler_words_detail}",
            title="[bold]FILLER WORDS[/bold]",
            border_style="dim",
        ))

    # Pronunciation issues
    if result.pronunciation_issues:
        console.print()
        console.print("[bold red]PRONUNCIATION ISSUES[/bold red]")
        console.print()
        for issue in result.pronunciation_issues:
            sound = issue.get("sound", "")
            example = issue.get("example", "")
            ipa = issue.get("ipa", "")
            tip = issue.get("tip", "")
            ipa_display = f" /{ipa}/" if ipa else ""
            console.print(f"  [red]•[/red] [bold]{sound}[/bold]: {example}{ipa_display}")
            if tip:
                console.print(f"    [dim]{tip}[/dim]")

    # AI Prosody Analysis (perceived from audio)
    if result.ai_prosody:
        console.print()
        table = Table(
            title="[bold cyan]AI PROSODY ANALYSIS[/bold cyan] [dim](perceived from audio)[/dim]",
            box=box.ROUNDED,
            show_header=True,
            header_style="bold",
        )
        table.add_column("Aspect", style="cyan", width=12)
        table.add_column("Score", justify="center", width=8)
        table.add_column("AI Observation", style="dim")

        # Order for display
        display_order = ["pitch", "volume", "tempo", "rhythm", "pauses", "naturalness"]
        for category in display_order:
            if category in result.ai_prosody:
                data = result.ai_prosody[category]
                score = data.get("score", 0)
                feedback = data.get("feedback", "")
                # Color based on score
                if score >= 7:
                    score_display = f"[green]{score}/10[/green]"
                elif score >= 5:
                    score_display = f"[yellow]{score}/10[/yellow]"
                else:
                    score_display = f"[red]{score}/10[/red]"
                # Capitalize category name
                cat_display = category.capitalize()
                if category == "naturalness":
                    cat_display = "[bold]Naturalness[/bold]"
                table.add_row(cat_display, score_display, feedback)

        console.print(table)

    # Overall feedback
    if result.overall_feedback:
        console.print()
        console.print(Panel(
            result.overall_feedback,
            title="[bold]SUMMARY[/bold]",
            border_style="cyan",
        ))

    console.print()


def generate_tailored_prompt(weaknesses: dict, due_sounds: list[dict] = None) -> dict:
    """
    Generate a tailored practice prompt based on user's weaknesses.

    Args:
        weaknesses: Dictionary from get_user_weaknesses()
        due_sounds: Optional list of sounds due for spaced repetition review

    Returns:
        Dictionary with 'text', 'focus_areas', 'difficulty', and 'target_sounds'
    """
    client = get_client()

    focus_areas = weaknesses.get("focus_areas", [])
    difficulty = weaknesses.get("difficulty", "intermediate")
    recurring_sounds = weaknesses.get("recurring_sounds", [])

    # Build focus description for the prompt
    focus_descriptions = []

    # Prosody focuses
    prosody_focuses = [f["area"] for f in focus_areas if f["type"] == "prosody"]
    if prosody_focuses:
        focus_descriptions.append(f"Prosody: {', '.join(prosody_focuses)}")

    # Priority 1: Due sounds from spaced repetition (these need immediate practice)
    target_sounds = []
    if due_sounds:
        for s in due_sounds[:3]:  # Top 3 due sounds
            sound = s.get("sound", "")
            ipa = s.get("ipa", "")
            if sound:
                target_sounds.append({"sound": sound, "ipa": ipa})
        due_sound_names = [s["sound"] for s in target_sounds]
        focus_descriptions.insert(0, f"PRIORITY - Due for review: {', '.join(due_sound_names)}")

    # Priority 2: Pronunciation focuses from weaknesses analysis
    pron_sounds = [f["sound"] for f in focus_areas if f["type"] == "pronunciation"]
    if not pron_sounds and recurring_sounds:
        pron_sounds = [s[0] for s in recurring_sounds[:3]]

    # Add pron_sounds that aren't already in target_sounds
    existing_sounds = {s["sound"] for s in target_sounds}
    for sound in pron_sounds:
        if sound not in existing_sounds:
            target_sounds.append({"sound": sound, "ipa": ""})

    if pron_sounds:
        focus_descriptions.append(f"Sounds: {', '.join(pron_sounds)}")

    # Other focuses
    if any(f["type"] == "confidence" for f in focus_areas):
        focus_descriptions.append("Build confidence (strong, declarative sentences)")
    if any(f["type"] == "fluency" for f in focus_areas):
        focus_descriptions.append("Improve fluency (flowing, connected speech)")
    if any(f["type"] == "filler_words" for f in focus_areas):
        focus_descriptions.append("Reduce fillers (clear, direct statements)")

    focus_text = "\n".join(f"- {d}" for d in focus_descriptions) if focus_descriptions else "- General practice"

    prompt = f"""You are an English pronunciation coach creating practice material for a Spanish speaker.

TASK: Generate a short practice text (2-3 sentences) tailored to their specific needs.

DIFFICULTY LEVEL: {difficulty}
- beginner: Simple words, common vocabulary, short sentences
- intermediate: More complex vocabulary, compound sentences
- advanced: Challenging words, complex structures, natural idioms

FOCUS AREAS (prioritize these in your text):
{focus_text}

REQUIREMENTS:
1. Text should be natural and meaningful (not tongue twisters)
2. Include multiple instances of target sounds if pronunciation is a focus
3. If rhythm/pauses are a focus, include natural pause points (commas, periods)
4. If confidence is a focus, use declarative statements (not questions)
5. Keep it practical - something someone might actually say

YOU MUST RESPOND IN THIS EXACT FORMAT (both sections required):

TEXT:
The practice sentences go here. Two to three complete sentences.

KEY_SOUNDS:
word1 /IPA1/, word2 /IPA2/, word3 /IPA3/

EXAMPLE RESPONSE:
TEXT:
I think the weather will be rather warm throughout the week. Three of my brothers are gathering for a birthday celebration.

KEY_SOUNDS:
think /θɪŋk/, weather /ˈweðər/, rather /ˈræðər/, throughout /θruːˈaʊt/, three /θriː/, brothers /ˈbrʌðərz/
"""

    contents = [
        types.Content(
            role="user",
            parts=[types.Part.from_text(text=prompt)],
        ),
    ]

    generate_config = types.GenerateContentConfig(
        temperature=0.7,  # Higher for more variety
        max_output_tokens=2048,  # Enough for text + key sounds with IPA
    )

    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=contents,
        config=generate_config,
    )

    response_text = extract_text_from_response(response).strip()

    # Parse the response to extract TEXT and KEY_SOUNDS
    text = ""
    key_sounds = ""

    # Try to parse structured response - case insensitive search
    lines = response_text.split("\n")
    in_text_section = False
    in_key_section = False
    text_lines = []
    key_lines = []

    for line in lines:
        line_stripped = line.strip()
        line_upper = line_stripped.upper()

        # Check for section headers
        if line_upper.startswith("TEXT:"):
            in_text_section = True
            in_key_section = False
            # Get content after "TEXT:" on same line
            content = line_stripped[5:].strip()
            if content:
                text_lines.append(content)
        elif line_upper.startswith("KEY_SOUNDS:") or line_upper.startswith("KEY SOUNDS:"):
            in_key_section = True
            in_text_section = False
            # Get content after header on same line
            header_len = 11 if "KEY_SOUNDS:" in line_upper else 10
            content = line_stripped[header_len:].strip()
            if content:
                key_lines.append(content)
        elif in_text_section and line_stripped:
            # Skip placeholder lines like [Your text here]
            if not line_stripped.startswith("["):
                text_lines.append(line_stripped)
        elif in_key_section and line_stripped:
            # Skip placeholder lines
            if not line_stripped.startswith("[") and "/" in line_stripped:
                key_lines.append(line_stripped)

    # Combine extracted content
    if text_lines:
        text = " ".join(text_lines)
    else:
        # Fallback: look for sentences in the response
        text = response_text.strip('"\'')

    if key_lines:
        key_sounds = ", ".join(key_lines)

    # Clean up text - remove any remaining section headers
    for header in ["TEXT:", "text:", "Text:", "KEY_SOUNDS:", "KEY SOUNDS:", "key_sounds:", "key sounds:"]:
        text = text.replace(header, "").strip()

    # Validate text ends with proper punctuation (not cut off mid-sentence)
    if text and text[-1] not in ".!?":
        # Text was likely truncated - try to find the last complete sentence
        last_period = max(text.rfind("."), text.rfind("!"), text.rfind("?"))
        if last_period > len(text) // 2:  # Only trim if we have at least half the content
            text = text[:last_period + 1]

    return {
        "text": text,
        "key_sounds": key_sounds,
        "focus_areas": [f["description"] for f in focus_areas],
        "difficulty": difficulty,
        "id": f"tailored_{difficulty}",
        "target_sounds": target_sounds,  # For spaced repetition tracking
    }
