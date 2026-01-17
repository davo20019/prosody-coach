"""Feedback display module for prosody analysis results."""

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich.live import Live
from rich.layout import Layout
from rich import box
from typing import Optional

from analyzer import ProsodyAnalysis


console = Console()


def score_to_bar(score: int, width: int = 10) -> str:
    """Convert score (1-10) to a progress bar."""
    filled = int(score * width / 10)
    empty = width - filled
    return "[green]" + "" * filled + "[/green][dim]" + "" * empty + "[/dim]"


def score_to_color(score: int) -> str:
    """Get color based on score."""
    if score >= 8:
        return "green"
    elif score >= 5:
        return "yellow"
    else:
        return "red"


def display_analysis(analysis: ProsodyAnalysis) -> None:
    """Display complete prosody analysis with rich formatting."""

    # Header
    console.print()
    console.print(
        Panel(
            f"[bold]Duration:[/bold] {analysis.duration:.1f} seconds",
            title="[bold blue]PROSODY ANALYSIS[/bold blue]",
            border_style="blue",
        )
    )
    console.print()

    # Main scores table
    table = Table(
        box=box.ROUNDED,
        show_header=True,
        header_style="bold cyan",
        expand=True,
    )
    table.add_column("Component", style="bold", width=12)
    table.add_column("Score", justify="center", width=20)
    table.add_column("Details", width=35)
    table.add_column("Feedback", width=45)

    # Pitch row
    pitch = analysis.pitch
    pitch_color = score_to_color(pitch.score)
    table.add_row(
        "Pitch",
        f"{score_to_bar(pitch.score)}  [{pitch_color}]{pitch.score}/10[/{pitch_color}]",
        f"Range: {pitch.min_hz:.0f}-{pitch.max_hz:.0f} Hz\nVariation: {pitch.range_hz:.0f} Hz",
        pitch.feedback,
    )

    # Volume row
    volume = analysis.volume
    volume_color = score_to_color(volume.score)
    table.add_row(
        "Volume",
        f"{score_to_bar(volume.score)}  [{volume_color}]{volume.score}/10[/{volume_color}]",
        f"Range: {volume.dynamic_range_db:.1f} dB\nStress contrast: {volume.stress_contrast_db:.1f} dB",
        volume.feedback,
    )

    # Tempo row
    tempo = analysis.tempo
    tempo_color = score_to_color(tempo.score)
    table.add_row(
        "Tempo",
        f"{score_to_bar(tempo.score)}  [{tempo_color}]{tempo.score}/10[/{tempo_color}]",
        f"Speed: {tempo.estimated_wpm:.0f} WPM\nVariation: {tempo.variation_percent:.0f}%",
        tempo.feedback,
    )

    # Rhythm row
    rhythm = analysis.rhythm
    rhythm_color = score_to_color(rhythm.score)
    rhythm_type = "Syllable-timed" if rhythm.is_syllable_timed else "Stress-timed"
    table.add_row(
        "Rhythm",
        f"{score_to_bar(rhythm.score)}  [{rhythm_color}]{rhythm.score}/10[/{rhythm_color}]",
        f"PVI: {rhythm.pvi:.0f}\nType: {rhythm_type}",
        rhythm.feedback,
    )

    # Pauses row
    pauses = analysis.pauses
    pauses_color = score_to_color(pauses.score)
    table.add_row(
        "Pauses",
        f"{score_to_bar(pauses.score)}  [{pauses_color}]{pauses.score}/10[/{pauses_color}]",
        f"Count: {pauses.pause_count}\nAvg duration: {pauses.avg_pause_duration:.1f}s",
        pauses.feedback,
    )

    console.print(table)

    # Overall score
    overall_color = score_to_color(int(analysis.overall_score))
    console.print()
    console.print(
        Panel(
            f"[bold {overall_color}]{analysis.overall_score:.1f}/10[/bold {overall_color}]",
            title="[bold]Overall Score[/bold]",
            border_style=overall_color,
            width=30,
        ),
        justify="center",
    )

    # Top tip based on lowest score
    lowest = min(
        [
            (pitch.score, "pitch", "Try raising pitch on emphasized words and letting it fall naturally at sentence ends."),
            (volume.score, "volume", "Speak louder on key words (nouns, verbs, adjectives) and softer on function words."),
            (tempo.score, "tempo", "Slow down before important points, speed up on less critical information."),
            (rhythm.score, "rhythm", "Reduce unstressed syllables: 'comfortable' -> 'COMF-ter-ble', not 'com-for-ta-ble'."),
            (pauses.score, "pauses", "Add a brief pause before delivering key information to create anticipation."),
        ],
        key=lambda x: x[0],
    )

    console.print()
    console.print(
        Panel(
            f"[bold]Focus on {lowest[1]}:[/bold] {lowest[2]}",
            title="[bold yellow]Top Tip[/bold yellow]",
            border_style="yellow",
        )
    )
    console.print()


def display_quick_feedback(analysis: ProsodyAnalysis) -> None:
    """Display a brief summary of the analysis."""
    overall_color = score_to_color(int(analysis.overall_score))

    console.print()
    console.print(f"[bold]Overall:[/bold] [{overall_color}]{analysis.overall_score:.1f}/10[/{overall_color}]")
    console.print(
        f"Pitch: {analysis.pitch.score}/10 | "
        f"Volume: {analysis.volume.score}/10 | "
        f"Tempo: {analysis.tempo.score}/10 | "
        f"Rhythm: {analysis.rhythm.score}/10 | "
        f"Pauses: {analysis.pauses.score}/10"
    )
    console.print()


def display_comparison(analysis1: ProsodyAnalysis, analysis2: ProsodyAnalysis, label1: str = "Recording 1", label2: str = "Recording 2") -> None:
    """Display side-by-side comparison of two analyses."""
    console.print()
    console.print(Panel("[bold]COMPARISON[/bold]", border_style="blue"))

    table = Table(box=box.ROUNDED, show_header=True, header_style="bold cyan")
    table.add_column("Component", style="bold", width=12)
    table.add_column(label1, justify="center", width=20)
    table.add_column(label2, justify="center", width=20)
    table.add_column("Difference", justify="center", width=15)

    components = [
        ("Pitch", analysis1.pitch.score, analysis2.pitch.score),
        ("Volume", analysis1.volume.score, analysis2.volume.score),
        ("Tempo", analysis1.tempo.score, analysis2.tempo.score),
        ("Rhythm", analysis1.rhythm.score, analysis2.rhythm.score),
        ("Pauses", analysis1.pauses.score, analysis2.pauses.score),
        ("Overall", analysis1.overall_score, analysis2.overall_score),
    ]

    for name, score1, score2 in components:
        diff = score2 - score1
        if diff > 0:
            diff_str = f"[green]+{diff:.1f}[/green]"
        elif diff < 0:
            diff_str = f"[red]{diff:.1f}[/red]"
        else:
            diff_str = "[dim]0[/dim]"

        table.add_row(
            name,
            f"{score_to_bar(int(score1))} {score1:.1f}",
            f"{score_to_bar(int(score2))} {score2:.1f}",
            diff_str,
        )

    console.print(table)
    console.print()


# =============================================================================
# Rhythm Training Display Functions
# =============================================================================

def display_rhythm_progress(progress: dict) -> None:
    """Display rhythm training progress with level progress bars and nPVI trend."""
    from config import RHYTHM_LEVEL_CONFIG

    console.print()
    console.print(Panel(
        "[bold]Rhythm Training Progress[/bold]",
        border_style="cyan",
    ))

    # nPVI progress
    npvi_baseline = progress.get("npvi_baseline")
    npvi_current = progress.get("npvi_current")

    if npvi_baseline and npvi_current:
        npvi_change = npvi_current - npvi_baseline
        change_color = "green" if npvi_change >= 0 else "red"
        change_str = f"+{npvi_change:.0f}" if npvi_change >= 0 else f"{npvi_change:.0f}"

        # nPVI bar (target is 60, starting at 40)
        npvi_normalized = min(100, max(0, (npvi_current - 35) / 30 * 100))
        npvi_bar_width = 20
        filled = int(npvi_normalized * npvi_bar_width / 100)
        empty = npvi_bar_width - filled

        console.print()
        console.print(f"[bold]nPVI:[/bold] {npvi_current:.0f} [{change_color}]({change_str})[/{change_color}]")
        console.print(f"  [dim]35[/dim] [green]{'█' * filled}[/green][dim]{'░' * empty}[/dim] [dim]65[/dim]")
        console.print(f"  [dim]Spanish-like → English-like[/dim]")

    elif npvi_current:
        console.print(f"\n[bold]Current nPVI:[/bold] {npvi_current:.0f}")

    # Level progress
    current_level = progress.get("current_level", 1)
    levels = progress.get("levels", {})

    console.print()
    console.print("[bold]Levels:[/bold]")

    table = Table(box=box.SIMPLE, show_header=False, padding=(0, 1))
    table.add_column("Level", width=30)
    table.add_column("Progress", width=25)
    table.add_column("Status", width=15)

    for level_num in range(1, 7):
        level_data = levels.get(level_num, {})
        config = RHYTHM_LEVEL_CONFIG.get(level_num, {})

        level_name = config.get("name", f"Level {level_num}")
        required = config.get("consecutive_passes", 3)
        consecutive = level_data.get("consecutive_passes", 0)
        unlocked = level_data.get("unlocked_at") is not None
        mastered = consecutive >= required

        # Level label with number
        level_label = f"[bold]{level_num}.[/bold] {level_name}"

        # Progress bar
        if not unlocked:
            progress_str = "[dim]🔒 Locked[/dim]"
            status = ""
        elif mastered:
            progress_str = "[green]✓ ✓ ✓[/green]"
            status = "[green]Mastered[/green]"
        else:
            checks = "✓ " * consecutive + "○ " * (required - consecutive)
            progress_str = f"[yellow]{checks.strip()}[/yellow]"
            status = f"[yellow]{consecutive}/{required}[/yellow]"

        # Highlight current level
        if level_num == current_level and not mastered:
            level_label = f"[bold cyan]→ {level_label}[/bold cyan]"

        table.add_row(level_label, progress_str, status)

    console.print(table)
    console.print()


def display_level_unlock(level: int) -> None:
    """Display celebration when a new level is unlocked."""
    from config import RHYTHM_LEVEL_CONFIG

    config = RHYTHM_LEVEL_CONFIG.get(level, {})
    level_name = config.get("name", f"Level {level}")
    description = config.get("description", "")

    console.print()
    console.print(Panel(
        f"[bold green]🎉 LEVEL {level} UNLOCKED! 🎉[/bold green]\n\n"
        f"[bold]{level_name}[/bold]\n"
        f"[dim]{description}[/dim]\n\n"
        f"[cyan]New techniques to practice:[/cyan]\n"
        f"{chr(10).join('• ' + t for t in config.get('techniques', []))}",
        border_style="green",
        title="[bold]CONGRATULATIONS[/bold]",
    ))
    console.print()


def display_rhythm_feedback(result, prosody, level: int, passed: bool) -> None:
    """Display rhythm-specific feedback from AI analysis."""

    console.print()

    # Pass/Fail indicator
    if passed:
        console.print(Panel(
            f"[bold green]✓ LEVEL {level} PASS[/bold green]",
            border_style="green",
        ))
    else:
        console.print(Panel(
            f"[bold yellow]○ Keep practicing Level {level}[/bold yellow]",
            border_style="yellow",
        ))

    # Transcript
    if result.transcript:
        console.print()
        console.print(Panel(
            f"[italic]{result.transcript}[/italic]",
            title="[bold blue]What you said[/bold blue]",
            border_style="blue",
        ))

    # Rhythm metrics
    console.print()
    table = Table(box=box.ROUNDED, show_header=True, title="[bold]Rhythm Analysis[/bold]", expand=True)
    table.add_column("Metric", style="bold", width=18)
    table.add_column("Value", justify="center", width=12)
    table.add_column("Feedback")  # No fixed width - let it expand

    # AI rhythm score
    rhythm_color = score_to_color(result.rhythm_score)
    table.add_row(
        "AI Rhythm Score",
        f"[{rhythm_color}]{result.rhythm_score}/10[/{rhythm_color}]",
        result.timing_feedback,  # Full feedback
    )

    # Measured nPVI
    npvi = prosody.rhythm.pvi
    npvi_color = "green" if npvi >= 55 else "yellow" if npvi >= 45 else "red"
    table.add_row(
        "nPVI (measured)",
        f"[{npvi_color}]{npvi:.0f}[/{npvi_color}]",
        "[dim]Target: 55-65 (English-like)[/dim]",
    )

    # AI nPVI estimate
    if result.npvi_estimate:
        est_color = "green" if result.npvi_estimate >= 55 else "yellow" if result.npvi_estimate >= 45 else "red"
        table.add_row(
            "nPVI (AI estimate)",
            f"[{est_color}]{result.npvi_estimate:.0f}[/{est_color}]",
            "[dim]Based on AI perception[/dim]",
        )

    # Stress correct
    stress_check = "[green]✓[/green]" if result.stress_correct else "[red]✗[/red]"
    table.add_row(
        "Stress Patterns",
        stress_check,
        result.stress_feedback,  # Full feedback
    )

    # Function reduction (for levels 2+)
    if level >= 2:
        reduction_check = "[green]✓[/green]" if result.function_reduction else "[yellow]○[/yellow]"
        table.add_row(
            "Function Reduction",
            reduction_check,
            result.reduction_feedback,  # Full feedback
        )

    console.print(table)

    # Word stress issues
    if result.word_stress_issues:
        console.print()
        console.print("[bold red]Word Stress Issues:[/bold red]")
        for issue in result.word_stress_issues:
            console.print(f"  [red]•[/red] [bold]{issue.get('word', '')}[/bold]")
            expected = issue.get('expected', '')
            heard = issue.get('heard', '')
            if expected and heard:
                console.print(f"    Expected: {expected} → Heard: {heard}")
            tip = issue.get('tip', '')
            if tip:
                console.print(f"    [dim]{tip}[/dim]")

    # Technique tip
    if result.technique_tip:
        console.print()
        console.print(Panel(
            f"[yellow]{result.technique_tip}[/yellow]",
            title="[bold yellow]Technique Tip[/bold yellow]",
            border_style="yellow",
        ))

    # Connected speech guidance (AI-generated)
    if result.linked or result.stress_pattern:
        console.print()
        content = ""
        if result.stress_pattern:
            content += f"[bold white]Pattern:[/bold white] [white]{result.stress_pattern}[/white]  [dim](o = unstressed, O = STRESSED)[/dim]\n\n"
        if result.linked:
            content += f"[bold yellow]Say it like:[/bold yellow] [yellow]{result.linked}[/yellow]"
            if result.linked_ipa:
                content += f"\n[dim yellow]{result.linked_ipa}[/dim yellow]"
        console.print(Panel(
            content.strip(),
            title="[bold cyan]Connected Speech[/bold cyan]",
            border_style="cyan",
        ))

    # Encouragement
    if result.encouragement:
        console.print()
        console.print(f"[green]{result.encouragement}[/green]")

    console.print()


def display_rhythm_drill_intro(drill: dict, level: int) -> None:
    """Display the drill introduction with text and technique."""
    from config import RHYTHM_LEVEL_CONFIG, TECHNIQUE_EXPLANATIONS

    config = RHYTHM_LEVEL_CONFIG.get(level, {})
    level_name = config.get("name", f"Level {level}")

    # Build panel content with text and IPA
    content = f"[bold white]{drill.get('text', '')}[/bold white]"
    if drill.get("ipa"):
        content += f"\n[dim cyan]/{drill['ipa']}/[/dim cyan]"

    console.print()
    console.print(Panel(
        content,
        title=f"[bold green]Level {level}: {level_name}[/bold green]",
        subtitle=f"[dim]{drill.get('focus', '')}[/dim]",
        border_style="green",
        padding=(1, 2),
    ))

    if drill.get("pattern"):
        console.print(f"[dim]Pattern: {drill['pattern']}  (o = unstressed, O = STRESSED)[/dim]")

    # Show technique with detailed explanation
    technique_text = drill.get("technique", "")
    if technique_text:
        # If technique already has detailed explanation (long text with colon), show as-is
        if len(technique_text) > 60 and ":" in technique_text:
            # Split into name and explanation
            parts = technique_text.split(":", 1)
            console.print(f"\n[bold cyan]Technique: {parts[0].strip()}[/bold cyan]")
            if len(parts) > 1:
                console.print(f"[cyan]{parts[1].strip()}[/cyan]")
        else:
            # Short label - look up detailed explanation
            console.print(f"\n[bold cyan]Technique: {technique_text}[/bold cyan]")
            # Try exact match first, then partial match
            explanation = TECHNIQUE_EXPLANATIONS.get(technique_text)
            if not explanation:
                for key, value in TECHNIQUE_EXPLANATIONS.items():
                    if key.lower() in technique_text.lower() or technique_text.lower() in key.lower():
                        explanation = value
                        break
            if explanation:
                console.print(f"[cyan]{explanation}[/cyan]")

    console.print()


# =============================================================================
# Real-Time Feedback Display
# =============================================================================

class LiveFeedbackDisplay:
    """
    Real-time feedback display using Rich Live for streaming updates.

    Provides visual feedback during real-time rhythm training sessions.
    """

    def __init__(self, console: Console = None):
        """Initialize the live feedback display."""
        self.console = console or Console()
        self.live: Optional[Live] = None
        self._current_state = "idle"
        self._drill_text = ""
        self._drill_ipa = ""
        self._level = 1
        self._partial_feedback = ""
        self._result_text = ""
        self._score = 0
        self._passed = False

    def _build_display(self) -> Panel:
        """Build the current display panel based on state."""
        content = Text()

        # Drill text
        if self._drill_text:
            content.append(self._drill_text + "\n", style="bold white")
            if self._drill_ipa:
                content.append(f"/{self._drill_ipa}/\n", style="dim cyan")
            content.append("\n")

        # State-specific content
        if self._current_state == "playing_tts":
            content.append("  Listen first...", style="bold cyan")
        elif self._current_state == "listening":
            content.append("  Recording - speak now...", style="bold red")
        elif self._current_state == "processing":
            content.append("  Processing...", style="dim")
        elif self._current_state == "feedback":
            if self._partial_feedback:
                content.append(f"  {self._partial_feedback}", style="yellow")
        elif self._current_state == "result":
            if self._passed:
                content.append(f"  PASS ({self._score}/10) - ", style="bold green")
            else:
                content.append(f"  Keep practicing ({self._score}/10) - ", style="bold yellow")
            if self._result_text:
                content.append(self._result_text)
        elif self._current_state == "transitioning":
            content.append("\n  [Next drill in 2s...]", style="dim")

        border_style = "green" if self._passed and self._current_state == "result" else "blue"

        return Panel(
            content,
            title=f"[bold]Level {self._level}: Real-Time Rhythm[/bold]",
            subtitle="[dim]say 'stop' or press 'q' to quit[/dim]",
            border_style=border_style,
        )

    def start(self):
        """Start the live display."""
        self.live = Live(
            self._build_display(),
            console=self.console,
            refresh_per_second=4,
            transient=False,
        )
        self.live.start()

    def stop(self):
        """Stop the live display."""
        if self.live:
            self.live.stop()
            self.live = None

    def set_drill(self, text: str, ipa: str = "", level: int = 1):
        """Set the current drill information."""
        self._drill_text = text
        self._drill_ipa = ipa
        self._level = level
        self._partial_feedback = ""
        self._result_text = ""
        self._passed = False
        self._update()

    def show_playing_tts(self):
        """Show that TTS is playing."""
        self._current_state = "playing_tts"
        self._update()

    def show_listening(self):
        """Show listening state with animation."""
        self._current_state = "listening"
        self._update()

    def show_processing(self):
        """Show processing state."""
        self._current_state = "processing"
        self._update()

    def update_partial_feedback(self, feedback: str):
        """Update with partial streaming feedback."""
        self._current_state = "feedback"
        self._partial_feedback = feedback
        self._update()

    def show_result(self, passed: bool, score: int, feedback: str = ""):
        """Show the final result."""
        self._current_state = "result"
        self._passed = passed
        self._score = score
        self._result_text = feedback
        self._update()

    def show_transitioning(self):
        """Show transitioning to next drill."""
        self._current_state = "transitioning"
        self._update()

    def clear(self):
        """Clear and reset the display."""
        self._current_state = "idle"
        self._drill_text = ""
        self._drill_ipa = ""
        self._partial_feedback = ""
        self._result_text = ""
        self._update()

    def _update(self):
        """Update the live display."""
        if self.live:
            self.live.update(self._build_display())
