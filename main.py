#!/usr/bin/env python3
"""Prosody Coach CLI - Improve your English pronunciation and speaking patterns."""

import typer
from rich.console import Console
from rich.panel import Panel
from pathlib import Path
from typing import Optional

from recorder import record_audio, save_recording, load_audio, get_duration, play_audio, play_tts
from analyzer import analyze_prosody, rhythm_npvi_target_for_type
from feedback import display_analysis, display_quick_feedback
from coach import analyze_parallel, display_coaching
from config import COACH_PROVIDER
from prompts import (
    get_prompt_by_id,
    get_prompts_by_category,
    get_all_categories,
    get_random_prompt,
    get_rhythm_drill,
    get_random_rhythm_drill,
)
from storage import (
    save_session, get_history, get_stats, get_best_and_worst, get_session,
    get_user_weaknesses, get_due_sounds, update_sound_after_practice,
    get_due_words, update_word_after_practice,
    get_rhythm_progress, set_rhythm_baseline, update_rhythm_progress,
    save_rhythm_drill_attempt, get_due_rhythm_drills, get_available_levels,
)

import re


def normalize_sound_name(sound: str) -> str:
    """
    Normalize a sound name for comparison by removing markdown formatting.

    Examples:
        '- **Consonant Clusters**' -> 'consonant clusters'
        '1. S-Clusters' -> 's-clusters'
        '- SOUND: /θ/' -> 'sound: /θ/'
    """
    s = sound.strip()
    # Remove leading dash/bullet and space
    s = re.sub(r'^[-•]\s*', '', s)
    # Remove leading numbers with dot or parenthesis
    s = re.sub(r'^\d+[.)]\s*', '', s)
    # Remove markdown bold markers
    s = s.replace('**', '')
    # Convert to lowercase and strip
    return s.lower().strip()


app = typer.Typer(
    name="prosody",
    help="Analyze and improve your English prosody (pitch, volume, tempo, rhythm, pauses).",
    add_completion=False,
)
local_app = typer.Typer(
    help="Configure and diagnose fully local AI coaching.",
    add_completion=False,
)
app.add_typer(local_app, name="local")
console = Console()


def normalize_provider(provider: str) -> str:
    """Normalize AI provider aliases for CLI options."""
    normalized = (provider or "gemini").strip().lower()
    aliases = {
        "gemini": "gemini",
        "google": "gemini",
        "local": "local",
        "llama": "local",
        "llamacpp": "local",
        "llama.cpp": "local",
    }
    if normalized not in aliases:
        raise typer.BadParameter("Provider must be 'gemini' or 'local'.")
    return aliases[normalized]


def run_coaching_provider(
    provider: str,
    audio_data,
    sample_rate: int,
    analysis,
    audio_path: Optional[Path] = None,
    expected_text: Optional[str] = None,
):
    """Run AI coaching through Gemini or the local provider."""
    provider = normalize_provider(provider)
    if provider == "local":
        from local_coach import analyze_with_local_coach

        return analyze_with_local_coach(
            audio_data=audio_data,
            sample_rate=sample_rate,
            prosody=analysis,
            audio_path=audio_path,
            expected_text=expected_text,
        )

    if expected_text:
        from coach import analyze_with_coach_practice

        return analyze_with_coach_practice(
            audio_data,
            sample_rate,
            analysis,
            expected_text,
        )

    from coach import analyze_with_coach

    return analyze_with_coach(audio_data, sample_rate, analysis)


def generate_tailored_prompt_for_provider(
    provider: str,
    weaknesses: dict,
    due_sounds: Optional[list[dict]] = None,
    due_words: Optional[list[dict]] = None,
) -> dict:
    """Generate tailored practice text through the selected AI provider."""
    provider = normalize_provider(provider)
    if provider == "local":
        from local_coach import generate_local_tailored_prompt

        return generate_local_tailored_prompt(
            weaknesses,
            due_sounds=due_sounds,
            due_words=due_words,
        )

    from coach import generate_tailored_prompt

    return generate_tailored_prompt(
        weaknesses,
        due_sounds=due_sounds,
        due_words=due_words,
    )


@local_app.command("setup")
def local_setup():
    """Show setup commands for whisper.cpp plus llama.cpp/Gemma."""
    setup_text = """
[bold]1. Install local runtimes[/bold]

  brew install whisper-cpp llama.cpp

[bold]2. Download models[/bold]

  mkdir -p "$HOME/models/whisper"
  curl -L -o "$HOME/models/whisper/ggml-base.en.bin" \\
    "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-base.en.bin"

  # llama.cpp can download a Gemma GGUF from Hugging Face on first run.
  # For a MacBook Pro M4 with 48 GB RAM, start with Gemma 4 E4B Q4_K_M.

[bold]3. Start the local LLM server[/bold]

  llama-server -hf ggml-org/gemma-4-E4B-it-GGUF:Q4_K_M \\
    --host 127.0.0.1 --port 8080 -ngl 99

[bold]4. (Recommended) Start whisper-server for fast transcription[/bold]

  # Keeps the Whisper model resident in RAM; ~4-10x faster than the CLI.
  whisper-server -m "$HOME/models/whisper/ggml-base.en.bin" \\
    --host 127.0.0.1 --port 9000 -t 8

[bold]5. Configure Prosody Coach[/bold]

  export PROSODY_COACH_PROVIDER=local
  export WHISPER_CPP_BIN="$(which whisper-cli)"
  export WHISPER_MODEL="$HOME/models/whisper/ggml-base.en.bin"
  export LOCAL_LLM_BASE_URL="http://127.0.0.1:8080/v1"
  export LOCAL_LLM_MODEL="ggml-org/gemma-4-E4B-it-GGUF:Q4_K_M"
  # Optional: route transcription through the running whisper-server
  export LOCAL_WHISPER_SERVER_URL="http://127.0.0.1:9000"

[bold]6. Test it[/bold]

  prosody local doctor
  prosody analyze --coach --provider local
  prosody practice --provider local
"""
    console.print()
    console.print(Panel(setup_text.strip(), title="[bold]Local AI Setup[/bold]", border_style="cyan"))


@local_app.command("config")
def local_config():
    """Print the current local provider configuration."""
    from rich.table import Table
    from local_coach import LocalCoachConfig

    config = LocalCoachConfig.from_env()
    table = Table(title="Local AI Configuration", border_style="blue")
    table.add_column("Setting", style="cyan")
    table.add_column("Value", style="white")
    table.add_row("PROSODY_COACH_PROVIDER", COACH_PROVIDER)
    table.add_row("WHISPER_CPP_BIN", config.whisper_bin)
    table.add_row("WHISPER_MODEL", config.whisper_model or "[dim]not set[/dim]")
    table.add_row("LOCAL_WHISPER_SERVER_URL", config.whisper_server_url or "[dim]not set (using CLI)[/dim]")
    table.add_row("LOCAL_LLM_BASE_URL", config.llm_base_url)
    table.add_row("LOCAL_LLM_MODEL", config.llm_model)
    table.add_row("LOCAL_LLM_TIMEOUT", str(config.llm_timeout))
    console.print()
    console.print(table)


@local_app.command("doctor")
def local_doctor():
    """Check whether the local AI provider is ready."""
    from rich.table import Table
    from local_coach import diagnose_local_setup

    checks = diagnose_local_setup()
    table = Table(title="Local AI Doctor", border_style="blue")
    table.add_column("Check", style="cyan")
    table.add_column("Status")
    table.add_column("Detail", style="white")
    table.add_column("Fix", style="dim")

    for check in checks:
        status = "[green]OK[/green]" if check.ok else "[red]Needs setup[/red]"
        table.add_row(check.label, status, check.detail, "" if check.ok else check.fix)

    console.print()
    console.print(table)
    if all(check.ok for check in checks):
        console.print("[green]Local AI coaching is ready.[/green]")
    else:
        console.print("[yellow]Run `prosody local setup` for the setup commands.[/yellow]")


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
        help="Enable AI coaching (transcription, grammar, tips).",
    ),
    provider: str = typer.Option(
        COACH_PROVIDER,
        "--provider",
        help="AI coaching provider: gemini or local.",
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
        provider = normalize_provider(provider)
        filepath = file
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

        # Initialize result variables
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
        analysis = None
        coaching = None

        if coach and provider == "gemini":
            # PARALLEL MODE: Run prosody + Gemini simultaneously with streaming
            from rich.live import Live
            from rich.text import Text

            # Track streaming progress
            stream_state = {"section": "Starting", "preview": "", "chunks": 0}

            def on_chunk(chunk, accumulated):
                stream_state["chunks"] += 1
                # Detect which section we're in
                sections = ["TRANSCRIPT", "GRAMMAR", "COACHING", "CONFIDENCE", "FLUENCY", "PROSODY", "OVERALL"]
                for section in reversed(sections):
                    if section in accumulated:
                        stream_state["section"] = section.capitalize()
                        break

                # Get transcript preview when available
                if "TRANSCRIPT:" in accumulated and not stream_state["preview"]:
                    lines = accumulated.split("\n")
                    for i, line in enumerate(lines):
                        if "TRANSCRIPT:" in line:
                            for next_line in lines[i+1:i+3]:
                                if next_line.strip() and not next_line.startswith("["):
                                    stream_state["preview"] = next_line.strip()[:50]
                                    break
                            break

            try:
                with Live(console=console, refresh_per_second=4, transient=True) as live:
                    import threading
                    result_holder = {"analysis": None, "coaching": None, "error": None}

                    def run_analysis():
                        try:
                            result_holder["analysis"], result_holder["coaching"] = analyze_parallel(
                                audio_data, sample_rate, on_chunk
                            )
                        except Exception as e:
                            result_holder["error"] = str(e)

                    thread = threading.Thread(target=run_analysis)
                    thread.start()

                    # Update display while waiting
                    spinner_frames = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
                    frame = 0
                    while thread.is_alive():
                        spinner = spinner_frames[frame % len(spinner_frames)]
                        text = Text()
                        text.append(f"  {spinner} ", style="cyan")
                        text.append("Analyzing", style="cyan bold")
                        text.append(f"  {stream_state['section']}", style="dim")
                        if stream_state["preview"]:
                            text.append(f'\n  "{stream_state["preview"]}..."', style="italic dim")
                        live.update(text)
                        frame += 1
                        thread.join(timeout=0.1)

                    thread.join()

                if result_holder["error"]:
                    raise Exception(result_holder["error"])

                analysis = result_holder["analysis"]
                coaching = result_holder["coaching"]

            except Exception as e:
                console.print(f"[yellow]AI coaching unavailable: {e}[/yellow]")
                # Fall back to local prosody only
                console.print("[dim]Falling back to local analysis...[/dim]")
                analysis = analyze_prosody(audio_data, sample_rate)
        elif coach and provider == "local":
            # LOCAL AI: prosody metrics first, then Whisper transcript + local LLM coaching.
            console.print("[dim]Analyzing prosody...[/dim]")
            analysis = analyze_prosody(audio_data, sample_rate, audio_path=filepath)
            try:
                console.print("[dim]Transcribing with whisper.cpp and coaching with local LLM...[/dim]")
                coaching = run_coaching_provider(
                    provider,
                    audio_data,
                    sample_rate,
                    analysis,
                    audio_path=filepath,
                )
            except Exception as e:
                console.print(f"[yellow]Local AI coaching unavailable: {e}[/yellow]")
        else:
            # LOCAL ONLY: Just prosody analysis
            console.print("[dim]Analyzing prosody...[/dim]")
            analysis = analyze_prosody(audio_data, sample_rate)

        # Display local prosody results
        if quick:
            display_quick_feedback(analysis)
        else:
            display_analysis(analysis)

        # Display AI coaching if available
        if coaching:
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

        # Playback
        if playback:
            console.print("[dim]Playing back your recording...[/dim]")
            play_audio(audio_data, sample_rate)

        # Save session
        save_session(
            analysis,
            mode="analyze",
            recording_path=filepath,
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
    provider: str = typer.Option(
        COACH_PROVIDER,
        "--provider",
        help="AI coaching provider: gemini or local.",
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
        provider = normalize_provider(provider)
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

        # Save recording (needed for vocalic nPVI alignment)
        filepath = None
        if save:
            filepath = save_recording(audio_data, sample_rate)
            console.print(f"[dim]Saved to: {filepath}[/dim]\n")

        # Analyze prosody (pass text and path for vocalic nPVI when available)
        console.print("[dim]Analyzing prosody...[/dim]")
        analysis = analyze_prosody(
            audio_data,
            sample_rate,
            expected_text=prompt_data["text"],
            audio_path=filepath,
        )
        display_analysis(analysis)

        # Start AI request in background while playing back
        import threading
        from coach import display_coaching

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
                coaching_result["coaching"] = run_coaching_provider(
                    provider,
                    audio_data,
                    sample_rate,
                    analysis,
                    audio_path=filepath,
                    expected_text=prompt_data["text"],
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
            recording_path=filepath,
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
    provider: str = typer.Option(
        COACH_PROVIDER,
        "--provider",
        help="AI coaching provider: gemini or local.",
    ),
):
    """
    Start a tailored training session based on your practice history.

    Analyzes your past sessions to identify weak areas and generates
    custom practice prompts targeting your specific needs.
    """
    from rich.prompt import Prompt
    from coach import display_coaching
    from recorder import play_tts

    provider = normalize_provider(provider)
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
            prompt_data = generate_tailored_prompt_for_provider(provider, weaknesses)
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

        # Save recording (needed for vocalic nPVI alignment)
        filepath = None
        if save:
            filepath = save_recording(audio_data, sample_rate)
            console.print(f"[dim]Saved to: {filepath}[/dim]\n")

        # Analyze prosody (pass text and path for vocalic nPVI when available)
        console.print("[dim]Analyzing prosody...[/dim]")
        analysis = analyze_prosody(
            audio_data,
            sample_rate,
            expected_text=prompt_data["text"],
            audio_path=filepath,
        )
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
                coaching_result["coaching"] = run_coaching_provider(
                    provider,
                    audio_data,
                    sample_rate,
                    analysis,
                    audio_path=filepath,
                    expected_text=prompt_data["text"],
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
            recording_path=filepath,
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
def rhythm(
    level: Optional[int] = typer.Option(
        None,
        "--level", "-l",
        help="Practice a specific level (1-6).",
    ),
    baseline: bool = typer.Option(
        False,
        "--baseline", "-b",
        help="Measure your starting nPVI.",
    ),
    status: bool = typer.Option(
        False,
        "--status", "-s",
        help="Show your rhythm training progress.",
    ),
    drill_id: Optional[str] = typer.Option(
        None,
        "--drill", "-d",
        help="Practice a specific drill by ID.",
    ),
    realtime: bool = typer.Option(
        False,
        "--realtime", "-r",
        help="Real-time mode with streaming AI feedback (experimental).",
    ),
):
    """
    Progressive rhythm training for stress-timed English.

    A structured 6-level program to improve your English rhythm
    from syllable-timed (Spanish-like) to stress-timed (English-like).

    Examples:
        prosody rhythm              # Continue at current level
        prosody rhythm --baseline   # Measure starting nPVI
        prosody rhythm --level 2    # Practice level 2
        prosody rhythm --status     # View progress
        prosody rhythm --realtime   # Real-time streaming mode
    """
    from rich.prompt import Prompt
    from feedback import (
        display_rhythm_progress,
        display_rhythm_feedback,
        display_rhythm_drill_intro,
        display_level_unlock,
    )
    from coach import (
        analyze_rhythm_with_coach,
        generate_targeted_drill,
        evaluate_mastery_with_ai,
    )
    from config import RHYTHM_LEVEL_CONFIG
    from storage import (
        track_rhythm_issue,
        mark_rhythm_issue_resolved,
        get_rhythm_issues,
        get_level_mastery_data,
        save_mastery_evaluation,
        should_evaluate_mastery,
    )

    # Handle real-time mode
    if realtime:
        import asyncio
        from realtime import run_realtime_rhythm_training

        # Determine level
        progress = get_rhythm_progress()
        current_level = progress.get("current_level", 1)
        practice_level = level if level else current_level

        try:
            asyncio.run(run_realtime_rhythm_training(practice_level, console))
        except KeyboardInterrupt:
            console.print("\n[yellow]Real-time session cancelled.[/yellow]")
        except Exception as e:
            console.print(f"\n[red]Real-time mode error: {e}[/red]")
            console.print("[dim]Try standard mode: prosody rhythm[/dim]")
        return

    try:
        # Status mode - show progress
        if status:
            progress = get_rhythm_progress()
            display_rhythm_progress(progress)
            return

        # Baseline mode - measure starting nPVI
        if baseline:
            console.print()
            console.print(Panel(
                "[bold]Baseline Measurement[/bold]\n\n"
                "We'll measure your current rhythm pattern (nPVI).\n"
                "Read the following sentence naturally - don't try to change anything.\n\n"
                "[dim]This establishes your starting point for tracking progress.[/dim]",
                border_style="cyan",
            ))

            baseline_text = "I want to go to the store to get some milk and bread for dinner tonight."

            console.print()
            console.print(Panel(
                f"[bold white]{baseline_text}[/bold white]",
                title="[bold green]READ THIS[/bold green]",
                border_style="green",
                padding=(1, 2),
            ))

            console.print()
            console.print("[dim]Playing reference audio...[/dim]")
            play_tts(baseline_text)

            console.print()
            console.print(Panel(
                "[bold]Press Enter to stop recording[/bold]",
                title="[bold blue]Recording[/bold blue]",
                border_style="blue",
            ))

            audio_data, sample_rate = record_audio()
            duration = get_duration(audio_data, sample_rate)
            console.print(f"[green]Done![/green] ({duration:.1f} seconds)\n")

            if duration < 2.0:
                console.print("[red]Recording too short. Please read the full sentence.[/red]")
                raise typer.Exit(1)

            # Analyze prosody (text available but no saved file for alignment)
            console.print("[dim]Analyzing prosody...[/dim]")
            analysis = analyze_prosody(
                audio_data,
                sample_rate,
                expected_text=baseline_text,
            )

            # Set baseline
            npvi = analysis.rhythm.pvi
            set_rhythm_baseline(npvi)

            console.print()
            console.print(Panel(
                f"[bold]Your baseline nPVI:[/bold] [cyan]{npvi:.0f}[/cyan]\n\n"
                f"[dim]Spanish typical: ~40 | English target: ~60[/dim]\n\n"
                f"{'[yellow]Starting point identified. Lets work on improving your rhythm![/yellow]' if npvi < 50 else '[green]Good starting point! Lets refine your rhythm further.[/green]'}",
                title="[bold]Baseline Established[/bold]",
                border_style="cyan",
            ))

            # Show next steps
            console.print()
            console.print("[bold]Next steps:[/bold]")
            console.print("  • Run [cyan]prosody rhythm[/cyan] to start Level 1 training")
            console.print("  • Run [cyan]prosody rhythm --status[/cyan] to track progress")
            console.print()
            return

        # Get current progress
        progress = get_rhythm_progress()
        current_level = progress.get("current_level", 1)
        available_levels = get_available_levels()

        # Determine which level to practice
        practice_level = level if level else current_level

        # Validate level selection
        if practice_level not in available_levels:
            if practice_level > max(available_levels):
                console.print(f"[yellow]Level {practice_level} is locked. Complete Level {max(available_levels)} first.[/yellow]")
                practice_level = max(available_levels)
            else:
                console.print(f"[red]Invalid level: {practice_level}. Available: {available_levels}[/red]")
                raise typer.Exit(1)

        # Check if we need baseline
        if not progress.get("npvi_baseline"):
            console.print()
            console.print("[yellow]No baseline measurement found.[/yellow]")
            console.print("[dim]Run 'prosody rhythm --baseline' first to measure your starting nPVI.[/dim]")
            console.print()
            raise typer.Exit(0)

        level_config = RHYTHM_LEVEL_CONFIG.get(practice_level, {})

        # Show level intro
        console.print()
        console.print(Panel(
            f"[bold]Level {practice_level}: {level_config.get('name', '')}[/bold]\n\n"
            f"{level_config.get('description', '')}\n\n"
            f"[dim]nPVI Target: {level_config.get('npvi_target', 50)}+ | "
            f"Min Rhythm Score: {level_config.get('min_rhythm_score', 5)}/10 | "
            f"Passes needed: {level_config.get('consecutive_passes', 3)}[/dim]",
            border_style="cyan",
        ))

        # Get drill with smart selection
        if drill_id:
            drill = get_rhythm_drill(drill_id)
            if not drill:
                console.print(f"[red]Drill '{drill_id}' not found.[/red]")
                raise typer.Exit(1)
        else:
            drill = None

            # Priority 1: Check for unresolved issues and generate targeted drill
            unresolved_issues = get_rhythm_issues(level=practice_level, unresolved_only=True)
            if unresolved_issues:
                console.print("[dim]Found problem areas - generating targeted practice...[/dim]")
                try:
                    drill = generate_targeted_drill(
                        practice_level,
                        unresolved_issues,
                        []  # existing drills
                    )
                    if drill:
                        console.print("[cyan]AI-generated drill targeting your specific issues[/cyan]")
                except Exception:
                    pass  # Fall through to standard drills

            # Priority 2: Check for due drills (spaced repetition)
            if not drill:
                due_drills = get_due_rhythm_drills(level=practice_level, limit=1)
                if due_drills:
                    drill = get_rhythm_drill(due_drills[0]["drill_id"])
                    console.print("[dim]Reviewing a drill that's due for practice...[/dim]")

            # Priority 3: Get random drill from level
            if not drill:
                drill = get_random_rhythm_drill(practice_level)

        if not drill:
            console.print(f"[red]No drills available for Level {practice_level}.[/red]")
            raise typer.Exit(1)

        # Training loop
        while True:
            # Display drill (IPA shows pronunciation - no TTS to avoid bad rhythm model)
            display_rhythm_drill_intro(drill, practice_level)

            # Record
            console.print()
            console.print(Panel(
                "[bold]Press Enter to stop recording[/bold]",
                title="[bold blue]Recording[/bold blue]",
                border_style="blue",
            ))

            audio_data, sample_rate = record_audio()
            duration = get_duration(audio_data, sample_rate)
            console.print(f"[green]Done![/green] ({duration:.1f} seconds)\n")

            if duration < 1.0:
                console.print("[red]Recording too short. Please try again.[/red]")
                continue

            # Analyze prosody (text available but no saved file for alignment)
            console.print("[dim]Analyzing prosody...[/dim]")
            analysis = analyze_prosody(
                audio_data,
                sample_rate,
                expected_text=drill["text"],
            )

            # Start AI rhythm coaching in background
            import threading
            rhythm_coaching_result = {"result": None, "error": None}

            def fetch_rhythm_coaching():
                try:
                    rhythm_coaching_result["result"] = analyze_rhythm_with_coach(
                        audio_data, sample_rate, analysis, drill["text"],
                        practice_level, drill.get("focus", ""), drill.get("technique", "")
                    )
                except Exception as e:
                    rhythm_coaching_result["error"] = str(e)

            ai_thread = threading.Thread(target=fetch_rhythm_coaching)
            ai_thread.start()

            # Playback while AI processes
            console.print("[dim]Playing back (AI processing in background)...[/dim]")
            play_audio(audio_data, sample_rate)

            # Wait for AI to finish if still running
            if ai_thread.is_alive():
                console.print("[dim]Waiting for AI feedback...[/dim]")
            ai_thread.join()

            # Get result
            if rhythm_coaching_result["result"]:
                rhythm_result = rhythm_coaching_result["result"]
            elif rhythm_coaching_result["error"]:
                console.print(f"[yellow]AI feedback unavailable: {rhythm_coaching_result['error']}[/yellow]")
                rhythm_result = None
            else:
                rhythm_result = None

            # Determine pass/fail
            npvi = analysis.rhythm.pvi
            rhythm_score = analysis.rhythm.score
            npvi_target = level_config.get("npvi_target", 45)
            min_rhythm = level_config.get("min_rhythm_score", 5)

            # Use AI judgment if available, otherwise use measured values
            if rhythm_result:
                passed = rhythm_result.level_passed
                ai_rhythm_score = rhythm_result.rhythm_score
            else:
                pvi_type = getattr(analysis.rhythm, "pvi_type", "vocalic")
                adjusted_npvi_target = rhythm_npvi_target_for_type(npvi_target, pvi_type)
                passed = rhythm_score >= min_rhythm and npvi >= adjusted_npvi_target
                ai_rhythm_score = rhythm_score

            # Track issues from AI feedback
            if rhythm_result and rhythm_result.word_stress_issues:
                for issue in rhythm_result.word_stress_issues:
                    track_rhythm_issue(
                        issue_type="word_stress",
                        level=practice_level,
                        word=issue.get("word"),
                        expected=issue.get("expected"),
                        heard=issue.get("heard"),
                    )

            # Mark issues as resolved if user passed with good stress
            if rhythm_result and passed and rhythm_result.stress_correct:
                # Any words in the drill that were previously problematic are now resolved
                drill_words = drill.get("text", "").lower().split()
                for word in drill_words:
                    # Only mark resolved if it was actually a tracked issue
                    mark_rhythm_issue_resolved(word=word.strip(",.!?"), level=practice_level)

            # Get current progress BEFORE updating (to show pre-attempt state)
            current_progress = get_rhythm_progress()
            levels_data = current_progress.get("levels", {})
            level_progress_data = levels_data.get(practice_level, {})
            consecutive_before = level_progress_data.get("consecutive_passes", 0)
            required_passes = level_config.get("consecutive_passes", 3)

            # If passed, the display should show the NEW progress (increment by 1)
            consecutive_for_display = consecutive_before + 1 if passed else 0
            progress_tuple = (consecutive_for_display, required_passes)

            # Display feedback with new hierarchy: VERDICT → ACTION → DETAILS
            show_details = False  # Will be toggled with 'd' key

            if rhythm_result:
                display_rhythm_feedback(
                    rhythm_result, analysis, practice_level, passed,
                    progress=progress_tuple, show_details=show_details
                )
            else:
                # Basic feedback without AI (fallback)
                console.print()
                progress_visual = ""
                for i in range(required_passes):
                    if i < consecutive_for_display:
                        progress_visual += "[green]✓[/green] "
                    else:
                        progress_visual += "[dim]○[/dim] "
                progress_visual = progress_visual.strip()

                if passed:
                    console.print(Panel(
                        f"[bold green]✓ PASS[/bold green]    {rhythm_score}/10    Progress: {progress_visual}\n"
                        f"[dim]Level {practice_level}[/dim]",
                        border_style="green",
                        padding=(0, 2),
                    ))
                else:
                    console.print(Panel(
                        f"[bold yellow]○ KEEP PRACTICING[/bold yellow]    {rhythm_score}/10    Progress: {progress_visual}\n"
                        f"[dim]Level {practice_level}[/dim]",
                        border_style="yellow",
                        padding=(0, 2),
                    ))
                pvi_type = getattr(analysis.rhythm, "pvi_type", "vocalic")
                adjusted_npvi_target = rhythm_npvi_target_for_type(npvi_target, pvi_type)
                metric_label = "IOI nPVI" if pvi_type == "ioi" else "vocalic nPVI"
                console.print(f"\n[dim]{metric_label}: {npvi:.0f} (target: {adjusted_npvi_target:.0f}+)[/dim]")

            # Update progress in database
            progress_update = update_rhythm_progress(
                practice_level, npvi, ai_rhythm_score, passed
            )

            # Save drill attempt
            save_rhythm_drill_attempt(
                drill["id"], practice_level, npvi, ai_rhythm_score, passed
            )

            # AI Mastery Evaluation (dynamic level advancement)
            if should_evaluate_mastery(practice_level) and practice_level < 6:
                console.print("[dim]Evaluating mastery...[/dim]")
                try:
                    mastery_data = get_level_mastery_data(practice_level)
                    mastery_result = evaluate_mastery_with_ai(mastery_data)

                    # Save evaluation
                    save_mastery_evaluation(
                        level=practice_level,
                        fundamentals_solid=mastery_result.fundamentals_solid,
                        issues_resolved=mastery_data["resolved_issues_count"],
                        issues_remaining=len(mastery_data["unresolved_issues"]),
                        unique_drills_passed=mastery_data["unique_drills_passed"],
                        recommendation=mastery_result.recommendation,
                        reasoning=mastery_result.reasoning,
                        npvi_avg=mastery_data["avg_npvi"],
                        rhythm_avg=mastery_data["avg_rhythm_score"],
                    )

                    # Show AI recommendation
                    if mastery_result.recommendation == "advance":
                        console.print()
                        console.print(Panel(
                            f"[bold green]🎓 AI RECOMMENDS ADVANCEMENT[/bold green]\n\n"
                            f"{mastery_result.reasoning}\n\n"
                            f"[dim]Confidence: {mastery_result.confidence:.0%}[/dim]",
                            border_style="green",
                        ))
                        # Force level unlock if AI recommends and not already unlocked
                        if not progress_update.get("next_level_unlocked"):
                            from storage import get_db, init_db
                            from datetime import datetime
                            init_db()
                            with get_db() as db:
                                db.execute(
                                    f"UPDATE rhythm_progress SET current_level = ?, level_{practice_level + 1}_unlocked_at = ?",
                                    (practice_level + 1, datetime.now().isoformat())
                                )
                            display_level_unlock(practice_level + 1)
                            progress_update["next_level_unlocked"] = True
                    elif mastery_result.focus_areas:
                        console.print()
                        console.print(Panel(
                            f"[bold yellow]📋 FOCUS AREAS[/bold yellow]\n\n"
                            f"{chr(10).join('• ' + area for area in mastery_result.focus_areas[:3])}\n\n"
                            f"[dim]{mastery_result.reasoning}[/dim]",
                            border_style="yellow",
                        ))
                except Exception:
                    # AI evaluation failed, fall back to standard progress
                    pass

            # Check for level unlock (standard path)
            if progress_update.get("next_level_unlocked"):
                display_level_unlock(practice_level + 1)

            # Next prompt (progress now shown in feedback header)
            console.print()
            console.print("[dim]─" * 40 + "[/dim]")

            # Flush any pending stdin (fixes double-enter issue on macOS)
            import sys
            import termios
            try:
                termios.tcflush(sys.stdin, termios.TCIFLUSH)
            except Exception:
                pass  # Ignore if not a terminal

            action = Prompt.ask("[Enter] next  [d] details  [q] quit", default="", show_default=False)

            if action.lower() == "q":
                # Show final progress
                final_progress = get_rhythm_progress()
                display_rhythm_progress(final_progress)
                break

            if action.lower() == "d":
                # Re-display with full details
                if rhythm_result:
                    console.print()  # Clear some space
                    display_rhythm_feedback(
                        rhythm_result, analysis, practice_level, passed,
                        progress=progress_tuple, show_details=True
                    )
                    # Wait for user to continue after viewing details
                    Prompt.ask("[Enter] next  [q] quit", default="", show_default=False)
                continue  # Don't get a new drill, let them see the current one

            # Get next drill with smart selection
            drill = None

            # Priority 1: Check for unresolved issues and generate targeted drill
            unresolved_issues = get_rhythm_issues(level=practice_level, unresolved_only=True)
            if unresolved_issues:
                try:
                    drill = generate_targeted_drill(
                        practice_level,
                        unresolved_issues,
                        []
                    )
                    if drill:
                        console.print("[cyan]AI-generated drill targeting your issues[/cyan]")
                except Exception:
                    pass

            # Priority 2: Check for due drills (spaced repetition)
            if not drill:
                due_drills = get_due_rhythm_drills(level=practice_level, limit=1)
                if due_drills:
                    drill = get_rhythm_drill(due_drills[0]["drill_id"])

            # Priority 3: Get random drill from level
            if not drill:
                drill = get_random_rhythm_drill(practice_level)

            if not drill:
                console.print(f"[yellow]No more drills available for Level {practice_level}.[/yellow]")
                break

    except KeyboardInterrupt:
        console.print("\n[yellow]Rhythm training cancelled.[/yellow]")
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
    if session.get("recording_path"):
        console.print(f"[bold]Recording:[/bold] {session['recording_path']}")

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
            console.print("\n[yellow]Trend: Steady[/yellow]")

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
    from storage import get_user_weaknesses

    menu_options = {
        "1": ("analyze", "Record and analyze your speech"),
        "2": ("practice", "Practice with guided prompts"),
        "3": ("train", "Tailored training (based on your history)"),
        "4": ("rhythm", "Rhythm training (stress-timed English)"),
        "5": ("history", "View your practice history"),
        "6": ("progress", "View your progress stats"),
        "7": ("info", "Learn about prosody components"),
        "8": ("tips", "Tips for Spanish speakers"),
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

        # Check for due words (mispronounced words)
        due_words = get_due_words(limit=10)

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

        # Get rhythm progress for menu display
        rhythm_progress = get_rhythm_progress()
        rhythm_level = rhythm_progress.get("current_level", 1)
        rhythm_has_baseline = rhythm_progress.get("npvi_baseline") is not None

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
            elif key == "4":
                # Rhythm training with level indicator
                if rhythm_has_baseline:
                    console.print(f"  [bold magenta]{key}[/bold magenta]  [magenta]{desc}[/magenta] L{rhythm_level}")
                else:
                    console.print(f"  [bold cyan]{key}[/bold cyan]  {desc} [dim](new)[/dim]")
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
            run_rhythm_training(Prompt, rhythm_progress)
        elif choice == "5":
            history(limit=10, mode=None)
        elif choice == "6":
            progress()
        elif choice == "7":
            info()
        elif choice == "8":
            tips()


def run_tailored_training(Prompt, weaknesses: dict):
    """Run tailored training session based on user's weaknesses."""
    from coach import display_coaching
    from analyzer import analyze_prosody
    from recorder import record_audio, play_audio, get_duration, save_recording, play_tts
    from storage import save_session

    provider = normalize_provider(COACH_PROVIDER)

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
            prompt_data = generate_tailored_prompt_for_provider(
                provider,
                weaknesses,
                due_sounds=due_sounds,
                due_words=due_words,
            )
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

        # Save recording (needed for vocalic nPVI alignment)
        filepath = None
        if save:
            filepath = save_recording(audio_data, sample_rate)
            console.print(f"[dim]Saved to: {filepath}[/dim]\n")

        # Analyze prosody (pass text and path for vocalic nPVI when available)
        console.print("[dim]Analyzing prosody...[/dim]")
        analysis = analyze_prosody(
            audio_data,
            sample_rate,
            expected_text=prompt_data["text"],
            audio_path=filepath,
        )
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
                coaching_result["coaching"] = run_coaching_provider(
                    provider,
                    audio_data,
                    sample_rate,
                    analysis,
                    audio_path=filepath,
                    expected_text=prompt_data["text"],
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
            recording_path=filepath,
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
            # Get sounds that were flagged as issues in this session (normalized for comparison)
            flagged_sounds = set()
            if pronunciation_issues:
                for issue in pronunciation_issues:
                    flagged_sounds.add(normalize_sound_name(issue.get("sound", "")))

            console.print()
            console.print("[bold]Spaced repetition update (sounds):[/bold]")
            # Update each target sound based on whether it was flagged
            for target in target_sounds:
                sound = target.get("sound", "")
                if sound:
                    # Sound was correct if its normalized name wasn't flagged as an issue
                    normalized_sound = normalize_sound_name(sound)
                    was_correct = normalized_sound not in flagged_sounds
                    update_sound_after_practice(sound, was_correct)
                    display_name = normalized_sound if normalized_sound != sound.lower() else sound
                    if was_correct:
                        console.print(f"  [green]✓[/green] '{display_name}' - correct! (interval increased)")
                    else:
                        console.print(f"  [red]✗[/red] '{display_name}' - needs more practice (interval reset)")

        # Update spaced repetition for target words
        target_words = prompt_data.get("target_words", [])
        if target_words:
            # Get words that were mispronounced in this session
            flagged_words = set()
            if pronunciation_issues:
                for issue in pronunciation_issues:
                    example = issue.get("example", "").lower()
                    # Extract word from example
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


def run_rhythm_training(Prompt, rhythm_progress: dict):
    """Run rhythm training session from the interactive menu."""
    from feedback import display_rhythm_progress

    # Check if baseline is set
    if not rhythm_progress.get("npvi_baseline"):
        console.print()
        console.print(Panel(
            "[bold]Welcome to Rhythm Training![/bold]\n\n"
            "This program will help you develop English stress-timed rhythm.\n\n"
            "[yellow]First, let's measure your baseline nPVI to track progress.[/yellow]",
            border_style="cyan",
        ))

        console.print()
        start = Prompt.ask("Start baseline measurement?", choices=["y", "n"], default="y")

        if start == "y":
            rhythm(level=None, baseline=True, status=False, drill_id=None, realtime=False)

            # After baseline, offer to start training
            console.print()
            continue_training = Prompt.ask(
                "Start Level 1 training now?",
                choices=["y", "n"],
                default="y"
            )
            if continue_training == "y":
                rhythm(level=None, baseline=False, status=False, drill_id=None, realtime=False)
        else:
            console.print("[dim]You can run 'prosody rhythm --baseline' when ready.[/dim]")
        return

    # Show current progress
    display_rhythm_progress(rhythm_progress)

    console.print()
    console.print("[bold]Options:[/bold]")
    console.print("  [bold cyan]1[/bold cyan]  Continue training at current level")
    console.print("  [bold cyan]2[/bold cyan]  View progress")
    console.print("  [bold cyan]b[/bold cyan]  [dim]Back to main menu[/dim]")
    console.print()

    choice = Prompt.ask(
        "[bold]Select an option[/bold]",
        choices=["1", "2", "b"],
        default="1",
        show_choices=False,
    )

    if choice == "1":
        rhythm(level=None, baseline=False, status=False, drill_id=None, realtime=False)
    elif choice == "2":
        rhythm(level=None, baseline=False, status=True, drill_id=None, realtime=False)
    # "b" just returns to main menu


@app.command()
def framework(
    framework_id: str = typer.Argument(..., help="Framework id: star, prep, scqa, sbi, story."),
    prompt_id: Optional[str] = typer.Option(None, "--prompt-id", "-p", help="Specific prompt id; default is the first prompt."),
    provider: str = typer.Option(COACH_PROVIDER, "--provider", help="'gemini' or 'local'."),
    save: bool = typer.Option(True, "--save/--no-save", help="Persist the attempt to history."),
):
    """Record a spoken answer and score it against a communication framework.

    Examples:
      prosody framework star
      prosody framework prep --prompt-id prep_2
      prosody framework story --provider local
    """
    from frameworks import FRAMEWORKS, get_framework, get_prompt
    from coach_pipeline import analyze_framework_session
    from storage import save_framework_attempt
    from recorder import record_audio, save_recording
    from config import RECORDINGS_DIR

    fw = get_framework(framework_id)
    if fw is None:
        console.print(f"[red]Unknown framework: {framework_id}[/red]")
        console.print(f"Available: {', '.join(FRAMEWORKS.keys())}")
        raise typer.Exit(code=1)

    prompt = get_prompt(framework_id, prompt_id) if prompt_id else None
    if prompt is None:
        prompt = fw["prompts"][0]

    console.print(Panel(
        f"[bold]{fw['name']}[/bold] — {fw['description']}\n\n"
        f"[italic]{prompt['text']}[/italic]\n\n"
        f"Structure: {' → '.join(s['name'] for s in fw['slots'])}\n"
        f"Target: {fw['target_duration_seconds'][0]}–{fw['target_duration_seconds'][1]}s",
        title="Frameworks practice",
        border_style="cyan",
    ))

    audio_data, sample_rate = record_audio()
    if audio_data is None or len(audio_data) == 0:
        console.print("[red]No audio recorded.[/red]")
        raise typer.Exit(code=1)

    wav_path = None
    if save:
        from uuid import uuid4
        wav_path = Path(RECORDINGS_DIR) / f"{uuid4().hex}.wav"
        save_recording(audio_data, sample_rate, wav_path)

    console.print("[muted]Analyzing — this takes a few seconds…[/muted]")
    result = analyze_framework_session(
        audio_data, sample_rate,
        framework=fw, prompt=prompt,
        provider=provider, audio_path=wav_path,
    )

    console.print(Panel(
        f"Structure score: [bold]{result.overall_score:.1f}/10[/bold] "
        f"{'[green]PASS[/green]' if result.passed else '[yellow]Keep practicing[/yellow]'}\n"
        f"Provider: {result.provider}  ·  status: {result.status}"
        + (f"  ·  error: {result.error}" if result.error else ""),
        title="Result",
        border_style="green" if result.passed else "yellow",
    ))

    if result.structure:
        for slot_def in fw["slots"]:
            s = result.structure.slot(slot_def["id"])
            icon = "✓" if s and s.present == "yes" else ("~" if s and s.present == "partial" else "✗")
            quality = f"{s.quality}/5" if s else "0/5"
            note = s.note if s else ""
            console.print(f"  {icon} [bold]{slot_def['name']}[/bold] ({quality}): {note}")
        if result.structure.overall_note:
            console.print(f"\n[italic]{result.structure.overall_note}[/italic]")
        if result.structure.cultural_note:
            console.print(f"[cyan]Cultural note:[/cyan] {result.structure.cultural_note}")
        if result.structure.grammar_notes:
            console.print("\n[cyan]Language flags:[/cyan]")
            for note in result.structure.grammar_notes:
                console.print(f"  - {note}")

    if save and result.structure is not None:
        save_framework_attempt(
            analysis=result.analysis,
            framework_id=framework_id,
            prompt_id=prompt["id"],
            structure=result.structure,
            per_slot_prosody=result.per_slot_prosody,
            overall_score=result.overall_score,
            passed=result.passed,
            transcript=result.transcript.text if result.transcript else None,
            recording_path=str(wav_path) if wav_path else None,
            coach_provider=result.provider,
            coach_status=result.status,
            coach_error=result.error,
        )
        console.print("\n[muted]Saved to history.[/muted]")


@app.command()
def serve(
    port: int = typer.Option(7860, "--port", help="HTTP port."),
    no_browser: bool = typer.Option(False, "--no-browser", help="Skip auto-opening the browser."),
    reload: bool = typer.Option(False, "--reload", help="Enable uvicorn autoreload (dev)."),
):
    """Start the web UI on http://127.0.0.1:<port>.

    Bind address is hardcoded to 127.0.0.1 — Prosody Coach is a single-user
    local tool. There is intentionally no --host flag; if you need to expose
    it, edit this command and accept responsibility for the security model
    (no auth, no CSRF, API keys readable from the page).
    """
    import threading
    import webbrowser

    import uvicorn

    host = "127.0.0.1"
    if not no_browser:
        url = f"http://{host}:{port}"
        threading.Timer(0.5, lambda: webbrowser.open(url)).start()

    uvicorn.run(
        "web.app:create_app",
        host=host,
        port=port,
        factory=True,
        reload=reload,
    )


if __name__ == "__main__":
    app()
