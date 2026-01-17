"""Real-time rhythm training module using Gemini Live API."""

import asyncio
import base64
import os
import sys
import re
import json
from enum import Enum, auto
from dataclasses import dataclass, field
from typing import Optional

from rich.console import Console
from rich.panel import Panel

from google import genai
from google.genai import types

from config import (
    GEMINI_API_KEY,
    GEMINI_LIVE_MODEL,
    RHYTHM_LEVEL_CONFIG,
    REALTIME_FEEDBACK_DELAY,
    REALTIME_SESSION_TIMEOUT,
    SAMPLE_RATE,
)
from recorder import AsyncAudioStreamer
from feedback import LiveFeedbackDisplay
from prompts import get_random_rhythm_drill, get_rhythm_drills_by_level
from storage import (
    get_rhythm_progress,
    update_rhythm_progress,
    save_rhythm_drill_attempt,
    get_available_levels,
)


class SessionState(Enum):
    """State machine for real-time rhythm session."""
    IDLE = auto()
    PLAYING_TTS = auto()
    LISTENING = auto()
    PROCESSING = auto()
    SHOWING_FEEDBACK = auto()
    TRANSITIONING = auto()
    STOPPED = auto()


@dataclass
class RealtimeFeedback:
    """Parsed feedback from Gemini Live API response."""
    transcript: str = ""
    rhythm_score: int = 5
    passed: bool = False
    feedback: str = ""
    word_issues: list = field(default_factory=list)
    encouragement: str = ""


class RealtimeRhythmSession:
    """
    Manages real-time rhythm training with Gemini Live API.

    Uses WebSocket connection for streaming audio and receiving
    real-time feedback without requiring Enter presses.
    """

    def __init__(self, level: int, console: Console):
        """
        Initialize the real-time session.

        Args:
            level: Rhythm training level (1-6)
            console: Rich console for output
        """
        self.level = level
        self.console = console
        self.state = SessionState.IDLE
        self.display = LiveFeedbackDisplay(console)
        self.audio_streamer = AsyncAudioStreamer()
        self.current_drill = None
        self.session = None
        self.client = None
        self._stop_requested = False
        self._keyboard_task = None

    def _get_system_instruction(self, drill: dict) -> str:
        """Build system instruction for Gemini Live with current drill context."""
        level_config = RHYTHM_LEVEL_CONFIG.get(self.level, RHYTHM_LEVEL_CONFIG[1])

        return f"""You are a real-time English rhythm coach for a Spanish speaker. Provide IMMEDIATE, CONCISE feedback.

CURRENT DRILL:
Text: "{drill.get('text', '')}"
Level: {self.level} - {level_config['name']}
Focus: {drill.get('focus', '')}
Technique: {drill.get('technique', '')}

REQUIREMENTS:
- nPVI Target: {level_config['npvi_target']}+
- Min Rhythm Score: {level_config['min_rhythm_score']}/10

RESPONSE FORMAT (JSON only, no markdown):
{{"transcript": "what they said", "rhythm_score": 7, "passed": true, "feedback": "Good stress on TODAY!", "word_issues": [], "encouragement": "Nice rhythm!"}}

RULES:
1. Listen for the user speaking the drill text
2. Evaluate rhythm: stressed vs unstressed syllable contrast
3. Check word stress patterns
4. Provide encouraging, specific feedback
5. If user says "stop" or "quit", respond with: {{"stop": true}}
6. Keep feedback SHORT (under 50 words)

Be supportive but accurate. Spanish speakers often use equal syllable timing - help them develop English stress-timing."""

    async def _connect(self) -> bool:
        """Initialize WebSocket connection to Gemini Live API."""
        api_key = os.environ.get("GEMINI_API_KEY") or GEMINI_API_KEY
        if not api_key:
            self.console.print(
                "[red]GEMINI_API_KEY not set. Set it in environment or config.py[/red]"
            )
            return False

        try:
            self.client = genai.Client(api_key=api_key)
            return True
        except Exception as e:
            self.console.print(f"[red]Failed to initialize Gemini client: {e}[/red]")
            return False

    def _get_session_config(self, drill: dict) -> types.LiveConnectConfig:
        """Get the Live API session config for a drill."""
        return types.LiveConnectConfig(
            response_modalities=["TEXT"],
            system_instruction=types.Content(
                parts=[types.Part.from_text(text=self._get_system_instruction(drill))]
            ),
        )

    async def _send_audio(self):
        """Stream audio to Gemini Live API."""
        try:
            async for chunk in self.audio_streamer.stream_audio():
                if self._stop_requested or self.state == SessionState.STOPPED:
                    break
                if self.session and chunk:
                    # Base64 encode the audio data
                    audio_b64 = base64.b64encode(chunk).decode("utf-8")
                    await self.session.send_realtime_input(
                        audio=types.Blob(
                            data=audio_b64,
                            mime_type=f"audio/pcm;rate={SAMPLE_RATE}"
                        )
                    )
        except Exception as e:
            if not self._stop_requested:
                pass  # Silently handle audio streaming errors

    async def _receive_responses(self) -> RealtimeFeedback:
        """Receive and parse streaming responses from Gemini."""
        feedback = RealtimeFeedback()
        accumulated_text = ""

        try:
            async for response in self.session.receive():
                if self._stop_requested:
                    break

                # Handle server content
                if response.server_content:
                    if response.server_content.model_turn:
                        for part in response.server_content.model_turn.parts:
                            if part.text:
                                accumulated_text += part.text
                                # Try to parse partial feedback
                                self.display.update_partial_feedback(
                                    f"Analyzing... {part.text[:50]}"
                                )

                    # Check if turn is complete
                    if response.server_content.turn_complete:
                        break

        except Exception as e:
            if not self._stop_requested:
                self.console.print(f"[yellow]Response error: {e}[/yellow]")

        # Parse accumulated JSON response
        if accumulated_text:
            feedback = self._parse_feedback(accumulated_text)

        return feedback

    def _parse_feedback(self, text: str) -> RealtimeFeedback:
        """Parse JSON feedback from Gemini response."""
        feedback = RealtimeFeedback()

        try:
            # Clean up text - remove markdown code blocks if present
            text = text.strip()
            if text.startswith("```"):
                text = re.sub(r'^```\w*\n?', '', text)
                text = re.sub(r'\n?```$', '', text)
            text = text.strip()

            data = json.loads(text)

            # Check for stop command
            if data.get("stop"):
                self._stop_requested = True
                return feedback

            feedback.transcript = data.get("transcript", "")
            feedback.rhythm_score = int(data.get("rhythm_score", 5))
            feedback.passed = bool(data.get("passed", False))
            feedback.feedback = data.get("feedback", "")
            feedback.word_issues = data.get("word_issues", [])
            feedback.encouragement = data.get("encouragement", "")

        except json.JSONDecodeError:
            # Try to extract info from plain text
            feedback.feedback = text[:100] if text else "Processing..."
        except Exception:
            pass

        return feedback

    async def _check_keyboard(self):
        """Check for keyboard input to quit."""
        loop = asyncio.get_event_loop()

        def check_stdin():
            import select
            if select.select([sys.stdin], [], [], 0)[0]:
                char = sys.stdin.read(1)
                if char.lower() == 'q':
                    return True
            return False

        while not self._stop_requested:
            try:
                should_quit = await loop.run_in_executor(None, check_stdin)
                if should_quit:
                    self._stop_requested = True
                    break
                await asyncio.sleep(0.1)
            except Exception:
                break

    async def run_drill(self, drill: dict) -> Optional[RealtimeFeedback]:
        """
        Execute a single drill with streaming feedback.

        Args:
            drill: Drill dictionary with text, ipa, focus, etc.

        Returns:
            RealtimeFeedback if completed, None if stopped
        """
        self.current_drill = drill

        # Update display (IPA is shown, no TTS needed in real-time mode)
        self.display.set_drill(
            text=drill.get("text", ""),
            ipa=drill.get("ipa", ""),
            level=self.level,
        )

        if self._stop_requested:
            return None

        # Start listening immediately
        self.state = SessionState.LISTENING
        self.display.show_listening()

        # Start audio streaming
        await self.audio_streamer.start()

        feedback = RealtimeFeedback()

        # Use async with for the session context manager
        try:
            config = self._get_session_config(drill)
            async with self.client.aio.live.connect(
                model=GEMINI_LIVE_MODEL,
                config=config,
            ) as session:
                self.session = session

                # Run audio sending and response receiving concurrently
                try:
                    async with asyncio.timeout(30):  # 30 second timeout per drill
                        send_task = asyncio.create_task(self._send_audio())
                        receive_task = asyncio.create_task(self._receive_responses())

                        # Wait for feedback (receive task completes when turn is done)
                        feedback = await receive_task

                        # Stop audio streaming
                        await self.audio_streamer.stop()
                        send_task.cancel()
                        try:
                            await send_task
                        except asyncio.CancelledError:
                            pass

                except asyncio.TimeoutError:
                    await self.audio_streamer.stop()
                    feedback = RealtimeFeedback(
                        feedback="Session timed out. Try speaking sooner.",
                        rhythm_score=5,
                        passed=False,
                    )

        except Exception as e:
            await self.audio_streamer.stop()
            self.console.print(f"[yellow]Drill error: {e}[/yellow]")
            feedback = RealtimeFeedback(
                feedback=f"Error: {str(e)[:50]}",
                rhythm_score=5,
                passed=False,
            )

        self.session = None

        if self._stop_requested:
            return None

        # Show result
        self.state = SessionState.SHOWING_FEEDBACK
        self.display.show_result(
            passed=feedback.passed,
            score=feedback.rhythm_score,
            feedback=feedback.feedback or feedback.encouragement,
        )

        return feedback

    async def start(self):
        """Initialize the session."""
        # Connect to API
        if not await self._connect():
            return False

        # Start display
        self.display.start()

        # Start keyboard listener
        self._keyboard_task = asyncio.create_task(self._check_keyboard())

        return True

    async def stop(self):
        """Clean up and stop the session."""
        self._stop_requested = True
        self.state = SessionState.STOPPED

        # Stop keyboard listener
        if self._keyboard_task:
            self._keyboard_task.cancel()
            try:
                await self._keyboard_task
            except asyncio.CancelledError:
                pass

        # Stop audio
        await self.audio_streamer.stop()

        # Session is managed by async with context, no need to close manually

        # Stop display
        self.display.stop()


async def run_realtime_rhythm_training(level: int, console: Console):
    """
    Main entry point for real-time rhythm training mode.

    Args:
        level: Starting level (1-6)
        console: Rich console for output
    """
    # Validate level
    available_levels = get_available_levels()
    if level not in available_levels:
        if level > max(available_levels):
            console.print(
                f"[yellow]Level {level} is locked. Starting at Level {max(available_levels)}.[/yellow]"
            )
            level = max(available_levels)
        else:
            console.print(f"[red]Invalid level: {level}[/red]")
            return

    # Check for baseline
    progress = get_rhythm_progress()
    if not progress.get("npvi_baseline"):
        console.print()
        console.print(
            "[yellow]No baseline measurement found.[/yellow]\n"
            "[dim]Run 'prosody rhythm --baseline' first to measure your starting nPVI.[/dim]"
        )
        return

    # Show intro
    level_config = RHYTHM_LEVEL_CONFIG.get(level, {})
    console.print()
    console.print(
        Panel(
            f"[bold yellow]EXPERIMENTAL - Real-Time Rhythm Training[/bold yellow]\n\n"
            f"[yellow]This feature is still in development and may not work correctly.[/yellow]\n"
            f"[dim]Use 'prosody rhythm' (without --realtime) for the stable version.[/dim]\n\n"
            f"Level {level}: {level_config.get('name', '')}\n"
            f"{level_config.get('description', '')}\n\n"
            f"[dim]- Speak naturally after seeing the prompt\n"
            f"- No Enter presses needed\n"
            f"- Say 'stop' or press 'q' to quit[/dim]",
            border_style="yellow",
            title="[bold yellow]Real-Time Mode (Experimental)[/bold yellow]",
        )
    )
    console.print()

    # Create session
    session = RealtimeRhythmSession(level, console)

    try:
        # Initialize
        if not await session.start():
            console.print(
                "[yellow]Failed to start real-time mode. "
                "Try standard mode: prosody rhythm[/yellow]"
            )
            return

        # Get drills for level
        drills = get_rhythm_drills_by_level(level)
        if not drills:
            console.print(f"[red]No drills available for Level {level}.[/red]")
            await session.stop()
            return

        drill_index = 0

        # Main loop
        while not session._stop_requested:
            # Get next drill
            drill = drills[drill_index % len(drills)]
            drill_index += 1

            # Run drill
            feedback = await session.run_drill(drill)

            if feedback is None or session._stop_requested:
                break

            # Update progress
            update_rhythm_progress(
                level=level,
                npvi=50,  # Placeholder - Live API doesn't provide nPVI
                rhythm_score=feedback.rhythm_score,
                passed=feedback.passed,
            )

            # Save attempt
            save_rhythm_drill_attempt(
                drill_id=drill.get("id", "unknown"),
                level=level,
                npvi=50,
                rhythm_score=feedback.rhythm_score,
                passed=feedback.passed,
            )

            # Transition delay
            session.state = SessionState.TRANSITIONING
            session.display.show_transitioning()
            await asyncio.sleep(REALTIME_FEEDBACK_DELAY)

    except KeyboardInterrupt:
        pass
    except Exception as e:
        console.print(f"\n[red]Error: {e}[/red]")
    finally:
        await session.stop()

    # Show final message
    console.print()
    console.print("[dim]Real-time session ended.[/dim]")
    console.print("[dim]Run 'prosody rhythm --status' to see your progress.[/dim]")
