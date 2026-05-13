"""Helpers for web spaced-repetition updates after recorded practice."""

import re
from collections.abc import Callable
from typing import Any, Optional

from storage import normalize_sound_name


def update_practiced_due_words(
    expected_text: Optional[str],
    pronunciation_issues: Optional[list[dict]],
    get_due_words: Callable[[int], list[dict]],
    update_word_after_practice: Callable[[str, bool], None],
) -> None:
    if not expected_text:
        return

    practiced_words = set(re.findall(r"[a-z]+", expected_text.lower()))
    if not practiced_words:
        return

    flagged_words = set()
    for issue in pronunciation_issues or []:
        example = (issue or {}).get("example", "").lower()
        match = re.match(r"^([a-z]+)", example)
        if match:
            flagged_words.add(match.group(1))

    for due_word in get_due_words(limit=100):
        word = (due_word.get("word") or "").strip().lower()
        if word and word in practiced_words:
            update_word_after_practice(word, word not in flagged_words)


def update_practiced_target_sounds(
    target_sounds: Optional[list[Any]],
    pronunciation_issues: Optional[list[dict]],
    update_sound_after_practice: Callable[[str, bool], None],
) -> None:
    if not target_sounds:
        return

    flagged_sounds = {
        normalize_sound_name((issue or {}).get("sound", ""))
        for issue in pronunciation_issues or []
    }

    seen = set()
    for target in target_sounds:
        sound = target.get("sound", "") if isinstance(target, dict) else str(target)
        normalized = normalize_sound_name(sound)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        update_sound_after_practice(sound, normalized not in flagged_sounds)
