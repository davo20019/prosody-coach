"""Communication-framework catalog.

This is the contributor surface for the Frameworks practice mode. A "framework"
is a named structure for short spoken answers (typically 30-90 seconds) with
explicit slots that the speaker is expected to fill: e.g. STAR has Situation,
Task, Action, Result. The framework_scoring module evaluates a recorded answer
against these slots and the prosody pipeline measures delivery.

Adding a new framework
----------------------
Add a key to FRAMEWORKS with this shape:

    "framework_id": {
        "id": "framework_id",                 # must match the key
        "name": "Human Name",                 # shown in the UI
        "category": "Short label",            # used to group cards
        "description": "One-sentence pitch",  # shown on the index card
        "when_to_use": "Short guidance",      # shown on the run page
        "target_duration_seconds": (low, high),
        "slots": [
            {
                "id": "slot_id",              # snake_case; used in scoring
                "name": "Display Name",
                "description": "What goes here",
                "expected_tense": "past" | "present" | "past_or_present_perfect" | "any",
                "starters": [                 # 3 short opening phrases for ESL scaffolding
                    "Phrase one…",
                    "Phrase two…",
                    "Phrase three…",
                ],
            },
            ...
        ],
        "scoring_rubric": {
            # Optional. Slot id that must include a number for full credit.
            "must_include_metric": "slot_id" | None,
            # Optional. If True, the cultural-pragmatic check flags
            # under-claiming credit (no first-person verbs).
            "self_attribution_required": bool,
        },
        "prompts": [
            {"id": "framework_id_1", "text": "...", "category": "..."},
            ...   # 3-5 starter prompts
        ],
    }

Conventions
-----------
- Slot ids are short, snake_case, and stable. The UI keys per-slot prosody by
  slot id and the storage layer JSON-serializes them, so renaming a slot is a
  migration concern.
- Prompt ids are framework_id + ordinal. They are stable identifiers used by
  the spaced-repetition table (framework_prompt_progress).
- Keep prompts realistic and ESL-friendly. The audience is non-native English
  speakers preparing for interviews, presentations, and professional meetings.
- Don't add a framework without at least three prompts.
"""

from typing import Optional


FRAMEWORKS: dict[str, dict] = {
    "star": {
        "id": "star",
        "name": "STAR Method",
        "category": "Behavioral interviews",
        "description": "Structure stories that prove your impact: Situation, Task, Action, Result.",
        "when_to_use": "Behavioral interview questions, performance reviews, networking.",
        "target_duration_seconds": (60, 90),
        "slots": [
            {
                "id": "situation",
                "name": "Situation",
                "description": "Set the context — what was happening, when, where.",
                "expected_tense": "past",
                "starters": [
                    "At my last role,…",
                    "On one project,…",
                    "When our team was facing…",
                ],
            },
            {
                "id": "task",
                "name": "Task",
                "description": "Explain the challenge or goal and your role in it.",
                "expected_tense": "past",
                "starters": [
                    "My responsibility was to…",
                    "The goal was to…",
                    "I needed to…",
                ],
            },
            {
                "id": "action",
                "name": "Action",
                "description": "Describe what you did — concrete, first-person steps.",
                "expected_tense": "past",
                "starters": [
                    "I started by…",
                    "I coordinated with…",
                    "I decided to…",
                ],
            },
            {
                "id": "result",
                "name": "Result",
                "description": "Share the outcome with a number, percentage, or before/after.",
                "expected_tense": "past_or_present_perfect",
                "starters": [
                    "As a result,…",
                    "That led to…",
                    "In the end, we…",
                ],
            },
        ],
        "scoring_rubric": {
            "must_include_metric": "result",
            "self_attribution_required": True,
        },
        "prompts": [
            {
                "id": "star_1",
                "text": "Tell me about a time you handled a conflict on your team.",
                "category": "leadership",
            },
            {
                "id": "star_2",
                "text": "Describe a project where you had to learn something new quickly.",
                "category": "learning",
            },
            {
                "id": "star_3",
                "text": "Tell me about a time you disagreed with your manager and how you handled it.",
                "category": "communication",
            },
            {
                "id": "star_4",
                "text": "Describe a situation where you missed a deadline. What did you do?",
                "category": "ownership",
            },
            {
                "id": "star_5",
                "text": "Tell me about an accomplishment you are most proud of.",
                "category": "impact",
            },
        ],
    },

    "prep": {
        "id": "prep",
        "name": "PREP",
        "category": "Quick verbal answers",
        "description": "Make a point and back it up in under a minute: Point, Reason, Example, Point.",
        "when_to_use": "Meeting answers, status updates, stating an opinion.",
        "target_duration_seconds": (30, 60),
        "slots": [
            {
                "id": "point",
                "name": "Point",
                "description": "State your position in one sentence.",
                "expected_tense": "any",
                "starters": [
                    "I believe that…",
                    "My recommendation is…",
                    "The clearest path is…",
                ],
            },
            {
                "id": "reason",
                "name": "Reason",
                "description": "Why you hold this position — one or two reasons.",
                "expected_tense": "any",
                "starters": [
                    "The main reason is…",
                    "This works because…",
                    "We see this because…",
                ],
            },
            {
                "id": "example",
                "name": "Example",
                "description": "A concrete example or data point that supports the reason.",
                "expected_tense": "past",
                "starters": [
                    "For example, last quarter we…",
                    "When we tried this with…",
                    "On the X project, we saw…",
                ],
            },
            {
                "id": "point_restated",
                "name": "Point (restated)",
                "description": "Close by restating the point, often with a recommendation.",
                "expected_tense": "any",
                "starters": [
                    "So to come back to the point,…",
                    "That's why I recommend…",
                    "In short, we should…",
                ],
            },
        ],
        "scoring_rubric": {
            "must_include_metric": None,
            "self_attribution_required": False,
        },
        "prompts": [
            {
                "id": "prep_1",
                "text": "Should our team adopt the new tool we have been evaluating?",
                "category": "decision",
            },
            {
                "id": "prep_2",
                "text": "What is the single most important priority for next quarter?",
                "category": "prioritization",
            },
            {
                "id": "prep_3",
                "text": "Do you think remote work helps or hurts collaboration on our team?",
                "category": "opinion",
            },
            {
                "id": "prep_4",
                "text": "Should we invest in writing more tests or shipping the new feature first?",
                "category": "tradeoff",
            },
        ],
    },

    "scqa": {
        "id": "scqa",
        "name": "SCQA",
        "category": "Executive openings",
        "description": "Open a topic the way consultants do: Situation, Complication, Question, Answer.",
        "when_to_use": "Opening a presentation, framing an executive update, writing an exec summary.",
        "target_duration_seconds": (60, 90),
        "slots": [
            {
                "id": "situation",
                "name": "Situation",
                "description": "What everyone already agrees is true (the shared context).",
                "expected_tense": "present",
                "starters": [
                    "Today, our team…",
                    "Currently, the business…",
                    "In our area, we usually…",
                ],
            },
            {
                "id": "complication",
                "name": "Complication",
                "description": "What changed, or the problem the audience needs to know about.",
                "expected_tense": "past_or_present_perfect",
                "starters": [
                    "But over the last quarter,…",
                    "Recently, we have seen…",
                    "However, that changed when…",
                ],
            },
            {
                "id": "question",
                "name": "Question",
                "description": "The implicit question that the complication raises.",
                "expected_tense": "any",
                "starters": [
                    "So the question is…",
                    "This raises the question of…",
                    "The key decision is whether…",
                ],
            },
            {
                "id": "answer",
                "name": "Answer",
                "description": "Your headline answer or recommendation.",
                "expected_tense": "any",
                "starters": [
                    "My recommendation is…",
                    "I propose that we…",
                    "The short answer is…",
                ],
            },
        ],
        "scoring_rubric": {
            "must_include_metric": None,
            "self_attribution_required": False,
        },
        "prompts": [
            {
                "id": "scqa_1",
                "text": "Open a status update about a project that is two weeks behind schedule.",
                "category": "project_status",
            },
            {
                "id": "scqa_2",
                "text": "Open a recommendation to pause a feature launch you have been preparing.",
                "category": "recommendation",
            },
            {
                "id": "scqa_3",
                "text": "Open a kickoff for a new initiative you are asking your team to take on.",
                "category": "kickoff",
            },
            {
                "id": "scqa_4",
                "text": "Open an update about customer churn going up over the last quarter.",
                "category": "metrics",
            },
        ],
    },

    "sbi": {
        "id": "sbi",
        "name": "SBI Feedback",
        "category": "Feedback conversations",
        "description": "Give specific, kind feedback: Situation, Behavior, Impact.",
        "when_to_use": "Giving feedback to a peer or report, raising a concern with a manager.",
        "target_duration_seconds": (30, 60),
        "slots": [
            {
                "id": "situation",
                "name": "Situation",
                "description": "When and where it happened — concrete time and place.",
                "expected_tense": "past",
                "starters": [
                    "In yesterday's standup,…",
                    "During the launch review on Tuesday,…",
                    "Last Friday in the team channel,…",
                ],
            },
            {
                "id": "behavior",
                "name": "Behavior",
                "description": "What the person actually did or said — observable, not interpreted.",
                "expected_tense": "past",
                "starters": [
                    "You interrupted twice while…",
                    "You wrote that…",
                    "You delivered the update without…",
                ],
            },
            {
                "id": "impact",
                "name": "Impact",
                "description": "The effect on you, the team, or the work.",
                "expected_tense": "any",
                "starters": [
                    "The effect was that…",
                    "As a result, the team…",
                    "This made it harder for me to…",
                ],
            },
        ],
        "scoring_rubric": {
            "must_include_metric": None,
            "self_attribution_required": False,
        },
        "prompts": [
            {
                "id": "sbi_1",
                "text": "Give a peer feedback about interrupting others in meetings.",
                "category": "team_dynamics",
            },
            {
                "id": "sbi_2",
                "text": "Give a direct report positive feedback about how they handled a tough customer.",
                "category": "positive",
            },
            {
                "id": "sbi_3",
                "text": "Tell your manager that you felt overlooked when credit was given for a project.",
                "category": "upward",
            },
            {
                "id": "sbi_4",
                "text": "Give a teammate feedback about missing agreed-on follow-ups.",
                "category": "accountability",
            },
        ],
    },

    "story": {
        "id": "story",
        "name": "Story Arc",
        "category": "Narrative storytelling",
        "description": "Tell a short, memorable story: Setup, Tension, Action, Resolution.",
        "when_to_use": "Networking, all-hands talks, opening a presentation with a story.",
        "target_duration_seconds": (60, 120),
        "slots": [
            {
                "id": "setup",
                "name": "Setup",
                "description": "Who, where, when — establish the character and context.",
                "expected_tense": "past",
                "starters": [
                    "A few years ago,…",
                    "Early in my career,…",
                    "When I was at X,…",
                ],
            },
            {
                "id": "tension",
                "name": "Tension",
                "description": "What changed or what was at stake — the conflict.",
                "expected_tense": "past",
                "starters": [
                    "Then everything changed when…",
                    "What I didn't expect was…",
                    "Suddenly,…",
                ],
            },
            {
                "id": "action",
                "name": "Action",
                "description": "What happened or what you did about it.",
                "expected_tense": "past",
                "starters": [
                    "So I…",
                    "What I did next was…",
                    "I decided to…",
                ],
            },
            {
                "id": "resolution",
                "name": "Resolution",
                "description": "How it ended, plus the takeaway or insight.",
                "expected_tense": "past_or_present_perfect",
                "starters": [
                    "In the end,…",
                    "What I learned was…",
                    "Looking back,…",
                ],
            },
        ],
        "scoring_rubric": {
            "must_include_metric": None,
            "self_attribution_required": False,
        },
        "prompts": [
            {
                "id": "story_1",
                "text": "Tell a short story about a moment that changed how you think about your work.",
                "category": "lesson_learned",
            },
            {
                "id": "story_2",
                "text": "Tell a story about a mistake you made and what you took away from it.",
                "category": "mistake",
            },
            {
                "id": "story_3",
                "text": "Tell a story about how you started in your field.",
                "category": "origin",
            },
            {
                "id": "story_4",
                "text": "Tell a story about a small win that meant more than it should have.",
                "category": "moment",
            },
        ],
    },
}


def get_framework(framework_id: str) -> Optional[dict]:
    """Return the framework definition, or None if unknown."""
    return FRAMEWORKS.get(framework_id)


def list_frameworks() -> list[dict]:
    """Return all frameworks as a list, preserving declaration order."""
    return list(FRAMEWORKS.values())


def get_prompt(framework_id: str, prompt_id: str) -> Optional[dict]:
    """Return a specific prompt within a framework, or None if not found."""
    framework = FRAMEWORKS.get(framework_id)
    if framework is None:
        return None
    for prompt in framework["prompts"]:
        if prompt["id"] == prompt_id:
            return prompt
    return None


def get_slot(framework_id: str, slot_id: str) -> Optional[dict]:
    """Return a specific slot within a framework, or None if not found."""
    framework = FRAMEWORKS.get(framework_id)
    if framework is None:
        return None
    for slot in framework["slots"]:
        if slot["id"] == slot_id:
            return slot
    return None
