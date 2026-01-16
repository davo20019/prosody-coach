#!/usr/bin/env python3
"""Prosody Coach CLI - Improve your English pronunciation and speaking patterns."""

import typer
from rich.console import Console
from rich.panel import Panel
from pathlib import Path
from typing import Optional

from recorder import record_audio, save_recording, load_audio, get_duration, play_audio
from analyzer import analyze_prosody
from feedback import display_analysis, display_quick_feedback
from coach import analyze_with_coach, display_coaching
from prompts import (
    get_prompt_by_id,
    get_prompts_by_category,
    get_all_categories,
    get_random_prompt,
    list_all_prompts,
)

app = typer.Typer(
    name="prosody",
    help="Analyze and improve your English prosody (pitch, volume, tempo, rhythm, pauses).",
    add_completion=False,
)
console = Console()


@app.command()
def analyze(
    file: Optional[Path] = typer.Option(
        None,
        "--file", "-f",
        help="Analyze an existing audio file instead of recording.",
        exists=True,
    ),
    save: bool = typer.Option(
        False,
        "--save", "-s",
        help="Save the recording for later reference.",
    ),
    quick: bool = typer.Option(
        False,
        "--quick", "-q",
        help="Show quick summary instead of detailed analysis.",
    ),
    coach: bool = typer.Option(
        False,
        "--coach", "-c",
        help="Enable AI coaching (transcription, grammar, tips) via Gemini.",
    ),
    playback: bool = typer.Option(
        False,
        "--playback", "-p",
        help="Play back your recording after analysis.",
    ),
):
    """
    Record and analyze your speech prosody.

    Records from your microphone (press Enter to stop), then analyzes
    the 5 components of prosody: pitch, volume, tempo, rhythm, and pauses.

    Use --coach to enable AI-powered transcription, grammar correction,
    and personalized coaching tips.
    """
    try:
        if file:
            # Analyze existing file
            console.print(f"\n[bold blue]Loading:[/bold blue] {file}")
            audio_data, sample_rate = load_audio(file)
            duration = get_duration(audio_data, sample_rate)
            console.print(f"[dim]Duration: {duration:.1f} seconds[/dim]\n")
        else:
            # Record new audio
            console.print()
            console.print(
                Panel(
                    "[bold]Press Enter to stop recording[/bold]",
                    title="[bold blue]Recording[/bold blue]",
                    border_style="blue",
                )
            )
            console.print("[dim]Recording...[/dim]", end=" ")

            audio_data, sample_rate = record_audio()
            duration = get_duration(audio_data, sample_rate)

            console.print(f"[green]Done![/green] ({duration:.1f} seconds)\n")

            if duration < 1.0:
                console.print("[red]Recording too short. Please speak for at least 2 seconds.[/red]")
                raise typer.Exit(1)

            if save:
                filepath = save_recording(audio_data, sample_rate)
                console.print(f"[dim]Saved to: {filepath}[/dim]\n")

        # Analyze prosody
        console.print("[dim]Analyzing prosody...[/dim]")
        analysis = analyze_prosody(audio_data, sample_rate)

        # Display results
        if quick:
            display_quick_feedback(analysis)
        else:
            display_analysis(analysis)

        # AI coaching if enabled
        if coach:
            console.print("[dim]Getting AI coaching feedback...[/dim]")
            try:
                coaching = analyze_with_coach(audio_data, sample_rate, analysis)
                display_coaching(coaching, console)
            except Exception as e:
                console.print(f"[yellow]AI coaching unavailable: {e}[/yellow]")

        # Playback if requested
        if playback:
            console.print("[dim]Playing back your recording...[/dim]")
            play_audio(audio_data, sample_rate)
            console.print("[green]Playback complete.[/green]\n")

    except KeyboardInterrupt:
        console.print("\n[yellow]Recording cancelled.[/yellow]")
        raise typer.Exit(0)
    except Exception as e:
        console.print(f"\n[red]Error: {e}[/red]")
        raise typer.Exit(1)


@app.command()
def info():
    """
    Display information about the prosody components analyzed.
    """
    console.print()
    console.print(Panel("[bold]The 5 Components of Prosody[/bold]", border_style="blue"))

    info_text = """
[bold cyan]1. Pitch[/bold cyan] (Intonation)
   The highness or lowness of your voice. English uses wide pitch
   variation to convey meaning and emotion.
   [dim]Target: 100-150 Hz variation range[/dim]

[bold cyan]2. Volume[/bold cyan] (Stress)
   Loudness variation between stressed and unstressed syllables.
   English emphasizes important words by making them louder.
   [dim]Target: 6-10 dB contrast between stressed/unstressed[/dim]

[bold cyan]3. Tempo[/bold cyan] (Speed)
   Speaking rate and its variation. Good speakers vary speed for emphasis.
   [dim]Target: 130-160 WPM with 15-25% variation[/dim]

[bold cyan]4. Rhythm[/bold cyan] (Timing Pattern)
   The timing between syllables. Spanish is syllable-timed (equal length),
   English is stress-timed (stressed syllables longer).
   [dim]Target: PVI of 55-65 (higher = more English-like)[/dim]

[bold cyan]5. Pauses[/bold cyan] (Strategic Silence)
   Deliberate breaks in speech for emphasis and breathing.
   [dim]Target: 3-5 pauses per 30 seconds, 0.5-1.5s each[/dim]
"""
    console.print(info_text)


@app.command()
def tips():
    """
    Show tips for improving prosody as a Spanish speaker.
    """
    console.print()
    console.print(Panel("[bold]Tips for Spanish Speakers[/bold]", border_style="green"))

    tips_text = """
[bold yellow]Common Patterns to Avoid:[/bold yellow]

[bold]1. Monotone Speech[/bold]
   Spanish speakers often use flatter pitch in English.
   [green]Fix:[/green] Exaggerate pitch changes at first. Go higher on
   stressed words, lower at sentence ends.

[bold]2. Equal Syllable Length[/bold]
   Spanish gives equal time to each syllable. English doesn't.
   [green]Fix:[/green] Stretch stressed syllables, rush through unstressed ones.
   "COMfortable" not "com-for-ta-ble"

[bold]3. Missing Reductions[/bold]
   Unstressed vowels in English become "schwa" (uh).
   [green]Fix:[/green] "to" -> "tuh", "for" -> "fer", "can" -> "cun"

[bold]4. No Strategic Pauses[/bold]
   Spanish speakers often speak in continuous streams.
   [green]Fix:[/green] Pause before important information to create anticipation.

[bold]5. Harsh Intonation[/bold]
   Falling pitch throughout can sound angry in English.
   [green]Fix:[/green] Rise slightly on positive statements, only fall on negatives.

[bold yellow]Practice Sentences:[/bold yellow]

Try these with exaggerated prosody:

  "I THINK we should WAIT until TOMORROW."
  (Stress caps, reduce others, pause after "think")

  "That's INteresting! Tell me MORE about it."
  (Rise on "interesting", fall on "more")

  "I NEver said she STOLE my MOney."
  (Each word can be stressed for different meanings)
"""
    console.print(tips_text)


@app.command()
def practice(
    category: Optional[str] = typer.Argument(
        None,
        help="Category: stress, intonation, professional, rhythm, passages",
    ),
    prompt_id: Optional[str] = typer.Option(
        None,
        "--id", "-i",
        help="Specific prompt ID to practice.",
    ),
    text: Optional[str] = typer.Option(
        None,
        "--text", "-t",
        help="Custom text to practice reading.",
    ),
    list_prompts: bool = typer.Option(
        False,
        "--list", "-l",
        help="List all available practice prompts.",
    ),
    playback: bool = typer.Option(
        False,
        "--playback", "-p",
        help="Play back your recording after analysis.",
    ),
    save: bool = typer.Option(
        False,
        "--save", "-s",
        help="Save the recording for later reference.",
    ),
):
    """
    Practice reading specific texts with AI feedback.

    Shows you a text to read aloud, then analyzes your prosody AND
    compares your pronunciation against the expected text.

    Examples:
        prosody practice                    # Random prompt
        prosody practice professional       # Random from category
        prosody practice --id pro_1         # Specific prompt
        prosody practice --text "Hello"     # Custom text
        prosody practice --list             # Show all prompts
    """
    try:
        # List mode
        if list_prompts:
            console.print()
            console.print(Panel("[bold]Available Practice Prompts[/bold]", border_style="blue"))
            console.print()

            for cat in get_all_categories():
                console.print(f"[bold cyan]{cat.upper()}[/bold cyan]")
                for p in get_prompts_by_category(cat):
                    console.print(f"  [dim]{p['id']}:[/dim] {p['text'][:60]}...")
                console.print()
            return

        # Get the prompt to practice
        if text:
            # Custom text
            prompt_data = {
                "id": "custom",
                "text": text,
                "tip": "Read naturally with good prosody.",
                "focus": "all"
            }
        elif prompt_id:
            # Specific prompt by ID
            prompt_data = get_prompt_by_id(prompt_id)
            if not prompt_data:
                console.print(f"[red]Prompt '{prompt_id}' not found. Use --list to see available prompts.[/red]")
                raise typer.Exit(1)
        elif category:
            # Random from category
            prompts = get_prompts_by_category(category)
            if not prompts:
                console.print(f"[red]Category '{category}' not found. Options: {', '.join(get_all_categories())}[/red]")
                raise typer.Exit(1)
            prompt_data = get_random_prompt(category)
        else:
            # Random from all
            prompt_data = get_random_prompt()

        # Display the text to read
        console.print()
        console.print(Panel(
            f"[bold white]{prompt_data['text']}[/bold white]",
            title="[bold green]READ THIS TEXT[/bold green]",
            border_style="green",
            padding=(1, 2),
        ))

        if prompt_data.get("tip"):
            console.print(f"[yellow]Tip:[/yellow] {prompt_data['tip']}")

        if prompt_data.get("focus"):
            console.print(f"[dim]Focus: {prompt_data['focus']}[/dim]")

        console.print()
        console.print(
            Panel(
                "[bold]Press Enter to stop recording[/bold]",
                title="[bold blue]Recording[/bold blue]",
                border_style="blue",
            )
        )
        console.print("[dim]Recording...[/dim]", end=" ")

        # Record
        audio_data, sample_rate = record_audio()
        duration = get_duration(audio_data, sample_rate)
        console.print(f"[green]Done![/green] ({duration:.1f} seconds)\n")

        if duration < 1.0:
            console.print("[red]Recording too short. Please read the full text.[/red]")
            raise typer.Exit(1)

        if save:
            filepath = save_recording(audio_data, sample_rate)
            console.print(f"[dim]Saved to: {filepath}[/dim]\n")

        # Analyze prosody
        console.print("[dim]Analyzing prosody...[/dim]")
        analysis = analyze_prosody(audio_data, sample_rate)
        display_analysis(analysis)

        # AI coaching with expected text comparison
        console.print("[dim]Getting AI feedback on your reading...[/dim]")
        try:
            from coach import analyze_with_coach_practice, display_coaching
            coaching = analyze_with_coach_practice(
                audio_data, sample_rate, analysis, prompt_data["text"]
            )
            display_coaching(coaching, console)
        except Exception as e:
            console.print(f"[yellow]AI feedback unavailable: {e}[/yellow]")

        # Playback if requested
        if playback:
            console.print("[dim]Playing back your recording...[/dim]")
            play_audio(audio_data, sample_rate)
            console.print("[green]Playback complete.[/green]\n")

    except KeyboardInterrupt:
        console.print("\n[yellow]Practice cancelled.[/yellow]")
        raise typer.Exit(0)
    except Exception as e:
        console.print(f"\n[red]Error: {e}[/red]")
        raise typer.Exit(1)


@app.callback()
def main():
    """
    Prosody Coach - Improve your English speaking patterns.

    Analyzes 5 key components: pitch, volume, tempo, rhythm, and pauses.
    Designed for Spanish speakers learning English.
    """
    pass


if __name__ == "__main__":
    app()
