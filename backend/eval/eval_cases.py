"""
Eval cases for StudySprinter's /generate endpoint.

Each case is a set of notes plus what we expect a "good" result to look like.
This isn't exhaustive testing: it's a small, deliberately varied set that
catches the failure modes most likely to actually happen: too-short notes,
notes with no real content, very long notes, notes about niche/ambiguous
topics, and duplicate/malformed output.

Updated after adding a server-side 300-character minimum (mirroring the
frontend's existing rule): cases that used to test "short but valid" or
"gibberish" content now correctly expect a 400, since anything genuinely
short/low-effort will fail the length check before it ever reaches the AI.
"""

EVAL_CASES = [
    {
        "name": "standard_science_topic",
        "notes": "Photosynthesis is the process by which plants, algae, and some bacteria convert light energy into chemical energy. It occurs primarily in the chloroplasts of plant cells, specifically using a pigment called chlorophyll which absorbs light, mostly in the blue and red wavelengths. The overall process uses carbon dioxide from the air and water absorbed by the roots, and produces glucose and oxygen as a byproduct.",
        "title": "Photosynthesis",
        "expect_keywords": ["chlorophyll", "glucose", "oxygen"],
        "min_flashcards": 10,
        "min_quiz": 10,
    },
    {
        "name": "standard_history_topic",
        "notes": "The French Revolution began in 1789 and fundamentally transformed France's political and social structure. It was driven by frustration with the absolute monarchy under King Louis XVI, financial crisis from war debts, and inequality between the nobility and the Third Estate. The storming of the Bastille on July 14, 1789 became a symbolic turning point.",
        "title": "French Revolution",
        "expect_keywords": ["Bastille", "1789", "Louis XVI"],
        "min_flashcards": 10,
        "min_quiz": 10,
    },
    {
        "name": "just_over_minimum_length",
        "notes": "Mitochondria are the powerhouse of the cell. They generate ATP through cellular respiration, converting nutrients into usable energy for the cell to function. Mitochondria have their own DNA, separate from the cell's nucleus, and are believed to have originated from ancient free-living bacteria through a process called endosymbiosis billions of years ago.",
        "title": "Mitochondria",
        "expect_keywords": ["ATP", "mitochondria"],
        "min_flashcards": 5,
        "min_quiz": 5,
    },
    {
        "name": "notes_with_numbers_and_dates",
        "notes": "World War II lasted from 1939 to 1945. It began when Germany invaded Poland on September 1, 1939. The war involved over 30 countries and resulted in an estimated 70-85 million deaths, making it the deadliest conflict in human history. The war ended in Europe on May 8, 1945 (V-E Day) and in the Pacific on September 2, 1945 (V-J Day).",
        "title": "WWII Overview",
        "expect_keywords": ["1939", "1945"],
        "min_flashcards": 10,
        "min_quiz": 10,
    },
    {
        "name": "gibberish_input",
        "notes": "asdkjh aksjdh aksjdha skjdh aksjdh aksjdha skjdha skjdh aksjdha skjdh aksjdha skjdh aksjdha skjdha skdjha skdjha skjdha skjdha skdjha skjdha skjdha skjdhaksjdh aksjdha skdjha skjdha skjdha skjdha",
        "title": "Nonsense",
        "expect_error": True,
    },
    {
        "name": "very_short_repetitive_notes",
        "notes": "The sky is blue. The sky is blue. The sky is blue. The sky is blue. The sky is blue. The sky is blue. The sky is blue. The sky is blue. The sky is blue. The sky is blue.",
        "title": "Sky Color",
        "expect_error": True,
    },
    {
        "name": "long_gibberish_input",
        "notes": "asdkjh aksjdh aksjdha skjdh aksjdh aksjdha skjdha skjdh aksjdha skjdh aksjdha skjdh aksjdha skjdha skdjha skdjha skjdha skjdha skdjha skjdha skjdha skjdhaksjdh aksjdha skdjha skjdha skjdha skjdha kjashdkajshd kajshdkajshd kajshdkjahsd kajshdkajshd kajshdkjahsdkjahsd kajshdkajshdkjahsd kajshdkajshdkjashd kajshdkjahsdkjahsd",
        "title": "Long Nonsense",
        "expect_graceful_handling": True,
        "min_flashcards": 0,
        "min_quiz": 0,
    },
    {
        "name": "empty_notes",
        "notes": "",
        "title": "Empty",
        "expect_error": True,
    },
    {
        "name": "whitespace_only_notes",
        "notes": "     \n\n   \t  ",
        "title": "Whitespace",
        "expect_error": True,
    },
    {
        "name": "under_minimum_length",
        "notes": "This is short.",
        "title": "Too Short",
        "expect_error": True,
    },
]
