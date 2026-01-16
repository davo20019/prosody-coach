"""Practice prompts for prosody training."""

# Built-in practice prompts organized by category
PRACTICE_PROMPTS = {
    # Stress practice - longer texts
    "stress": [
        {
            "id": "stress_1",
            "text": "I NEVER said she STOLE my MONEY. You must have MISUNDERSTOOD what I was TRYING to say. Let me EXPLAIN it again MORE clearly this time.",
            "tip": "Emphasize the capitalized words. Stressed words carry the main meaning.",
            "focus": "pitch, volume"
        },
        {
            "id": "stress_2",
            "text": "The IMPORTANT thing is to STAY CALM and THINK CLEARLY. When we PANIC, we make BAD decisions. Take a DEEP breath and FOCUS on what MATTERS most.",
            "tip": "Stress the key content words (nouns, verbs, adjectives). Reduce function words.",
            "focus": "volume, rhythm"
        },
        {
            "id": "stress_3",
            "text": "I THINK we should WAIT until TOMORROW before making any FINAL decisions. There's no RUSH, and we NEED more TIME to CONSIDER all the OPTIONS.",
            "tip": "Pause after 'I think' and before key decisions. Stress action words.",
            "focus": "pauses, pitch"
        },
    ],

    # Questions and intonation - longer texts with mixed patterns
    "intonation": [
        {
            "id": "intonation_1",
            "text": "Are you coming to the meeting tomorrow? I really hope you can make it. We have some important topics to discuss, and your input would be valuable.",
            "tip": "Rising intonation on the question, then neutral/falling on the statements.",
            "focus": "pitch"
        },
        {
            "id": "intonation_2",
            "text": "What time does the meeting start? I want to make sure I arrive early. Also, where is it being held? Is it in the main conference room?",
            "tip": "Falling intonation on WH-questions, rising on yes/no questions.",
            "focus": "pitch"
        },
        {
            "id": "intonation_3",
            "text": "You finished the project already? That's incredible! How did you manage to do it so fast? I thought it would take at least another week.",
            "tip": "Rising intonation shows surprise. Falling on WH-questions. Enthusiasm on exclamations.",
            "focus": "pitch"
        },
    ],

    # Professional/meeting scenarios - longer texts
    "professional": [
        {
            "id": "pro_1",
            "text": "Thank you for joining today's meeting. Let me share the agenda with you. First, we'll review last quarter's results. Then, we'll discuss our goals for the upcoming quarter. Finally, I'd like to open the floor for questions and suggestions.",
            "tip": "Warm tone, pause between agenda items. Use listing intonation (slight rise on each item except the last).",
            "focus": "tempo, pauses"
        },
        {
            "id": "pro_2",
            "text": "I understand your concern, and I appreciate you bringing this up. However, I think we should consider another approach. Let me explain why I believe this alternative could work better for our team and our timeline.",
            "tip": "Empathetic tone first, then confident. Pause before 'However' and before 'Let me explain'.",
            "focus": "pitch, pauses"
        },
        {
            "id": "pro_3",
            "text": "Based on the data we've collected over the past three months, I recommend we postpone the launch until next quarter. This will give us time to address the issues we've identified and ensure a more successful release.",
            "tip": "Confident, measured pace. Slow down on key recommendations. Stress 'recommend', 'postpone', 'successful'.",
            "focus": "tempo, volume"
        },
        {
            "id": "pro_4",
            "text": "Could you please clarify what you mean by that? I want to make sure I understand correctly before we move forward. It's important that we're all on the same page regarding the project requirements.",
            "tip": "Polite, curious tone on questions. Confident on statements. Pause before 'It's important'.",
            "focus": "pitch, tempo"
        },
    ],

    # Rhythm practice (reducing unstressed syllables) - longer texts
    "rhythm": [
        {
            "id": "rhythm_1",
            "text": "I want to go to the store to get some milk. Then I need to stop by the bank to deposit a check. After that, I'll probably grab a cup of coffee.",
            "tip": "Reduce 'to' to 'tuh', 'a' to 'uh'. Stress content words: WANT, GO, STORE, GET, MILK, NEED, STOP, BANK, DEPOSIT, CHECK, GRAB, CUP, COFFEE.",
            "focus": "rhythm"
        },
        {
            "id": "rhythm_2",
            "text": "She's going to be late for the meeting because she had to finish the report. He's going to be there early, but he's not going to wait for her.",
            "tip": "'Going to' becomes 'gonna', 'had to' becomes 'had tuh'. Stress: LATE, MEETING, FINISH, REPORT, EARLY, WAIT.",
            "focus": "rhythm"
        },
        {
            "id": "rhythm_3",
            "text": "I could have done it differently if I had known about the problem. You should have told me earlier, and we would have fixed it together.",
            "tip": "'Could have' → 'coulda', 'should have' → 'shoulda', 'would have' → 'woulda'. Reduce 'if I had' to 'if I'd'.",
            "focus": "rhythm"
        },
    ],

    # Vowel reductions and schwa practice
    "reductions": [
        {
            "id": "reductions_1",
            "text": "I need a comfortable chair for my office. The vegetable soup was delicious, and the chocolate cake was interesting. It was definitely memorable.",
            "tip": "Reduce: COMFterble (not com-for-ta-ble), VEJtable (not veg-e-ta-ble), CHOClit (not choc-o-late), INtresting (not in-ter-est-ing), DEFnitly (not def-i-nite-ly), MEMrable (not mem-or-a-ble).",
            "focus": "rhythm"
        },
        {
            "id": "reductions_2",
            "text": "I want to go to a restaurant for dinner. Can you give me a cup of water? I'd like to order a salad and a sandwich.",
            "tip": "Reduce function words: 'to' → 'tuh', 'a' → 'uh', 'for' → 'fer', 'of' → 'uv', 'and' → 'n'. These should be quick and unstressed.",
            "focus": "rhythm"
        },
        {
            "id": "reductions_3",
            "text": "What do you want to do today? I was going to ask him, but he had to leave early. She could have told us about the problem.",
            "tip": "'want to' → 'wanna', 'going to' → 'gonna', 'had to' → 'had tuh', 'could have' → 'coulda'. Don't pronounce every syllable clearly.",
            "focus": "rhythm"
        },
        {
            "id": "reductions_4",
            "text": "The photograph was beautiful. She's studying photography at the university. The photographic equipment is expensive.",
            "tip": "Notice stress shift: PHOtograph → phoTOGraphy → photoGRAphic. Unstressed syllables become schwa (uh). The vowels change completely based on stress.",
            "focus": "rhythm, pitch"
        },
        {
            "id": "reductions_5",
            "text": "It's probably going to rain tomorrow. Actually, I think we should definitely cancel the barbecue. Everyone was planning to come, but the weather looks terrible.",
            "tip": "Reduce: PROBly (not prob-ab-ly), ACTchully (not ac-tu-al-ly), DEFnitly (not def-i-nite-ly), BARbkyoo (not bar-be-cue), EVryone (not ev-er-y-one).",
            "focus": "rhythm"
        },
    ],

    # Longer passages for sustained practice
    "passages": [
        {
            "id": "passage_1",
            "text": "Good morning everyone. Today I'd like to discuss our quarterly results. As you can see from the chart, we've exceeded our targets in three key areas. Let me walk you through each one.",
            "tip": "Vary your pace: slower on key numbers, faster on transitions. Pause between sentences.",
            "focus": "tempo, pauses"
        },
        {
            "id": "passage_2",
            "text": "I appreciate your feedback on this proposal. While I understand the concerns you've raised, I believe the benefits outweigh the risks. Let me explain why I think this approach will work.",
            "tip": "Acknowledge tone first, then confident assertion. Strategic pauses before 'While' and 'Let me'.",
            "focus": "pitch, pauses"
        },
    ],
}


def get_prompt_by_id(prompt_id: str) -> dict | None:
    """Get a specific prompt by its ID."""
    for category, prompts in PRACTICE_PROMPTS.items():
        for prompt in prompts:
            if prompt["id"] == prompt_id:
                return prompt
    return None


def get_prompts_by_category(category: str) -> list[dict]:
    """Get all prompts in a category."""
    return PRACTICE_PROMPTS.get(category, [])


def get_all_categories() -> list[str]:
    """Get list of all categories."""
    return list(PRACTICE_PROMPTS.keys())


def get_random_prompt(category: str = None) -> dict:
    """Get a random prompt, optionally from a specific category."""
    import random

    if category and category in PRACTICE_PROMPTS:
        prompts = PRACTICE_PROMPTS[category]
    else:
        # Get all prompts
        prompts = []
        for cat_prompts in PRACTICE_PROMPTS.values():
            prompts.extend(cat_prompts)

    return random.choice(prompts)


def list_all_prompts() -> list[dict]:
    """Get all prompts as a flat list with category info."""
    all_prompts = []
    for category, prompts in PRACTICE_PROMPTS.items():
        for prompt in prompts:
            all_prompts.append({**prompt, "category": category})
    return all_prompts
