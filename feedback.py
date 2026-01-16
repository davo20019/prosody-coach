"""Feedback display module for prosody analysis results."""

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich import box

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
