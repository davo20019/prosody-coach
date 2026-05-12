"""Feedback display module for prosody analysis results."""

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich.live import Live
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


def build_word_stress_display(transcript: str, stress_pattern: str, linked: str = None) -> str:
    """
    Build a word-aligned stress visualization using a table for proper alignment.

    Args:
        transcript: The original sentence
        stress_pattern: Pattern like "o O o O o o O"
        linked: Connected speech like "I-WANNA-GO-tuhthuh-STORE"

    Returns:
        Formatted string showing words aligned with stress markers
    """
    if not transcript or not stress_pattern:
        return ""

    # Parse stress pattern
    pattern_parts = stress_pattern.strip().split()
    words = transcript.replace(",", "").replace(".", "").replace("?", "").replace("!", "").split()

    # Build the display using simple fixed-width formatting
    # Each word gets the same column width based on longest word
    max_width = max(len(w) for w in words) if words else 4
    col_width = max(max_width + 1, 5)  # At least 5 chars per column

    word_cells = []
    marker_cells = []

    for i, word in enumerate(words):
        if i < len(pattern_parts):
            is_stressed = pattern_parts[i] == "O"
        else:
            is_stressed = False

        # Create the word cell (padded to fixed width)
        if is_stressed:
            display_word = word.upper()
            word_cells.append(f"[bold yellow]{display_word:<{col_width}}[/bold yellow]")
            marker_cells.append(f"[bold cyan]{'↑':<{col_width}}[/bold cyan]")
        else:
            display_word = word.lower()
            word_cells.append(f"[dim]{display_word:<{col_width}}[/dim]")
            marker_cells.append(f"{'':<{col_width}}")

    # Join with no extra spacing (width is built into each cell)
    word_line = "".join(word_cells)
    marker_line = "".join(marker_cells)

    return word_line + "\n" + marker_line


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

    # Build nPVI details - show both when vocalic is available
    pvi_details = f"nPVI: {rhythm.pvi:.0f}"
    if rhythm.pvi_type == "vocalic" and rhythm.pvi_ioi is not None:
        pvi_details = f"nPVI (vocalic): {rhythm.pvi:.0f}\nnPVI (onset): {rhythm.pvi_ioi:.0f}"
        if rhythm.vowel_count:
            pvi_details += f"\nVowels: {rhythm.vowel_count}"
    elif rhythm.pvi_type == "ioi":
        pvi_details = f"nPVI (onset): {rhythm.pvi:.0f}"

    table.add_row(
        "Rhythm",
        f"{score_to_bar(rhythm.score)}  [{rhythm_color}]{rhythm.score}/10[/{rhythm_color}]",
        f"{pvi_details}\nType: {rhythm_type}",
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
        console.print("  [dim]Spanish-like → English-like[/dim]")

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


def display_rhythm_feedback(result, prosody, level: int, passed: bool, progress: tuple = (0, 3), show_details: bool = False) -> None:
    """
    Display rhythm-specific feedback from AI analysis.

    New hierarchy: VERDICT → ACTION → DETAILS
    - Verdict: Pass/fail + score + progress in one glance
    - Action: What to do differently (technique + how to say it)
    - Details: Metrics (collapsed by default, 'd' to expand)

    Args:
        result: RhythmCoachingResult from AI
        prosody: ProsodyAnalysis from audio
        level: Current level (1-6)
        passed: Whether the attempt passed
        progress: Tuple of (current_consecutive, required) e.g. (1, 3)
        show_details: Whether to show detailed metrics
    """
    from config import RHYTHM_LEVEL_CONFIG

    config = RHYTHM_LEVEL_CONFIG.get(level, {})
    level_name = config.get("name", f"Level {level}")

    console.print()

    # ==========================================================================
    # SECTION 1: VERDICT - Pass/fail + score + progress in one header
    # ==========================================================================
    rhythm_color = score_to_color(result.rhythm_score)
    current_passes, required_passes = progress

    if passed:
        status_icon = "[bold green]✓ PASS[/bold green]"
        border_color = "green"
    else:
        status_icon = "[bold yellow]○ KEEP PRACTICING[/bold yellow]"
        border_color = "yellow"

    # Build progress indicator: ✓ ✓ ○ format
    progress_visual = ""
    for i in range(required_passes):
        if i < current_passes:
            progress_visual += "[green]✓[/green] "
        else:
            progress_visual += "[dim]○[/dim] "
    progress_visual = progress_visual.strip()

    # Compact header with all key info
    header_content = (
        f"{status_icon}    "
        f"[{rhythm_color}][bold]{result.rhythm_score}/10[/bold][/{rhythm_color}]    "
        f"Progress: {progress_visual}\n"
        f"[dim]Level {level}: {level_name}[/dim]"
    )

    console.print(Panel(
        header_content,
        border_style=border_color,
        padding=(0, 2),
    ))

    # Transcript - simple, no heavy panel
    if result.transcript:
        console.print()
        console.print(f'  [italic]"{result.transcript}"[/italic]')

    # ==========================================================================
    # SECTION 2: WHAT'S HAPPENING - Feedback on stress and reduction
    # ==========================================================================

    # Show the key feedback about what the learner is doing right/wrong
    # This is pedagogically important - don't hide it in details
    feedback_content = ""

    # Stress feedback (always relevant)
    stress_icon = "[green]✓[/green]" if result.stress_correct else "[yellow]○[/yellow]"
    if result.stress_feedback:
        feedback_content += f"{stress_icon} [bold]Stress:[/bold] {result.stress_feedback}\n"

    # Reduction feedback (level 2+)
    if level >= 2 and result.reduction_feedback:
        reduction_icon = "[green]✓[/green]" if result.function_reduction else "[yellow]○[/yellow]"
        feedback_content += f"{reduction_icon} [bold]Reduction:[/bold] {result.reduction_feedback}\n"

    if feedback_content.strip():
        console.print()
        console.print(Panel(
            feedback_content.strip(),
            title="[bold blue]What You're Doing[/bold blue]",
            border_style="blue",
            padding=(0, 2),
        ))

    # ==========================================================================
    # SECTION 3: HOW TO SAY IT - Stress pattern + connected speech
    # ==========================================================================
    console.print()

    # Build the "How to say it" section with stress pattern and connected speech
    action_content = ""

    # Word-aligned stress visualization (most important - shows which words to stress)
    if result.transcript and result.stress_pattern:
        stress_display = build_word_stress_display(result.transcript, result.stress_pattern)
        if stress_display:
            action_content += f"{stress_display}\n\n"

    # Connected speech - the "say it like this" model (shows HOW to pronounce)
    if result.linked:
        action_content += f"[bold yellow]Say it like:[/bold yellow]  [yellow]{result.linked}[/yellow]"
        if result.linked_ipa:
            action_content += f"\n[dim]{result.linked_ipa}[/dim]"
        action_content += "\n\n"

    # Technique tip - practical advice
    if result.technique_tip:
        tip_text = result.technique_tip
        # Extract the HOW TO PRACTICE part if structured
        if "HOW TO PRACTICE:" in tip_text.upper():
            how_to_idx = tip_text.upper().find("HOW TO PRACTICE:")
            how_to_text = tip_text[how_to_idx + len("HOW TO PRACTICE:"):].strip()
            how_to_text = how_to_text.lstrip("[3. ").rstrip("]")
            action_content += f"[bold white]Practice tip:[/bold white] {how_to_text}"
        elif "3." in tip_text:
            lines = tip_text.split("\n")
            for line in lines:
                if line.strip().startswith("[3.") or line.strip().startswith("3."):
                    how_to_text = line.strip().lstrip("[3. ").rstrip("]")
                    if ":" in how_to_text:
                        how_to_text = how_to_text.split(":", 1)[1].strip()
                    action_content += f"[bold white]Practice tip:[/bold white] {how_to_text}"
                    break
        else:
            # Show the full technique tip if we can't parse it
            action_content += f"[bold white]Practice tip:[/bold white] {tip_text}"

    if action_content.strip():
        console.print(Panel(
            action_content.strip(),
            title="[bold cyan]How to Say It[/bold cyan]",
            border_style="cyan",
            padding=(1, 2),
        ))

    # If no stress pattern was provided, show a note
    if not result.stress_pattern and not result.linked:
        console.print("[dim]Note: Focus on stressing content words (nouns, verbs, adjectives) and reducing function words (the, to, a).[/dim]")

    # ==========================================================================
    # SECTION 3: DETAILS - Metrics (shown if show_details=True or word issues)
    # ==========================================================================

    # Always show word stress issues if present (these are specific and actionable)
    if result.word_stress_issues:
        console.print()
        console.print("[bold]Word issues:[/bold]")
        for issue in result.word_stress_issues:
            word = issue.get('word', '')
            expected = issue.get('expected', '')
            heard = issue.get('heard', '')
            tip = issue.get('tip', '')
            if expected and heard:
                console.print(f"  [red]•[/red] [bold]{word}[/bold]: {heard} → {expected}")
            else:
                console.print(f"  [red]•[/red] [bold]{word}[/bold]")
            if tip:
                console.print(f"    [dim]{tip}[/dim]")

    if show_details:
        # Full metrics table
        console.print()
        table = Table(box=box.SIMPLE, show_header=True, padding=(0, 1))
        table.add_column("Metric", style="bold", width=16)
        table.add_column("Value", justify="center", width=8)
        table.add_column("", width=50)

        # nPVI - show both vocalic and onset when available
        rhythm = prosody.rhythm
        npvi = rhythm.pvi
        npvi_color = "green" if npvi >= 55 else "yellow" if npvi >= 45 else "red"

        if rhythm.pvi_type == "vocalic" and rhythm.pvi_ioi is not None:
            # Show both metrics
            table.add_row(
                "nPVI (vocalic)",
                f"[{npvi_color}]{rhythm.pvi_vocalic:.0f}[/{npvi_color}]",
                "[dim]True vowel-based measurement[/dim]",
            )
            ioi_color = "green" if rhythm.pvi_ioi >= 55 else "yellow" if rhythm.pvi_ioi >= 45 else "red"
            table.add_row(
                "nPVI (onset)",
                f"[{ioi_color}]{rhythm.pvi_ioi:.0f}[/{ioi_color}]",
                "[dim]Syllable onset approximation[/dim]",
            )
            if rhythm.vowel_count:
                table.add_row(
                    "Vowels",
                    f"{rhythm.vowel_count}",
                    "[dim]Detected vowels for vocalic nPVI[/dim]",
                )
        else:
            # IOI only
            table.add_row(
                "nPVI (onset)",
                f"[{npvi_color}]{npvi:.0f}[/{npvi_color}]",
                "[dim]target: 55-65[/dim]",
            )

        # Stress patterns
        stress_icon = "[green]✓[/green]" if result.stress_correct else "[red]✗[/red]"
        stress_summary = "Correct placement" if result.stress_correct else "Needs work"
        table.add_row("Stress", stress_icon, f"[dim]{stress_summary}[/dim]")

        # Function reduction (levels 2+)
        if level >= 2:
            reduction_icon = "[green]✓[/green]" if result.function_reduction else "[yellow]○[/yellow]"
            reduction_summary = "Good reduction" if result.function_reduction else "Reduce more"
            table.add_row("Reduction", reduction_icon, f"[dim]{reduction_summary}[/dim]")

        console.print(table)

        # Full AI feedback (only in details mode)
        if result.timing_feedback:
            console.print()
            console.print(f"[dim]{result.timing_feedback}[/dim]")
    else:
        # Compact metrics line
        rhythm = prosody.rhythm
        npvi = rhythm.pvi
        npvi_color = "green" if npvi >= 55 else "yellow" if npvi >= 45 else "red"
        stress_icon = "[green]✓[/green]" if result.stress_correct else "[red]✗[/red]"

        # Indicate measurement type in compact view
        npvi_label = "nPVI" if rhythm.pvi_type == "ioi" else "nPVI (vocalic)"
        metrics_line = f"[dim]{npvi_label}: [{npvi_color}]{npvi:.0f}[/{npvi_color}]  •  Stress: {stress_icon}[/dim]"
        if level >= 2:
            reduction_icon = "[green]✓[/green]" if result.function_reduction else "[yellow]○[/yellow]"
            metrics_line += f"[dim]  •  Reduction: {reduction_icon}[/dim]"

        console.print()
        console.print(metrics_line)

    # Encouragement (brief, at the end)
    if result.encouragement and not show_details:
        console.print()
        console.print(f"[green]{result.encouragement}[/green]")

    console.print()


def display_rhythm_drill_intro(drill: dict, level: int) -> None:
    """Display the drill introduction with text and technique."""
    from config import RHYTHM_LEVEL_CONFIG, TECHNIQUE_EXPLANATIONS

    config = RHYTHM_LEVEL_CONFIG.get(level, {})
    level_name = config.get("name", f"Level {level}")

    drill_text = drill.get('text', '')
    pattern = drill.get("pattern", "")

    # Build panel content
    content_parts = []

    # Main sentence with word-aligned stress visualization
    if drill_text and pattern:
        stress_display = build_word_stress_display(drill_text, pattern)
        if stress_display:
            content_parts.append(stress_display)
        else:
            content_parts.append(f"[bold white]{drill_text}[/bold white]")
    else:
        content_parts.append(f"[bold white]{drill_text}[/bold white]")

    # IPA pronunciation
    if drill.get("ipa"):
        content_parts.append(f"[dim]/{drill['ipa']}/[/dim]")

    console.print()
    console.print(Panel(
        "\n".join(content_parts),
        title=f"[bold green]Level {level}: {level_name}[/bold green]",
        subtitle=f"[dim]{drill.get('focus', '')}[/dim]",
        border_style="green",
        padding=(1, 2),
    ))

    # Show technique with detailed explanation (brief version)
    technique_text = drill.get("technique", "")
    if technique_text:
        # Extract just the technique name and a brief explanation
        if len(technique_text) > 60 and ":" in technique_text:
            parts = technique_text.split(":", 1)
            technique_name = parts[0].strip()
            technique_detail = parts[1].strip() if len(parts) > 1 else ""
            # Truncate long explanations for the intro
            if len(technique_detail) > 100:
                technique_detail = technique_detail[:100] + "..."
            console.print(f"[cyan]Technique:[/cyan] [dim]{technique_name}[/dim]")
            if technique_detail:
                console.print(f"[dim]{technique_detail}[/dim]")
        else:
            console.print(f"[cyan]Technique:[/cyan] [dim]{technique_text}[/dim]")
            # Look up detailed explanation
            explanation = TECHNIQUE_EXPLANATIONS.get(technique_text)
            if not explanation:
                for key, value in TECHNIQUE_EXPLANATIONS.items():
                    if key.lower() in technique_text.lower() or technique_text.lower() in key.lower():
                        explanation = value
                        break
            if explanation:
                # Truncate for intro view
                if len(explanation) > 100:
                    explanation = explanation[:100] + "..."
                console.print(f"[dim]{explanation}[/dim]")

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
