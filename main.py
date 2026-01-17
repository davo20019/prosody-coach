#!/usr/bin/env python3
"""Prosody Coach CLI - Improve your English pronunciation and speaking patterns."""

import typer
from rich.console import Console
from rich.panel import Panel
from pathlib import Path
from typing import Optional

from recorder import record_audio, save_recording, load_audio, get_duration, play_audio, play_tts
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
from storage import (
    save_session, get_history, get_stats, get_best_and_worst, get_session,
    get_user_weaknesses, get_due_sounds, update_sound_after_practice, get_sound_stats,
    get_due_words, update_word_after_practice, get_word_stats
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
        import threading
        transcript = None
        ai_summary = None
        ai_tips = None
        grammar_issues = None
        suggested_revision = None
        confidence_score = None
        confidence_feedback = None
        filler_word_count = None
        filler_words_detail = None
        pronunciation_issues = None
        fluency_score = None
        fluency_feedback = None
        coaching_result = {"coaching": None, "error": None}

        def fetch_coaching():
            try:
                coaching_result["coaching"] = analyze_with_coach(audio_data, sample_rate, analysis)
            except Exception as e:
                coaching_result["error"] = str(e)

        # Start AI coaching in background if enabled
        ai_thread = None
        if coach:
            ai_thread = threading.Thread(target=fetch_coaching)
            ai_thread.start()

        # Playback while AI processes
        if playback:
            msg = "[dim]Playing back (AI processing in background)...[/dim]" if coach else "[dim]Playing back your recording...[/dim]"
            console.print(msg)
            play_audio(audio_data, sample_rate)

        # Wait for AI to finish if still running
        if ai_thread:
            if ai_thread.is_alive():
                console.print("[dim]Waiting for AI feedback...[/dim]")
            ai_thread.join()

            if coaching_result["coaching"]:
                coaching = coaching_result["coaching"]
                display_coaching(coaching, console)
                transcript = coaching.transcript
                ai_summary = coaching.overall_feedback
                ai_tips = coaching.coaching_tips
                grammar_issues = coaching.grammar_issues
                suggested_revision = coaching.suggested_revision
                confidence_score = coaching.confidence_score
                confidence_feedback = coaching.confidence_feedback
                filler_word_count = coaching.filler_word_count
                filler_words_detail = coaching.filler_words_detail
                pronunciation_issues = coaching.pronunciation_issues
                fluency_score = coaching.fluency_score
                fluency_feedback = coaching.fluency_feedback
            elif coaching_result["error"]:
                console.print(f"[yellow]AI coaching unavailable: {coaching_result['error']}[/yellow]")

        # Save session
        save_session(
            analysis,
            mode="analyze",
            transcript=transcript,
            ai_summary=ai_summary,
            ai_tips=ai_tips,
            grammar_issues=grammar_issues,
            suggested_revision=suggested_revision,
            confidence_score=confidence_score,
            confidence_feedback=confidence_feedback,
            filler_word_count=filler_word_count,
            filler_words_detail=filler_words_detail,
            pronunciation_issues=pronunciation_issues,
            fluency_score=fluency_score,
            fluency_feedback=fluency_feedback,
        )

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

        # Play reference audio (TTS)
        console.print()
        console.print("[bold cyan]🔊 Listen first...[/bold cyan]")
        if not play_tts(prompt_data["text"]):
            console.print("[dim]TTS unavailable - skipping reference audio[/dim]")

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

        # Start AI request in background while playing back
        import threading
        from coach import analyze_with_coach_practice, display_coaching

        transcript = None
        ai_summary = None
        ai_tips = None
        grammar_issues = None
        suggested_revision = None
        confidence_score = None
        confidence_feedback = None
        filler_word_count = None
        filler_words_detail = None
        pronunciation_issues = None
        fluency_score = None
        fluency_feedback = None
        coaching_result = {"coaching": None, "error": None}

        def fetch_coaching():
            try:
                coaching_result["coaching"] = analyze_with_coach_practice(
                    audio_data, sample_rate, analysis, prompt_data["text"]
                )
            except Exception as e:
                coaching_result["error"] = str(e)

        # Start AI request in background
        ai_thread = threading.Thread(target=fetch_coaching)
        ai_thread.start()

        # Playback while AI processes
        if playback:
            console.print("[dim]Playing back (AI processing in background)...[/dim]")
            play_audio(audio_data, sample_rate)

        # Wait for AI to finish if still running
        if ai_thread.is_alive():
            console.print("[dim]Waiting for AI feedback...[/dim]")
        ai_thread.join()

        # Display AI coaching results
        if coaching_result["coaching"]:
            coaching = coaching_result["coaching"]
            display_coaching(coaching, console)
            transcript = coaching.transcript
            ai_summary = coaching.overall_feedback
            ai_tips = coaching.coaching_tips
            grammar_issues = coaching.grammar_issues
            suggested_revision = coaching.suggested_revision
            confidence_score = coaching.confidence_score
            confidence_feedback = coaching.confidence_feedback
            filler_word_count = coaching.filler_word_count
            filler_words_detail = coaching.filler_words_detail
            pronunciation_issues = coaching.pronunciation_issues
            fluency_score = coaching.fluency_score
            fluency_feedback = coaching.fluency_feedback
        elif coaching_result["error"]:
            console.print(f"[yellow]AI feedback unavailable: {coaching_result['error']}[/yellow]")

        # Save session
        save_session(
            analysis,
            mode="practice",
            prompt_id=prompt_data.get("id"),
            transcript=transcript,
            ai_summary=ai_summary,
            ai_tips=ai_tips,
            grammar_issues=grammar_issues,
            suggested_revision=suggested_revision,
            confidence_score=confidence_score,
            confidence_feedback=confidence_feedback,
            filler_word_count=filler_word_count,
            filler_words_detail=filler_words_detail,
            pronunciation_issues=pronunciation_issues,
            fluency_score=fluency_score,
            fluency_feedback=fluency_feedback,
        )

    except KeyboardInterrupt:
        console.print("\n[yellow]Practice cancelled.[/yellow]")
        raise typer.Exit(0)
    except Exception as e:
        console.print(f"\n[red]Error: {e}[/red]")
        raise typer.Exit(1)


@app.command()
def train(
    playback: bool = typer.Option(
        True,
        "--playback/--no-playback", "-p/-P",
        help="Play back your recording after analysis.",
    ),
    save: bool = typer.Option(
        True,
        "--save/--no-save", "-s/-S",
        help="Save recordings to disk.",
    ),
):
    """
    Start a tailored training session based on your practice history.

    Analyzes your past sessions to identify weak areas and generates
    custom practice prompts targeting your specific needs.
    """
    from rich.prompt import Prompt
    from coach import generate_tailored_prompt, analyze_with_coach_practice, display_coaching
    from recorder import play_tts

    weaknesses = get_user_weaknesses(limit=10)

    if not weaknesses.get("sufficient_data"):
        console.print()
        console.print(Panel(
            "[yellow]Not enough data yet![/yellow]\n\n"
            f"You have {weaknesses.get('session_count', 0)} sessions. "
            "Complete at least 3 sessions to unlock tailored training.\n\n"
            "[dim]Try 'prosody analyze' or 'prosody practice' first.[/dim]",
            title="[bold]Tailored Training[/bold]",
            border_style="yellow",
        ))
        raise typer.Exit(0)

    console.print()
    console.print(Panel(
        "[bold green]Tailored Training[/bold green]\n\n"
        f"[dim]Difficulty:[/dim] [bold]{weaknesses['difficulty'].title()}[/bold]\n"
        f"[dim]Based on:[/dim] {weaknesses['session_count']} sessions",
        border_style="green",
    ))

    # Show focus areas
    if weaknesses.get("focus_areas"):
        console.print()
        console.print("[bold]Focus areas for this session:[/bold]")
        for focus in weaknesses["focus_areas"]:
            console.print(f"  [yellow]•[/yellow] {focus['description']}")

    # Training loop
    while True:
        console.print()
        console.print("[dim]Generating tailored prompt...[/dim]")

        try:
            prompt_data = generate_tailored_prompt(weaknesses)
        except Exception as e:
            console.print(f"[red]Error generating prompt: {e}[/red]")
            raise typer.Exit(1)

        console.print()
        # Build display with key sounds if available
        display_text = f"[bold]{prompt_data['text']}[/bold]"
        if prompt_data.get("key_sounds"):
            display_text += f"\n\n[dim]Key sounds:[/dim] [yellow]{prompt_data['key_sounds']}[/yellow]"

        console.print(Panel(
            display_text,
            title="[bold cyan]READ THIS ALOUD[/bold cyan]",
            border_style="cyan",
        ))

        # Speak the reference
        console.print()
        console.print("[dim]Playing reference audio...[/dim]")
        play_tts(prompt_data["text"])

        # Record user
        console.print()
        try:
            audio_data, sample_rate = record_audio()
        except KeyboardInterrupt:
            console.print("\n[yellow]Training cancelled.[/yellow]")
            raise typer.Exit(0)

        duration = get_duration(audio_data, sample_rate)
        console.print(f"[green]Done![/green] ({duration:.1f} seconds)\n")

        if duration < 1.0:
            console.print("[red]Recording too short. Please read the full text.[/red]")
            continue

        if save:
            filepath = save_recording(audio_data, sample_rate)
            console.print(f"[dim]Saved to: {filepath}[/dim]\n")

        # Analyze prosody
        console.print("[dim]Analyzing prosody...[/dim]")
        analysis = analyze_prosody(audio_data, sample_rate)
        display_analysis(analysis)

        # AI coaching (parallel with playback)
        import threading
        transcript = None
        ai_summary = None
        ai_tips = None
        grammar_issues = None
        suggested_revision = None
        confidence_score = None
        confidence_feedback = None
        filler_word_count = None
        filler_words_detail = None
        pronunciation_issues = None
        fluency_score = None
        fluency_feedback = None
        coaching_result = {"coaching": None, "error": None}

        def fetch_coaching():
            try:
                coaching_result["coaching"] = analyze_with_coach_practice(
                    audio_data, sample_rate, analysis, prompt_data["text"]
                )
            except Exception as e:
                coaching_result["error"] = str(e)

        ai_thread = threading.Thread(target=fetch_coaching)
        ai_thread.start()

        if playback:
            console.print("[dim]Playing back (AI processing in background)...[/dim]")
            play_audio(audio_data, sample_rate)

        if ai_thread.is_alive():
            console.print("[dim]Waiting for AI feedback...[/dim]")
        ai_thread.join()

        if coaching_result["coaching"]:
            coaching = coaching_result["coaching"]
            display_coaching(coaching, console)
            transcript = coaching.transcript
            ai_summary = coaching.overall_feedback
            ai_tips = coaching.coaching_tips
            grammar_issues = coaching.grammar_issues
            suggested_revision = coaching.suggested_revision
            confidence_score = coaching.confidence_score
            confidence_feedback = coaching.confidence_feedback
            filler_word_count = coaching.filler_word_count
            filler_words_detail = coaching.filler_words_detail
            pronunciation_issues = coaching.pronunciation_issues
            fluency_score = coaching.fluency_score
            fluency_feedback = coaching.fluency_feedback
        elif coaching_result["error"]:
            console.print(f"[yellow]AI feedback unavailable: {coaching_result['error']}[/yellow]")

        # Save session
        save_session(
            analysis,
            mode="practice",
            prompt_id=prompt_data.get("id"),
            transcript=transcript,
            ai_summary=ai_summary,
            ai_tips=ai_tips,
            grammar_issues=grammar_issues,
            suggested_revision=suggested_revision,
            confidence_score=confidence_score,
            confidence_feedback=confidence_feedback,
            filler_word_count=filler_word_count,
            filler_words_detail=filler_words_detail,
            pronunciation_issues=pronunciation_issues,
            fluency_score=fluency_score,
            fluency_feedback=fluency_feedback,
        )

        console.print()
        console.print("[dim]─" * 40 + "[/dim]")
        action = Prompt.ask("Press Enter for next prompt, q to quit", default="", show_default=False)
        if action.lower() == "q":
            break


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
    from storage import get_user_weaknesses, get_due_sounds, get_sound_stats, get_due_words, get_word_stats

    menu_options = {
        "1": ("analyze", "Record and analyze your speech"),
        "2": ("practice", "Practice with guided prompts"),
        "3": ("train", "Tailored training (based on your history)"),
        "4": ("history", "View your practice history"),
        "5": ("progress", "View your progress stats"),
        "6": ("info", "Learn about prosody components"),
        "7": ("tips", "Tips for Spanish speakers"),
        "q": ("quit", "Exit"),
    }

    while True:
        console.print()
        console.print(Panel(
            "[bold]Prosody Coach[/bold]\n[dim]Improve your English speaking patterns[/dim]",
            border_style="blue",
        ))

        # Check for tailored training nudge
        weaknesses = get_user_weaknesses(limit=10)

        # Check for due sounds (spaced repetition)
        due_sounds = get_due_sounds(limit=10)
        sound_stats = get_sound_stats()

        # Check for due words (mispronounced words)
        due_words = get_due_words(limit=10)
        word_stats = get_word_stats()

        if due_words:
            console.print()
            words_preview = ", ".join([w["word"] for w in due_words[:5]])
            if len(due_words) > 5:
                words_preview += f" +{len(due_words) - 5} more"
            console.print(f"[bold red]📝 {len(due_words)} words due for review:[/bold red] [yellow]{words_preview}[/yellow]")

        if due_sounds:
            console.print()
            due_count = len(due_sounds)
            sounds_preview = ", ".join([s["sound"] for s in due_sounds[:3]])
            if due_count > 3:
                sounds_preview += f" +{due_count - 3} more"
            console.print(f"[bold red]🔔 {due_count} sounds due for review:[/bold red] [yellow]{sounds_preview}[/yellow]")

        if weaknesses.get("sufficient_data") and weaknesses.get("focus_areas"):
            focus_count = len(weaknesses["focus_areas"])
            console.print()
            console.print(f"[bold green]💡 Tip:[/bold green] [dim]You have {weaknesses['session_count']} sessions. "
                          f"Try [bold]Tailored training[/bold] to focus on {focus_count} identified areas![/dim]")

        console.print()

        for key, (cmd, desc) in menu_options.items():
            if key == "q":
                console.print(f"  [dim]{key}[/dim]  [red]{desc}[/red]")
            elif key == "3":
                # Highlight tailored training if data is available or sounds are due
                if due_sounds:
                    console.print(f"  [bold red]{key}[/bold red]  [red]{desc}[/red] 🔔 {len(due_sounds)} due")
                elif weaknesses.get("sufficient_data"):
                    console.print(f"  [bold green]{key}[/bold green]  [green]{desc}[/green] ✨")
                else:
                    console.print(f"  [dim]{key}[/dim]  [dim]{desc} (need 3+ sessions)[/dim]")
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
            save = Prompt.ask("Save recording?", choices=["y", "n"], default="y") == "y"
            playback = Prompt.ask("Play back after?", choices=["y", "n"], default="y") == "y"
            analyze(file=None, save=save, quick=False, coach=True, playback=playback)
        elif choice == "2":
            show_practice_menu(Prompt)
        elif choice == "3":
            run_tailored_training(Prompt, weaknesses)
        elif choice == "4":
            history(limit=10, mode=None)
        elif choice == "5":
            progress()
        elif choice == "6":
            info()
        elif choice == "7":
            tips()


def run_tailored_training(Prompt, weaknesses: dict):
    """Run tailored training session based on user's weaknesses."""
    from coach import generate_tailored_prompt, analyze_with_coach_practice, display_coaching
    from analyzer import analyze_prosody
    from recorder import record_audio, play_audio, get_duration, save_recording, play_tts
    from storage import save_session, get_due_sounds, update_sound_after_practice, get_due_words, update_word_after_practice

    if not weaknesses.get("sufficient_data"):
        console.print()
        console.print(Panel(
            "[yellow]Not enough data yet![/yellow]\n\n"
            f"You have {weaknesses.get('session_count', 0)} sessions. "
            "Complete at least 3 sessions to unlock tailored training.\n\n"
            "[dim]Try 'Record and analyze' or 'Practice with prompts' first.[/dim]",
            title="[bold]Tailored Training[/bold]",
            border_style="yellow",
        ))
        return

    # Get sounds and words due for spaced repetition review
    due_sounds = get_due_sounds(limit=5)
    due_words = get_due_words(limit=5)

    console.print()
    info_text = (
        "[bold green]Tailored Training[/bold green]\n\n"
        f"[dim]Difficulty:[/dim] [bold]{weaknesses['difficulty'].title()}[/bold]\n"
        f"[dim]Based on:[/dim] {weaknesses['session_count']} sessions"
    )
    if due_words:
        info_text += f"\n[dim]Words due for review:[/dim] [bold yellow]{len(due_words)}[/bold yellow]"
    if due_sounds:
        info_text += f"\n[dim]Sounds due for review:[/dim] [bold yellow]{len(due_sounds)}[/bold yellow]"

    console.print(Panel(info_text, border_style="green"))

    # Show focus areas
    if weaknesses.get("focus_areas"):
        console.print()
        console.print("[bold]Focus areas for this session:[/bold]")
        for focus in weaknesses["focus_areas"]:
            console.print(f"  [yellow]•[/yellow] {focus['description']}")

    # Show due words (mispronounced words)
    if due_words:
        console.print()
        console.print("[bold]Words due for review (you've mispronounced these):[/bold]")
        for w in due_words[:5]:
            ipa = f" /{w['ipa']}/" if w.get('ipa') else ""
            times = f" ({w['times_mispronounced']}x)" if w.get('times_mispronounced', 0) > 1 else ""
            console.print(f"  [red]•[/red] {w['word']}{ipa}{times}")

    # Show due sounds
    if due_sounds:
        console.print()
        console.print("[bold]Sounds due for review (spaced repetition):[/bold]")
        for s in due_sounds[:5]:
            ipa = f" {s['ipa']}" if s.get('ipa') else ""
            console.print(f"  [red]•[/red] {s['sound']}{ipa}")

    console.print()
    save = Prompt.ask("Save recordings?", choices=["y", "n"], default="y") == "y"
    playback = Prompt.ask("Play back after?", choices=["y", "n"], default="y") == "y"

    # Training loop
    while True:
        # Refresh due sounds and words each iteration
        due_sounds = get_due_sounds(limit=5)
        due_words = get_due_words(limit=5)

        console.print()
        console.print("[dim]Generating tailored prompt...[/dim]")

        try:
            prompt_data = generate_tailored_prompt(weaknesses, due_sounds=due_sounds, due_words=due_words)
        except Exception as e:
            console.print(f"[red]Error generating prompt: {e}[/red]")
            return

        console.print()
        # Build display with key sounds if available
        display_text = f"[bold]{prompt_data['text']}[/bold]"
        if prompt_data.get("key_sounds"):
            display_text += f"\n\n[dim]Key sounds:[/dim] [yellow]{prompt_data['key_sounds']}[/yellow]"

        console.print(Panel(
            display_text,
            title="[bold cyan]READ THIS ALOUD[/bold cyan]",
            border_style="cyan",
        ))

        # Speak the reference
        console.print()
        console.print("[dim]Playing reference audio...[/dim]")
        play_tts(prompt_data["text"])

        # Record user
        console.print()
        try:
            audio_data, sample_rate = record_audio()
        except KeyboardInterrupt:
            console.print("\n[yellow]Recording cancelled.[/yellow]")
            break

        duration = get_duration(audio_data, sample_rate)
        console.print(f"[green]Done![/green] ({duration:.1f} seconds)\n")

        if duration < 1.0:
            console.print("[red]Recording too short. Please read the full text.[/red]")
            continue

        if save:
            filepath = save_recording(audio_data, sample_rate)
            console.print(f"[dim]Saved to: {filepath}[/dim]\n")

        # Analyze prosody
        console.print("[dim]Analyzing prosody...[/dim]")
        analysis = analyze_prosody(audio_data, sample_rate)
        display_analysis(analysis)

        # AI coaching (parallel with playback)
        import threading
        transcript = None
        ai_summary = None
        ai_tips = None
        grammar_issues = None
        suggested_revision = None
        confidence_score = None
        confidence_feedback = None
        filler_word_count = None
        filler_words_detail = None
        pronunciation_issues = None
        fluency_score = None
        fluency_feedback = None
        coaching_result = {"coaching": None, "error": None}

        def fetch_coaching():
            try:
                coaching_result["coaching"] = analyze_with_coach_practice(
                    audio_data, sample_rate, analysis, prompt_data["text"]
                )
            except Exception as e:
                coaching_result["error"] = str(e)

        ai_thread = threading.Thread(target=fetch_coaching)
        ai_thread.start()

        if playback:
            console.print("[dim]Playing back (AI processing in background)...[/dim]")
            play_audio(audio_data, sample_rate)

        if ai_thread.is_alive():
            console.print("[dim]Waiting for AI feedback...[/dim]")
        ai_thread.join()

        if coaching_result["coaching"]:
            coaching = coaching_result["coaching"]
            display_coaching(coaching, console)
            transcript = coaching.transcript
            ai_summary = coaching.overall_feedback
            ai_tips = coaching.coaching_tips
            grammar_issues = coaching.grammar_issues
            suggested_revision = coaching.suggested_revision
            confidence_score = coaching.confidence_score
            confidence_feedback = coaching.confidence_feedback
            filler_word_count = coaching.filler_word_count
            filler_words_detail = coaching.filler_words_detail
            pronunciation_issues = coaching.pronunciation_issues
            fluency_score = coaching.fluency_score
            fluency_feedback = coaching.fluency_feedback
        elif coaching_result["error"]:
            console.print(f"[yellow]AI feedback unavailable: {coaching_result['error']}[/yellow]")

        # Save session
        save_session(
            analysis,
            mode="practice",
            prompt_id=prompt_data.get("id"),
            transcript=transcript,
            ai_summary=ai_summary,
            ai_tips=ai_tips,
            grammar_issues=grammar_issues,
            suggested_revision=suggested_revision,
            confidence_score=confidence_score,
            confidence_feedback=confidence_feedback,
            filler_word_count=filler_word_count,
            filler_words_detail=filler_words_detail,
            pronunciation_issues=pronunciation_issues,
            fluency_score=fluency_score,
            fluency_feedback=fluency_feedback,
        )

        # Update spaced repetition for target sounds
        target_sounds = prompt_data.get("target_sounds", [])
        if target_sounds:
            # Get sounds that were flagged as issues in this session
            flagged_sounds = set()
            if pronunciation_issues:
                for issue in pronunciation_issues:
                    flagged_sounds.add(issue.get("sound", "").lower())

            console.print()
            console.print("[bold]Spaced repetition update (sounds):[/bold]")
            # Update each target sound based on whether it was flagged
            for target in target_sounds:
                sound = target.get("sound", "")
                if sound:
                    # Sound was correct if it wasn't flagged as an issue
                    was_correct = sound.lower() not in flagged_sounds
                    update_sound_after_practice(sound, was_correct)
                    if was_correct:
                        console.print(f"  [green]✓[/green] '{sound}' - correct! (interval increased)")
                    else:
                        console.print(f"  [red]✗[/red] '{sound}' - needs more practice (interval reset)")

        # Update spaced repetition for target words
        target_words = prompt_data.get("target_words", [])
        if target_words:
            # Get words that were mispronounced in this session
            flagged_words = set()
            if pronunciation_issues:
                for issue in pronunciation_issues:
                    example = issue.get("example", "").lower()
                    # Extract word from example
                    import re
                    word_match = re.match(r'^([a-z]+)', example)
                    if word_match:
                        flagged_words.add(word_match.group(1))

            console.print()
            console.print("[bold]Spaced repetition update (words):[/bold]")
            for target in target_words:
                word = target.get("word", "")
                if word:
                    was_correct = word.lower() not in flagged_words
                    update_word_after_practice(word, was_correct)
                    if was_correct:
                        console.print(f"  [green]✓[/green] '{word}' - correct! (interval increased)")
                    else:
                        console.print(f"  [red]✗[/red] '{word}' - needs more practice (interval reset)")

        console.print()
        console.print("[dim]─" * 40 + "[/dim]")

        # Drain any pending stdin
        import sys
        import select
        while select.select([sys.stdin], [], [], 0)[0]:
            sys.stdin.readline()

        action = Prompt.ask("Press Enter for next prompt, q to quit", default="", show_default=False)
        if action.lower() == "q":
            break


def show_practice_menu(Prompt):
    """Display submenu for practice categories."""
    categories = {
        "1": ("stress", "Stress - Word emphasis practice"),
        "2": ("intonation", "Intonation - Pitch patterns"),
        "3": ("rhythm", "Rhythm - Syllable timing"),
        "4": ("reductions", "Reductions - Schwa and weak forms"),
        "5": ("professional", "Professional - Business scenarios"),
        "6": ("passages", "Passages - Longer readings"),
        "7": ("random", "Random - Any category"),
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

    save = Prompt.ask("Save recording?", choices=["y", "n"], default="y") == "y"
    playback = Prompt.ask("Play back after?", choices=["y", "n"], default="y") == "y"

    cat_name = None if choice == "7" else categories[choice][0]

    # Practice loop - keep going until user quits
    while True:
        try:
            practice(category=cat_name, prompt_id=None, text=None, list_prompts=False, playback=playback, save=save)
        except SystemExit:
            pass  # Typer raises SystemExit on errors, ignore it

        console.print()
        console.print("[dim]─" * 40 + "[/dim]")

        # Drain any pending stdin (from orphaned input() in recording thread)
        import sys
        import select
        while select.select([sys.stdin], [], [], 0)[0]:
            sys.stdin.readline()

        action = Prompt.ask("Press Enter for next prompt, q to quit", default="", show_default=False)

        if action.lower() == "q":
            break


if __name__ == "__main__":
    app()
