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
from storage import save_session, get_history, get_stats, get_best_and_worst, get_session

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

        # Save session to database
        transcript = None
        ai_summary = None
        ai_tips = None

        # AI coaching if enabled
        if coach:
            console.print("[dim]Getting AI coaching feedback...[/dim]")
            try:
                coaching = analyze_with_coach(audio_data, sample_rate, analysis)
                display_coaching(coaching, console)
                transcript = coaching.transcript
                ai_summary = coaching.overall_feedback
                ai_tips = coaching.coaching_tips
            except Exception as e:
                console.print(f"[yellow]AI coaching unavailable: {e}[/yellow]")

        # Save session
        save_session(
            analysis,
            mode="analyze",
            transcript=transcript,
            ai_summary=ai_summary,
            ai_tips=ai_tips,
        )

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
        transcript = None
        ai_summary = None
        ai_tips = None
        console.print("[dim]Getting AI feedback on your reading...[/dim]")
        try:
            from coach import analyze_with_coach_practice, display_coaching
            coaching = analyze_with_coach_practice(
                audio_data, sample_rate, analysis, prompt_data["text"]
            )
            display_coaching(coaching, console)
            transcript = coaching.transcript
            ai_summary = coaching.overall_feedback
            ai_tips = coaching.coaching_tips
        except Exception as e:
            console.print(f"[yellow]AI feedback unavailable: {e}[/yellow]")

        # Save session
        save_session(
            analysis,
            mode="practice",
            prompt_id=prompt_data.get("id"),
            transcript=transcript,
            ai_summary=ai_summary,
            ai_tips=ai_tips,
        )

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


@app.command()
def history(
    limit: int = typer.Option(
        10,
        "--limit", "-n",
        help="Number of sessions to show.",
    ),
    mode: Optional[str] = typer.Option(
        None,
        "--mode", "-m",
        help="Filter by mode: analyze or practice.",
    ),
):
    """
    View your practice history.

    Shows recent sessions with scores and timestamps.
    """
    from rich.table import Table
    from datetime import datetime

    sessions = get_history(limit=limit, mode=mode)

    if not sessions:
        console.print("\n[yellow]No sessions recorded yet. Run 'prosody analyze' to start.[/yellow]\n")
        return

    console.print()
    table = Table(title="Practice History", border_style="blue")
    table.add_column("ID", style="dim")
    table.add_column("Date", style="dim")
    table.add_column("Mode", style="cyan")
    table.add_column("Duration", justify="right")
    table.add_column("Pitch", justify="center")
    table.add_column("Volume", justify="center")
    table.add_column("Tempo", justify="center")
    table.add_column("Rhythm", justify="center")
    table.add_column("Pauses", justify="center")
    table.add_column("Overall", justify="center", style="bold")

    for s in sessions:
        dt = datetime.fromisoformat(s["created_at"])
        date_str = dt.strftime("%m/%d %H:%M")
        table.add_row(
            str(s["id"]),
            date_str,
            s["mode"],
            f"{s['duration']:.0f}s",
            str(s["pitch_score"]),
            str(s["volume_score"]),
            str(s["tempo_score"]),
            str(s["rhythm_score"]),
            str(s["pause_score"]),
            f"{s['overall_score']:.1f}",
        )

    console.print(table)
    console.print("[dim]Use 'prosody show <ID>' to view session details[/dim]")
    console.print()


@app.command()
def show(
    session_id: int = typer.Argument(..., help="Session ID to view"),
):
    """
    View detailed feedback for a specific session.

    Shows all prosody feedback and AI coaching tips.
    """
    from datetime import datetime

    session = get_session(session_id)

    if not session:
        console.print(f"\n[red]Session {session_id} not found.[/red]\n")
        raise typer.Exit(1)

    console.print()
    dt = datetime.fromisoformat(session["created_at"])
    console.print(Panel(
        f"[bold]Session {session_id}[/bold] - {dt.strftime('%B %d, %Y at %H:%M')}",
        border_style="blue"
    ))

    # Basic info
    console.print(f"\n[bold]Mode:[/bold] {session['mode']}")
    console.print(f"[bold]Duration:[/bold] {session['duration']:.0f} seconds")
    console.print(f"[bold]Overall Score:[/bold] {session['overall_score']}/10")

    # Prosody feedback
    console.print("\n[bold cyan]Prosody Analysis:[/bold cyan]")
    console.print(f"  [bold]Pitch ({session['pitch_score']}/10):[/bold] {session.get('pitch_feedback', 'N/A')}")
    console.print(f"  [bold]Volume ({session['volume_score']}/10):[/bold] {session.get('volume_feedback', 'N/A')}")
    console.print(f"  [bold]Tempo ({session['tempo_score']}/10):[/bold] {session.get('tempo_feedback', 'N/A')}")
    console.print(f"  [bold]Rhythm ({session['rhythm_score']}/10):[/bold] {session.get('rhythm_feedback', 'N/A')}")
    console.print(f"  [bold]Pauses ({session['pause_score']}/10):[/bold] {session.get('pause_feedback', 'N/A')}")

    # Transcript
    if session.get("transcript"):
        console.print("\n[bold cyan]Transcript:[/bold cyan]")
        console.print(f"  {session['transcript']}")

    # AI Summary
    if session.get("ai_summary"):
        console.print("\n[bold cyan]AI Summary:[/bold cyan]")
        console.print(f"  {session['ai_summary']}")

    # AI Tips
    if session.get("ai_tips"):
        console.print("\n[bold cyan]AI Coaching Tips:[/bold cyan]")
        for tip in session["ai_tips"]:
            console.print(f"  • {tip}")

    console.print()


@app.command()
def progress():
    """
    View your progress and statistics.

    Shows overall stats, averages, and trends.
    """
    stats = get_stats()

    if stats["total_sessions"] == 0:
        console.print("\n[yellow]No sessions recorded yet. Run 'prosody analyze' to start.[/yellow]\n")
        return

    console.print()
    console.print(Panel("[bold]Your Progress[/bold]", border_style="green"))

    # Summary stats
    console.print(f"\n[bold]Total Sessions:[/bold] {stats['total_sessions']}")
    console.print(f"[bold]Total Practice Time:[/bold] {stats['total_practice_time']} minutes")

    # Average scores
    if stats["averages"]:
        console.print("\n[bold cyan]Average Scores:[/bold cyan]")
        avg = stats["averages"]
        console.print(f"  Pitch:   {avg['pitch']}/10")
        console.print(f"  Volume:  {avg['volume']}/10")
        console.print(f"  Tempo:   {avg['tempo']}/10")
        console.print(f"  Rhythm:  {avg['rhythm']}/10")
        console.print(f"  Pauses:  {avg['pause']}/10")
        console.print(f"  [bold]Overall: {avg['overall']}/10[/bold]")

    # Trend
    if stats["recent_trend"] is not None:
        trend = stats["recent_trend"]
        if trend > 0:
            console.print(f"\n[green]Trend: +{trend:.1f} (improving)[/green]")
        elif trend < 0:
            console.print(f"\n[red]Trend: {trend:.1f} (needs work)[/red]")
        else:
            console.print(f"\n[yellow]Trend: Steady[/yellow]")

    # Best/worst components
    bw = get_best_and_worst()
    if bw["best"] and bw["worst"]:
        console.print(f"\n[green]Strongest:[/green] {bw['best'][0].title()} ({bw['best'][1]}/10)")
        console.print(f"[yellow]Focus on:[/yellow] {bw['worst'][0].title()} ({bw['worst'][1]}/10)")

    console.print()


@app.callback(invoke_without_command=True)
def main(ctx: typer.Context):
    """
    Prosody Coach - Improve your English speaking patterns.

    Analyzes 5 key components: pitch, volume, tempo, rhythm, and pauses.
    Designed for Spanish speakers learning English.
    """
    if ctx.invoked_subcommand is not None:
        return

    # Show interactive menu
    show_interactive_menu()


def show_interactive_menu():
    """Display interactive menu for selecting actions."""
    from rich.prompt import Prompt

    menu_options = {
        "1": ("analyze", "Record and analyze your speech"),
        "2": ("practice", "Practice with guided prompts"),
        "3": ("history", "View your practice history"),
        "4": ("progress", "View your progress stats"),
        "5": ("info", "Learn about prosody components"),
        "6": ("tips", "Tips for Spanish speakers"),
        "q": ("quit", "Exit"),
    }

    while True:
        console.print()
        console.print(Panel(
            "[bold]Prosody Coach[/bold]\n[dim]Improve your English speaking patterns[/dim]",
            border_style="blue",
        ))
        console.print()

        for key, (cmd, desc) in menu_options.items():
            if key == "q":
                console.print(f"  [dim]{key}[/dim]  [red]{desc}[/red]")
            else:
                console.print(f"  [bold cyan]{key}[/bold cyan]  {desc}")

        console.print()
        choice = Prompt.ask(
            "[bold]Select an option[/bold]",
            choices=list(menu_options.keys()),
            default="1",
            show_choices=False,
        )

        if choice == "q":
            console.print("[dim]Goodbye![/dim]\n")
            break
        elif choice == "1":
            save = Prompt.ask("Save recording?", choices=["y", "n"], default="n") == "y"
            playback = Prompt.ask("Play back after?", choices=["y", "n"], default="y") == "y"
            analyze(file=None, save=save, quick=False, coach=True, playback=playback)
        elif choice == "2":
            show_practice_menu(Prompt)
        elif choice == "3":
            history(limit=10, mode=None)
        elif choice == "4":
            progress()
        elif choice == "5":
            info()
        elif choice == "6":
            tips()


def show_practice_menu(Prompt):
    """Display submenu for practice categories."""
    categories = {
        "1": ("stress", "Stress - Word emphasis practice"),
        "2": ("intonation", "Intonation - Pitch patterns"),
        "3": ("rhythm", "Rhythm - Syllable timing"),
        "4": ("professional", "Professional - Business scenarios"),
        "5": ("passages", "Passages - Longer readings"),
        "6": ("random", "Random - Any category"),
        "b": ("back", "Back to main menu"),
    }

    console.print()
    console.print(Panel(
        "[bold]Practice Categories[/bold]\n[dim]Choose a focus area[/dim]",
        border_style="green",
    ))
    console.print()

    for key, (cat, desc) in categories.items():
        if key == "b":
            console.print(f"  [dim]{key}[/dim]  [yellow]{desc}[/yellow]")
        else:
            console.print(f"  [bold cyan]{key}[/bold cyan]  {desc}")

    console.print()
    choice = Prompt.ask(
        "[bold]Select category[/bold]",
        choices=list(categories.keys()),
        default="6",
        show_choices=False,
    )

    if choice == "b":
        return

    save = Prompt.ask("Save recording?", choices=["y", "n"], default="n") == "y"
    playback = Prompt.ask("Play back after?", choices=["y", "n"], default="y") == "y"

    if choice == "6":
        practice(category=None, prompt_id=None, text=None, list_prompts=False, playback=playback, save=save)
    else:
        cat_name = categories[choice][0]
        practice(category=cat_name, prompt_id=None, text=None, list_prompts=False, playback=playback, save=save)


if __name__ == "__main__":
    app()
