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


# =============================================================================
# Rhythm Training Drills
# =============================================================================
# Structured 6-level progression for improving English stress-timed rhythm
# Each drill has specific focus and technique tips

RHYTHM_DRILLS = {
    # Level 1: Word Stress Patterns (nPVI target: 45+)
    # Focus: Learning basic stressed vs unstressed syllable patterns
    "level_1": [
        {
            "id": "l1_01",
            "text": "today, because, above, begin, about",
            "ipa": "təˈdeɪ, bɪˈkɔz, əˈbʌv, bɪˈɡɪn, əˈbaʊt",
            "pattern": "oO",  # unstressed-STRESSED
            "focus": "Two-syllable words with second syllable stress",
            "tip": "The second syllable is LOUDER, LONGER, and HIGHER in pitch. Stretch it like a rubber band.",
            "technique": "Hyper-pronunciation with rubber band: Hold an imaginary rubber band between your hands. On the first syllable, keep hands together (tə-). On the second syllable, stretch the band wide (DAY!). Make the stretched syllable 2x longer, noticeably louder, and raise your pitch. Physical cue: Nod slightly on the stressed syllable. Practice: Say it wrong first (TO-day), then correct (tə-DAY) to feel the difference.",
            "priority": 1,  # Essential: Most common pattern
        },
        {
            "id": "l1_02",
            "text": "happy, water, picture, better, summer",
            "ipa": "ˈhæpi, ˈwɔːtər, ˈpɪktʃər, ˈbetər, ˈsʌmər",
            "pattern": "Oo",  # STRESSED-unstressed
            "focus": "Two-syllable words with first syllable stress",
            "tip": "The first syllable is strong. Let the second syllable become weak and quick.",
            "technique": "Front-weighted punch: Hit the first syllable like a boxer's jab - quick, sharp, powerful. Then let the second syllable trail off like an echo. The second syllable should feel almost swallowed. Physical cue: Tap your desk on the first syllable only. Timing test: The stressed syllable should be roughly 2x the duration of the unstressed one. Practice: Clap on 'HAP-' (loud), whisper '-py' (quiet).",
            "priority": 1,  # Essential: Most common pattern
        },
        {
            "id": "l1_03",
            "text": "computer, banana, tomorrow, important, together",
            "ipa": "kəmˈpjuːtər, bəˈnænə, təˈmɔroʊ, ɪmˈpɔrtənt, təˈɡeðər",
            "pattern": "oOo",  # unstressed-STRESSED-unstressed
            "focus": "Three-syllable words with middle stress",
            "tip": "Build up to the middle, then fade. com-PU-ter, not COM-pu-TER.",
            "technique": "Mountain pattern: Visualize climbing a hill - start low (com-), reach the peak at the middle (-PU-), descend (-ter). Your pitch should rise to the stressed syllable, then fall. Duration: The middle syllable should be longest. Volume: Middle syllable noticeably louder. Physical cue: Raise your hand as you climb to the stressed syllable, lower it after. Practice: Draw a mountain shape in the air as you say each word.",
            "priority": 1,  # Essential: Very common pattern
        },
        {
            "id": "l1_04",
            "text": "beautiful, wonderful, yesterday, different, family",
            "ipa": "ˈbjuːtɪfəl, ˈwʌndərfəl, ˈjestərdeɪ, ˈdɪfrənt, ˈfæməli",
            "pattern": "Ooo",  # STRESSED-unstressed-unstressed
            "focus": "Three-syllable words with first syllable stress",
            "tip": "Hit the first syllable hard, then rush through the rest. BEAU-ti-ful.",
            "technique": "Front-loaded stress: Power at the start",
        },
        {
            "id": "l1_05",
            "text": "understand, recommend, afternoon, seventeen, introduce",
            "ipa": "ˌʌndərˈstænd, ˌrekəˈmend, ˌæftərˈnuːn, ˌsevənˈtiːn, ˌɪntrəˈduːs",
            "pattern": "ooO",  # unstressed-unstressed-STRESSED
            "focus": "Three-syllable words with final stress",
            "tip": "Build anticipation through the first two syllables. Save the punch for the end.",
            "technique": "Delayed stress crescendo: Start low and quiet (un-der-), gradually rise in pitch and volume (-STAND). Imagine walking up stairs, landing firmly on the last step. Physical cue: Start with chin down, lift slightly on final syllable. Practice: Whisper first two syllables, speak final one normally.",
        },
        {
            "id": "l1_06",
            "text": "photograph, photography, photographic",
            "ipa": "ˈfoʊtəɡræf, fəˈtɑːɡrəfi, ˌfoʊtəˈɡræfɪk",
            "pattern": "variable",
            "focus": "Stress shift in word families",
            "tip": "PHO-to-graph → pho-TO-gra-phy → pho-to-GRA-phic. The stress moves!",
            "technique": "Word family contrast: Same root, different stress",
        },
        {
            "id": "l1_07",
            "text": "record (noun), record (verb), present (noun), present (verb)",
            "ipa": "ˈrekərd (n), rɪˈkɔrd (v), ˈprezənt (n), prɪˈzent (v)",
            "pattern": "variable",
            "focus": "Noun vs verb stress patterns",
            "tip": "Nouns: stress on FIRST syllable (RE-cord). Verbs: stress on SECOND (re-CORD).",
            "technique": "Noun-verb pairs: First vs second syllable stress",
        },
        {
            "id": "l1_08",
            "text": "communication, information, education, organization",
            "ipa": "kəˌmjuːnɪˈkeɪʃən, ˌɪnfərˈmeɪʃən, ˌedʒʊˈkeɪʃən, ˌɔːrɡənɪˈzeɪʃən",
            "pattern": "oooOo",
            "focus": "Long words with -tion ending",
            "tip": "Always stress the syllable BEFORE -tion. com-mu-ni-CA-tion.",
            "technique": "-tion rule: Stress falls on the syllable before -tion",
            "priority": 1,  # Essential: Very common suffix pattern
        },
        {
            "id": "l1_09",
            "text": "ability, possibility, responsibility, availability",
            "ipa": "əˈbɪləti, ˌpɑːsəˈbɪləti, rɪˌspɑːnsəˈbɪləti, əˌveɪləˈbɪləti",
            "pattern": "oOooo",
            "focus": "Words ending in -ity",
            "tip": "Stress the syllable BEFORE -ity. a-BI-li-ty, not a-bi-LI-ty.",
            "technique": "-ity rule: Stress before the suffix",
        },
        {
            "id": "l1_10",
            "text": "democratic, economic, scientific, automatic",
            "ipa": "ˌdeməˈkrætɪk, ˌiːkəˈnɑːmɪk, ˌsaɪənˈtɪfɪk, ˌɔːtəˈmætɪk",
            "pattern": "ooOo",
            "focus": "Words ending in -ic",
            "tip": "Stress the syllable directly before -ic. de-mo-CRA-tic.",
            "technique": "-ic rule: Stress the syllable before -ic",
        },
        {
            "id": "l1_11",
            "text": "comfortable, vegetable, interesting, different, separate",
            "ipa": "ˈkʌmftəbəl, ˈvedʒtəbəl, ˈɪntrəstɪŋ, ˈdɪfrənt, ˈseprət",
            "pattern": "Oo(o)",
            "focus": "Words with syllable reduction",
            "tip": "These words lose a syllable in natural speech: COMF-ter-ble, VEJ-ta-ble, IN-tres-ting.",
            "technique": "Syllable reduction: Drop the weak vowel",
        },
        {
            "id": "l1_12",
            "text": "calendar, celebrate, desperate, temperature, general",
            "ipa": "ˈkæləndər, ˈseləbreɪt, ˈdespərət, ˈtemprətʃər, ˈdʒenrəl",
            "pattern": "Ooo",
            "focus": "More first-syllable stress with reduction",
            "tip": "CA-len-dar (not ca-LEN-dar), CEL-e-brate, DES-prit, TEM-pra-chur, GEN-ral.",
            "technique": "Natural reduction in rapid speech",
        },
    ],

    # Level 2: Function Word Reduction (nPVI target: 50+)
    # Focus: Reducing unstressed function words to schwa
    "level_2": [
        {
            "id": "l2_01",
            "text": "I want to go to the store.",
            "ipa": "aɪ ˈwɑnt tə ˈɡoʊ tə ðə ˈstɔr",
            "pattern": "reduction",
            "focus": "Reducing 'to' and 'the'",
            "tip": "'want to' → 'wanna', 'to the' → 'tuhthuh'. Stress WANT, GO, STORE.",
            "technique": "Function word stealth: Function words (to, the, a) should be nearly invisible - like ninjas between content words. How to reduce: (1) Cut duration in half - say 'to' so fast it's just 'tuh'. (2) Lower volume - function words are background, not foreground. (3) Use schwa /ə/ - replace clear vowels with the neutral 'uh' sound. Physical cue: Imagine whispering the function words while speaking the content words normally. Practice drill: Say 'WANT_GO_STORE' with pauses, then fill in the gaps with super-quick 'tuh' and 'thuh'.",
            "priority": 1,  # Essential: Most basic function word reduction
        },
        {
            "id": "l2_02",
            "text": "She gave it to him for a dollar.",
            "ipa": "ʃi ˈɡeɪv ɪt tə ˈhɪm fər ə ˈdɑlər",
            "pattern": "reduction",
            "focus": "Multiple function word reductions",
            "tip": "'gave it' → 'gavit', 'for a' → 'feruh'. Stress GAVE, HIM, DOLLAR.",
            "technique": "Content vs function contrast",
        },
        {
            "id": "l2_03",
            "text": "Can you tell me where the bank is?",
            "ipa": "kən jə ˈtel mi wer ðə ˈbæŋk ɪz",
            "pattern": "reduction",
            "focus": "Question word reductions",
            "tip": "'Can you' → 'cunyuh', 'bank is' → 'bankiz'. Stress TELL, BANK.",
            "technique": "Question blending",
        },
        {
            "id": "l2_04",
            "text": "I would have called you if I had known.",
            "ipa": "aɪ ˈwʊdəv ˈkɔld ju ɪf aɪd ˈnoʊn",
            "pattern": "reduction",
            "focus": "Auxiliary verb reductions",
            "tip": "'would have' → 'woulduv', 'called you' → 'caldjou'. Stress CALLED, KNOWN.",
            "technique": "Auxiliary contraction",
        },
        {
            "id": "l2_05",
            "text": "Do you want to come with us?",
            "ipa": "dʒə ˈwɑnə ˈkʌm wɪθ əs",
            "pattern": "reduction",
            "focus": "Common phrase reductions",
            "tip": "'Do you' → 'd'yuh', 'want to' → 'wanna', 'with us' → 'withus'. Stress COME.",
            "technique": "Phrase blending",
            "priority": 1,  # Essential: Very common reduction
        },
        {
            "id": "l2_06",
            "text": "He is going to be late for the meeting.",
            "ipa": "hiz ˈɡənə bi ˈleɪt fər ðə ˈmiːtɪŋ",
            "pattern": "reduction",
            "focus": "'Going to' reduction",
            "tip": "'going to' → 'gonna', 'for the' → 'fer thuh'. Stress LATE, MEETING.",
            "technique": "Gonna/wanna patterns",
            "priority": 1,  # Essential: Very common reduction
        },
        {
            "id": "l2_07",
            "text": "What are you doing at the moment?",
            "ipa": "ˈwɑdərjə ˈduːɪŋ ət ðə ˈmoʊmənt",
            "pattern": "reduction",
            "focus": "Present continuous reduction",
            "tip": "'What are you' → 'Whadarya', 'at the' → 'at thuh'. Stress DOING, MOMENT.",
            "technique": "Rapid question formation",
        },
        {
            "id": "l2_08",
            "text": "I have been waiting for an hour.",
            "ipa": "aɪv bɪn ˈweɪtɪŋ fərən ˈaʊər",
            "pattern": "reduction",
            "focus": "Perfect tense reductions",
            "tip": "'I have' → 'I've', 'for an' → 'fer'n'. Stress WAITING, HOUR.",
            "technique": "Perfect aspect blending",
        },
        {
            "id": "l2_09",
            "text": "cup of coffee, piece of cake, out of time",
            "ipa": "ˈkʌpə ˈkɔfi, ˈpiːsə ˈkeɪk, ˈaʊtə ˈtaɪm",
            "pattern": "reduction",
            "focus": "'Of' reduction patterns",
            "tip": "'of' → 'uh' (like 'cupuh coffee'). The 'of' nearly disappears.",
            "technique": "Linking through 'of'",
        },
        {
            "id": "l2_10",
            "text": "There are a lot of things to do.",
            "ipa": "ðərər ə ˈlɑtə ˈθɪŋz tə ˈduː",
            "pattern": "reduction",
            "focus": "Multiple reductions in one phrase",
            "tip": "'There are' → 'Therr', 'a lot of' → 'uhlottuv', 'to do' → 'tuh do'.",
            "technique": "Backward build-up: Start from 'do' and add words backward",
        },
        {
            "id": "l2_11",
            "text": "I was going to ask you if you wanted to come to the party with us.",
            "ipa": "aɪ wəz ˈɡənə ˈæsk jə ɪf jə ˈwɑntɪd tə ˈkʌm tə ðə ˈpɑrti wɪθ əs",
            "pattern": "reduction",
            "focus": "Extended reduction practice",
            "tip": "'was' → 'wuz', 'going to' → 'gonna', 'you' → 'yuh', 'wanted to' → 'wantedtuh', 'to the' → 'tuhthuh', 'with us' → 'withus'.",
            "technique": "Content vs function contrast",
            "priority": 1,
        },
        {
            "id": "l2_12",
            "text": "We should have told them that we were going to be late for the meeting.",
            "ipa": "wi ˈʃʊdəv ˈtoʊld ðəm ðət wi wər ˈɡənə bi ˈleɪt fər ðə ˈmiːtɪŋ",
            "pattern": "reduction",
            "focus": "Complex sentence reductions",
            "tip": "'should have' → 'shoulduv', 'them that' → 'thum thut', 'were going to' → 'wer gonna', 'for the' → 'fer thuh'.",
            "technique": "Auxiliary contraction",
            "priority": 1,
        },
        {
            "id": "l2_13",
            "text": "Can you give me a cup of coffee and a piece of cake?",
            "ipa": "kən jə ˈɡɪv mi ə ˈkʌpə ˈkɔfi ən ə ˈpiːsə ˈkeɪk",
            "pattern": "reduction",
            "focus": "'Of' and article reductions",
            "tip": "'Can you' → 'Cunyuh', 'a cup of' → 'uh cupuh', 'and a' → 'ən uh', 'a piece of' → 'uh pieceuh'.",
            "technique": "Linking through 'of'",
        },
        {
            "id": "l2_14",
            "text": "I have been trying to get a hold of him for the past couple of days.",
            "ipa": "aɪv bɪn ˈtraɪɪŋ tə ˈɡet ə ˈhoʊld əv ɪm fər ðə ˈpæst ˈkʌpəl əv ˈdeɪz",
            "pattern": "reduction",
            "focus": "Multiple 'of' reductions",
            "tip": "'I have' → 'I've', 'to get' → 'tuh get', 'a hold of' → 'uh holduh', 'of him' → 'uhvim', 'for the' → 'fer thuh', 'couple of' → 'coupluv'.",
            "technique": "Perfect aspect blending",
        },
    ],

    # Level 3: Compound Stress (nPVI target: 53+)
    # Focus: Understanding compound word stress patterns
    "level_3": [
        {
            "id": "l3_01",
            "text": "HOT dog (food) vs hot DOG (overheated animal)",
            "ipa": "ˈhɑt dɔɡ vs hɑt ˈdɔɡ",
            "pattern": "compound",
            "focus": "Compound noun vs adjective + noun",
            "tip": "Compounds stress the FIRST word. Adj+noun stress the SECOND.",
            "technique": "Contrastive pairs: Same words, different meanings",
            "priority": 1,  # Essential: Core compound stress rule
        },
        {
            "id": "l3_02",
            "text": "WHITE house (the building) vs white HOUSE (any white house)",
            "ipa": "ˈwaɪt haʊs vs waɪt ˈhaʊs",
            "pattern": "compound",
            "focus": "Proper noun compounds",
            "tip": "WHITE House = the president's home. white HOUSE = just a white building.",
            "technique": "Meaning determines stress",
        },
        {
            "id": "l3_03",
            "text": "blackboard, greenhouse, lighthouse, sunflower",
            "ipa": "ˈblækbɔrd, ˈɡriːnhaʊs, ˈlaɪthaʊs, ˈsʌnflaʊər",
            "pattern": "compound",
            "focus": "Single-stress compounds",
            "tip": "BLACKboard, GREENhouse, LIGHThouse, SUNflower. First element stressed.",
            "technique": "Compound noun stress rule",
            "priority": 1,  # Essential: Common compound words
        },
        {
            "id": "l3_04",
            "text": "ice cream, peanut butter, credit card, high school",
            "ipa": "ˈaɪs kriːm, ˈpiːnʌt bʌtər, ˈkredɪt kɑrd, ˈhaɪ skuːl",
            "pattern": "compound",
            "focus": "Two-word compound nouns",
            "tip": "ICE cream, PEAnut butter, CREDit card, HIGH school. First word carries stress.",
            "technique": "First-element stress",
        },
        {
            "id": "l3_05",
            "text": "She's a FRENCH teacher (from France) vs She's a French TEACHER (teaches French)",
            "ipa": "ʃiz ə ˈfrentʃ tiːtʃər vs ʃiz ə frentʃ ˈtiːtʃər",
            "pattern": "compound",
            "focus": "Nationality compounds",
            "tip": "FRENCH teacher = teacher from France. French TEACHER = teaches the language.",
            "technique": "Stress placement changes meaning",
        },
        {
            "id": "l3_06",
            "text": "makeup, breakdown, checkout, takeoff, workout",
            "ipa": "ˈmeɪkʌp, ˈbreɪkdaʊn, ˈtʃekaʊt, ˈteɪkɔf, ˈwɜrkaʊt",
            "pattern": "compound",
            "focus": "Phrasal verb nouns",
            "tip": "MAKEup, BREAKdown, CHECKout, TAKEoff, WORKout. Stress first syllable.",
            "technique": "Verb→noun stress shift",
        },
        {
            "id": "l3_07",
            "text": "baby-sitter, movie-goer, truth-teller, ice-breaker",
            "ipa": "ˈbeɪbi sɪtər, ˈmuːvi ɡoʊər, ˈtruːθ telər, ˈaɪs breɪkər",
            "pattern": "compound",
            "focus": "Agent compounds (-er)",
            "tip": "BAby-sitter, MOvie-goer, TRUTH-teller. First element stressed.",
            "technique": "Agent noun compounds",
        },
        {
            "id": "l3_08",
            "text": "She works in a TOY store. She has a toy POODLE.",
            "ipa": "ʃi wɜrks ɪn ə ˈtɔɪ stɔr. ʃi hæz ə tɔɪ ˈpuːdəl",
            "pattern": "compound",
            "focus": "Store names vs descriptions",
            "tip": "TOY store (sells toys) = compound. toy POODLE (type of dog) = adj+noun.",
            "technique": "Function-based stress",
        },
    ],

    # Level 4: Thought Groups (nPVI target: 55+)
    # Focus: Chunking sentences into natural phrase groups
    "level_4": [
        {
            "id": "l4_01",
            "text": "When I get home | I'll call you.",
            "ipa": "wen aɪ ɡet ˈhoʊm | aɪl ˈkɔːl ju",
            "pattern": "thought_groups",
            "focus": "Two-part conditional sentences",
            "tip": "Pause briefly at the |. Each chunk has its own stress peak.",
            "technique": "Phrase chunking: Group related words together",
            "priority": 1,  # Essential: Basic thought group pattern
        },
        {
            "id": "l4_02",
            "text": "In the morning | after breakfast | I usually go for a walk.",
            "ipa": "ɪn ðə ˈmɔːrnɪŋ | ˈæftər ˈbrekfəst | aɪ ˈjuːʒuəli ˈɡoʊ fər ə ˈwɔːk",
            "pattern": "thought_groups",
            "focus": "Multiple prepositional phrases",
            "tip": "Three chunks, three slight pauses. Main stress in each chunk: MORNING, BREAKFAST, WALK.",
            "technique": "Strategic pausing at phrase boundaries",
        },
        {
            "id": "l4_03",
            "text": "The report | which was submitted yesterday | needs revision.",
            "ipa": "ðə rɪˈpɔːrt | wɪtʃ wəz səbˈmɪtɪd ˈjestərdeɪ | niːdz rɪˈvɪʒən",
            "pattern": "thought_groups",
            "focus": "Relative clauses as inserts",
            "tip": "The relative clause is parenthetical - slightly lower pitch, faster pace.",
            "technique": "Parenthetical insertion",
        },
        {
            "id": "l4_04",
            "text": "First | open the file. | Then | save your changes. | Finally | close the window.",
            "ipa": "ˈfɜːrst | ˈoʊpən ðə ˈfaɪl | ˈðen | ˈseɪv jɔːr ˈtʃeɪndʒəz | ˈfaɪnəli | ˈkloʊz ðə ˈwɪndoʊ",
            "pattern": "thought_groups",
            "focus": "Instruction sequences",
            "tip": "Signal words (First, Then, Finally) get their own beat. Pause after each step.",
            "technique": "Instructional chunking",
        },
        {
            "id": "l4_05",
            "text": "I think | that we should wait | until tomorrow.",
            "ipa": "aɪ ˈθɪŋk | ðət wi ʃʊd ˈweɪt | ənˈtɪl təˈmɔroʊ",
            "pattern": "thought_groups",
            "focus": "Reported thought structure",
            "tip": "'I think' is an opener. 'that we should wait' is the main thought. 'until tomorrow' is the time frame.",
            "technique": "Topic-comment-time structure",
        },
        {
            "id": "l4_06",
            "text": "Despite the rain | and the cold weather | we decided to go.",
            "ipa": "dɪˈspaɪt ðə ˈreɪn | ənd ðə ˈkoʊld ˈweðər | wi dɪˈsaɪdɪd tə ˈɡoʊ",
            "pattern": "thought_groups",
            "focus": "Concession structures",
            "tip": "The obstacles (rain, cold) group together. The decision is separate. Pause before 'we decided'.",
            "technique": "Contrast marking with pauses",
        },
        {
            "id": "l4_07",
            "text": "The quick brown fox | jumps over | the lazy dog.",
            "ipa": "ðə ˈkwɪk ˈbraʊn ˈfɑːks | ˈdʒʌmps ˈoʊvər | ðə ˈleɪzi ˈdɔːɡ",
            "pattern": "thought_groups",
            "focus": "Subject-verb-object chunking",
            "tip": "Subject phrase | action | object phrase. Each is a natural chunk.",
            "technique": "Basic SVO chunking",
        },
        {
            "id": "l4_08",
            "text": "If you have any questions | please let me know.",
            "ipa": "ɪf ju hæv ˈeni ˈkwestʃənz | pliːz ˈlet mi ˈnoʊ",
            "pattern": "thought_groups",
            "focus": "Conditional politeness",
            "tip": "Condition first (longer), then request (shorter). Clear pause between them.",
            "technique": "Politeness structures",
        },
    ],

    # Level 5: Full Sentence Rhythm (nPVI target: 58+)
    # Focus: Applying stress-timing to complete sentences
    "level_5": [
        {
            "id": "l5_01",
            "text": "SCIENTISTS have DISCOVERED a NEW way to TREAT the DISEASE.",
            "ipa": "ˈsaɪəntɪsts həv dɪsˈkʌvərd ə ˈnuː weɪ tə ˈtriːt ðə dɪˈziːz",
            "pattern": "sentence_rhythm",
            "focus": "News headline rhythm",
            "tip": "Content words (CAPS) are stressed and longer. Function words rush between them.",
            "technique": "Shadowing: Imitate immediately after hearing the model",
            "priority": 1,  # Essential: Core sentence rhythm pattern
        },
        {
            "id": "l5_02",
            "text": "The MEETING has been MOVED to FRIDAY at THREE o'clock.",
            "ipa": "ðə ˈmiːtɪŋ həz bɪn ˈmuːvd tə ˈfraɪdeɪ ət ˈθriː əˈklɑk",
            "pattern": "sentence_rhythm",
            "focus": "Office announcement rhythm",
            "tip": "Key information (MEETING, MOVED, FRIDAY, THREE) gets stress. 'has been', 'to', 'at' are quick.",
            "technique": "Information hierarchy",
        },
        {
            "id": "l5_03",
            "text": "I'd LIKE to ORDER the CHICKEN with RICE and a SIDE SALAD.",
            "ipa": "aɪd ˈlaɪk tə ˈɔrdər ðə ˈtʃɪkən wɪθ ˈraɪs ənd ə ˈsaɪd ˈsæləd",
            "pattern": "sentence_rhythm",
            "focus": "Restaurant ordering",
            "tip": "Menu items (CHICKEN, RICE, SALAD) are stressed. 'I'd like to order the' is one quick chunk.",
            "technique": "Formulaic phrase + content rhythm",
        },
        {
            "id": "l5_04",
            "text": "The TRAIN to LONDON LEAVES from PLATFORM NINE at SEVEN FIFTEEN.",
            "ipa": "ðə ˈtreɪn tə ˈlʌndən ˈliːvz frəm ˈplætfɔrm ˈnaɪn ət ˈsevən fɪfˈtiːn",
            "pattern": "sentence_rhythm",
            "focus": "Travel announcement",
            "tip": "Critical info (TRAIN, LONDON, PLATFORM, NINE, SEVEN, FIFTEEN) is stressed. Articles are minimal.",
            "technique": "Essential information stress",
        },
        {
            "id": "l5_05",
            "text": "SORRY, but I DON'T THINK that's GOING to WORK for us.",
            "ipa": "ˈsɑri bət aɪ ˈdoʊnt ˈθɪŋk ðæts ˈɡoʊɪŋ tə ˈwɜrk fər əs",
            "pattern": "sentence_rhythm",
            "focus": "Polite disagreement",
            "tip": "SORRY softens, DON'T THINK and WORK are the core. 'that's going to' blends together.",
            "technique": "Diplomatic rhythm",
        },
        {
            "id": "l5_06",
            "text": "Could you PLEASE send me the REPORT by the END of the DAY?",
            "ipa": "kʊd ju ˈpliːz ˈsend mi ðə rɪˈpɔrt baɪ ðə ˈend əv ðə ˈdeɪ",
            "pattern": "sentence_rhythm",
            "focus": "Polite request",
            "tip": "'Could you' is quick, PLEASE gets slight stress, REPORT, END, DAY are peaks.",
            "technique": "Request formula rhythm",
        },
        {
            "id": "l5_07",
            "text": "WHAT a BEAUTIFUL DAY! Let's GO to the PARK and have a PICNIC.",
            "ipa": "ˈwɑt ə ˈbjuːtɪfəl ˈdeɪ! lets ˈɡoʊ tə ðə ˈpɑrk ənd hæv ə ˈpɪknɪk",
            "pattern": "sentence_rhythm",
            "focus": "Exclamation + suggestion",
            "tip": "Exclamation rises on BEAUTIFUL. Suggestion has peaks on GO, PARK, PICNIC.",
            "technique": "Emotional rhythm variation",
        },
        {
            "id": "l5_08",
            "text": "I've been WORKING on this PROJECT for THREE MONTHS now.",
            "ipa": "aɪv bɪn ˈwɜrkɪŋ ɑn ðɪs ˈprɑdʒekt fər ˈθriː ˈmʌnθs naʊ",
            "pattern": "sentence_rhythm",
            "focus": "Duration expression",
            "tip": "'I've been' is quick, WORKING, PROJECT, THREE, MONTHS are stressed. 'now' adds emphasis.",
            "technique": "Progressive aspect rhythm",
        },
    ],

    # Level 6: Connected Speech (nPVI target: 60+)
    # Focus: Natural reductions, linking, and elision
    "level_6": [
        {
            "id": "l6_01",
            "text": "I'm going to → I'm gonna",
            "ipa": "aɪm ˈɡoʊɪŋ tə → aɪm ˈɡənə",
            "pattern": "connected",
            "focus": "Gonna reduction",
            "tip": "'Going to' → 'gonna' in casual speech. 'I'm gonna go' not 'I am going to go'.",
            "technique": "Common contractions in flow",
            "priority": 1,  # Essential: Most common connected speech pattern
        },
        {
            "id": "l6_02",
            "text": "Do you want to → D'you wanna | Would you like to → Wouldja like to",
            "ipa": "du ju ˈwɑnt tu → dʒə ˈwɑnə | wʊd ju ˈlaɪk tu → ˈwʊdʒə ˈlaɪk tə",
            "pattern": "connected",
            "focus": "Question reductions",
            "tip": "'Do you want to' → 'D'yuh wanna', 'Would you' → 'Wouldja'. Super common in real speech.",
            "technique": "Casual question forms",
            "priority": 1,  # Essential: Very common question reduction
        },
        {
            "id": "l6_03",
            "text": "an apple, an orange, an egg, an hour",
            "ipa": "ən‿ˈæpəl, ən‿ˈɔrɪndʒ, ən‿ˈeɡ, ən‿ˈaʊər",
            "pattern": "connected",
            "focus": "Linking with 'an'",
            "tip": "The 'n' links to the vowel: 'ana-pple', 'ano-range'. No pause between words.",
            "technique": "Consonant-vowel linking",
        },
        {
            "id": "l6_04",
            "text": "black cat, big game, red dress, bad day",
            "ipa": "ˈblæk‿ˈkæt, ˈbɪɡ‿ˈɡeɪm, ˈred‿ˈdres, ˈbæd‿ˈdeɪ",
            "pattern": "connected",
            "focus": "Consonant assimilation",
            "tip": "Final consonant blends into the next word: 'blaccat', 'biggame'. One smooth unit.",
            "technique": "Final consonant linking",
        },
        {
            "id": "l6_05",
            "text": "last time, next day, must be, just now",
            "ipa": "ˈlæs‿ˈtaɪm, ˈneks‿ˈdeɪ, ˈmʌs‿bi, ˈdʒʌs‿ˈnaʊ",
            "pattern": "connected",
            "focus": "Cluster simplification",
            "tip": "When consonants meet, some disappear: 'las time', 'nex day'. Natural elision.",
            "technique": "Consonant cluster reduction",
        },
        {
            "id": "l6_06",
            "text": "Did you eat yet? → Jeet yet? | Got to go → Gotta go",
            "ipa": "dɪd ju ˈiːt jet → ˈdʒiːt jet | ɡɑt tə ˈɡoʊ → ˈɡɑtə ˈɡoʊ",
            "pattern": "connected",
            "focus": "Extreme reductions",
            "tip": "'Did you eat' → 'Jeet' in very casual speech. 'Got to' → 'gotta'. Recognize and produce.",
            "technique": "Informal speech patterns",
        },
        {
            "id": "l6_07",
            "text": "see it, go away, the end, so on",
            "ipa": "ˈsiː‿jɪt, ˈɡoʊ‿wəˈweɪ, ði‿ˈend, ˈsoʊ‿wɑn",
            "pattern": "connected",
            "focus": "Glide insertion",
            "tip": "Between vowels, add a glide: 'see-yit', 'go-waway'. Smooth transition between vowels.",
            "technique": "Vowel-vowel linking",
        },
        {
            "id": "l6_08",
            "text": "I don't know → I dunno | Because → Cuz | Probably → Prolly",
            "ipa": "aɪ ˈdoʊnt ˈnoʊ → aɪ ˈdənoʊ | bɪˈkɔz → kəz | ˈprɑbəbli → ˈprɑli",
            "pattern": "connected",
            "focus": "Common casual forms",
            "tip": "These are how natives actually speak casually. 'Dunno', 'cuz', 'prolly' are real words.",
            "technique": "Everyday reductions",
        },
        {
            "id": "l6_09",
            "text": "What do you think about it? → Whaddya think about it?",
            "ipa": "wɑt du ju ˈθɪŋk əˈbaʊt ɪt → ˈwɑdʒə ˈθɪŋk əˈbaʊt ɪt",
            "pattern": "connected",
            "focus": "Full sentence connected speech",
            "tip": "'What do you' → 'Whaddya' is one fast unit. Practice until it flows naturally.",
            "technique": "Phrase-level connection",
        },
        {
            "id": "l6_10",
            "text": "I would have thought that he could have done it better.",
            "ipa": "aɪ ˈwʊdəv ˈθɔːt ðət hi ˈkʊdəv ˈdʌn ɪt ˈbetər",
            "pattern": "connected",
            "focus": "Multiple auxiliary reductions",
            "tip": "'would have' → 'woulduv', 'could have' → 'coulduv'. Keep the meaning, lose the extra sounds.",
            "technique": "Perfect modal blending",
        },
    ],
}


def get_rhythm_drill(drill_id: str) -> dict | None:
    """Get a specific rhythm drill by its ID."""
    for level_key, drills in RHYTHM_DRILLS.items():
        for drill in drills:
            if drill["id"] == drill_id:
                level_num = int(level_key.split("_")[1])
                return {**drill, "level": level_num}
    return None


def get_rhythm_drills_by_level(level: int) -> list[dict]:
    """Get all drills for a specific level."""
    level_key = f"level_{level}"
    drills = RHYTHM_DRILLS.get(level_key, [])
    return [{**drill, "level": level} for drill in drills]


def get_random_rhythm_drill(level: int) -> dict | None:
    """Get a random drill from a specific level."""
    import random
    drills = get_rhythm_drills_by_level(level)
    if not drills:
        return None
    return random.choice(drills)


def get_all_rhythm_levels() -> list[int]:
    """Get list of all available rhythm training levels."""
    levels = []
    for key in RHYTHM_DRILLS.keys():
        level_num = int(key.split("_")[1])
        levels.append(level_num)
    return sorted(levels)
