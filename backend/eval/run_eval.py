"""
Runs the eval cases in eval_cases.py against a running StudySprinter backend.

Usage:
    1. Make sure the backend is running: uvicorn main:app --reload
    2. From the backend folder, run: python run_eval.py

This hits /generate directly over HTTP (no auth token — guest mode),
same as a real unauthenticated user would.
"""

import requests
from eval_cases import EVAL_CASES

BACKEND_URL = "http://localhost:8000"


def check_case(case: dict, response) -> tuple[bool, str]:
    """Returns (passed, reason)."""

    if case.get("expect_error"):
        if response.status_code == 400:
            return True, "correctly rejected with 400"
        return False, f"expected 400, got {response.status_code}"

    if response.status_code != 200:
        return False, f"expected 200, got {response.status_code}: {response.text[:200]}"

    data = response.json()

    flashcards = data.get("flashcards", [])
    quiz = data.get("quiz", [])

    if case.get("expect_graceful_handling"):
        # We're not demanding quality here, just that it didn't crash
        # and returned a well-formed (if maybe low-value) response.
        if not isinstance(flashcards, list) or not isinstance(quiz, list):
            return False, "response missing flashcards/quiz lists"
        return True, f"handled gracefully ({len(flashcards)} cards, {len(quiz)} quiz Qs)"

    min_fc = case.get("min_flashcards", 1)
    min_quiz = case.get("min_quiz", 1)

    if len(flashcards) < min_fc:
        return False, f"expected >= {min_fc} flashcards, got {len(flashcards)}"
    if len(quiz) < min_quiz:
        return False, f"expected >= {min_quiz} quiz questions, got {len(quiz)}"

    # Check every quiz question has exactly 4 options and a valid correct index
    for i, q in enumerate(quiz):
        opts = q.get("options", [])
        if len(opts) != 4:
            return False, f"quiz question {i} has {len(opts)} options, expected 4"
        if not (0 <= q.get("correct", -1) < 4):
            return False, f"quiz question {i} has invalid correct index"

    # Check for duplicate flashcard questions (a real quality issue if it happens)
    questions = [fc["q"].strip().lower() for fc in flashcards]
    if len(questions) != len(set(questions)):
        return False, "duplicate flashcard questions detected"

    # Check expected keywords show up somewhere in the generated content
    if "expect_keywords" in case:
        all_text = " ".join(
            [data.get("summary", "")]
            + [fc["q"] + " " + fc["a"] for fc in flashcards]
        ).lower()
        missing = [kw for kw in case["expect_keywords"] if kw.lower() not in all_text]
        if missing:
            return False, f"missing expected keywords: {missing}"

    return True, f"{len(flashcards)} flashcards, {len(quiz)} quiz questions, all valid"


def run():
    results = []
    for case in EVAL_CASES:
        try:
            response = requests.post(
                f"{BACKEND_URL}/generate",
                json={"notes": case["notes"], "title": case["title"]},
                timeout=60,
            )
            passed, reason = check_case(case, response)
        except requests.exceptions.RequestException as e:
            passed, reason = False, f"request failed: {e}"

        results.append((case["name"], passed, reason))
        status = "PASS" if passed else "FAIL"
        print(f"[{status}] {case['name']}: {reason}")

    total = len(results)
    passed_count = sum(1 for _, p, _ in results if p)
    print(f"\n{passed_count}/{total} passed")

    return results


if __name__ == "__main__":
    run()
