import asyncio
import logging
import os
import random
import uuid
from typing import Optional

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from openai import OpenAI, APIError, APITimeoutError, RateLimitError
from pydantic import BaseModel
from supabase import create_client, Client

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("studyai")

app = FastAPI(title="StudyAI API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "https://studysprinter.vercel.app"],
    allow_methods=["*"],
    allow_headers=["*"],
)

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
supabase: Client = create_client(
    os.getenv("SUPABASE_URL"),
    os.getenv("SUPABASE_SERVICE_KEY")
)


# ---------------------------------------------------------------------------
# Auth helpers
#
# CHANGED: previously this decoded the JWT with verify_signature=False, which
# means any caller could forge a token with an arbitrary "sub" claim and act
# as any user. We now ask Supabase itself to validate the token server-side.
# ---------------------------------------------------------------------------

def _verify_token(token: str) -> Optional[str]:
    try:
        user_response = supabase.auth.get_user(token)
        if user_response and user_response.user:
            return user_response.user.id
        return None
    except Exception:
        return None


def get_user_id(authorization: str = Header(None)) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Not authenticated")
    token = authorization.split(" ")[1]
    user_id = _verify_token(token)
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token")
    return user_id


def get_optional_user_id(authorization: Optional[str]) -> Optional[str]:
    if not authorization or not authorization.startswith("Bearer "):
        return None
    token = authorization.split(" ")[1]
    return _verify_token(token)


# ---------------------------------------------------------------------------
# Request/response models
# ---------------------------------------------------------------------------

class NotesRequest(BaseModel):
    notes: str
    title: str = "Untitled Study Set"


class Flashcard(BaseModel):
    q: str
    a: str


class QuizQuestion(BaseModel):
    q: str
    options: list[str]
    correct: int


# CHANGED: this is the schema-constrained shape the OpenAI call now enforces
# via client.beta.chat.completions.parse(). Previously the code called
# json.loads() on free-form JSON and accessed data["quiz"], data["summary"]
# etc directly — if the model omitted a field or changed shape, that raised
# an unhandled KeyError/IndexError that fell through to a generic 500.
class StudySetResponse(BaseModel):
    summary: str
    flashcards: list[Flashcard]
    quiz: list[QuizQuestion]


class StatsRequest(BaseModel):
    quiz_score: int = None
    cards_reviewed: int = 0


class ImportRequest(BaseModel):
    title: str
    notes: str
    summary: str
    flashcards: list[dict]
    quiz: list[dict]
    best_score: Optional[int] = None
    times_reviewed: Optional[int] = None
    pinned: bool = False


@app.get("/")
@app.head("/")
def root():
    return {"status": "StudyAI backend is running"}


# ---------------------------------------------------------------------------
# Generation
# ---------------------------------------------------------------------------

def _build_prompt(notes: str) -> str:
    return f"""You are a study assistant. Generate study materials STRICTLY based on the provided notes only. Do NOT invent, assume, or add any information not explicitly present in the notes. For each quiz question, double check that the correct index accurately points to the right answer.

Generate:
- A 3-4 sentence plain-English summary of the key concepts
- Exactly 10 flashcards (question + answer)
- Exactly 10 multiple choice quiz questions, each with exactly 4 options and a correct index (0-3)

Notes:
{notes}"""


# CHANGED: previously a single client.chat.completions.create() call with no
# retry — any transient failure (rate limit, timeout, brief API hiccup)
# surfaced immediately as a 500. This retries transient failures with
# backoff and distinguishes retryable from non-retryable cases.
async def call_openai_with_retry(notes: str, max_retries: int = 3) -> StudySetResponse:
    prompt = _build_prompt(notes)
    last_error = None

    for attempt in range(max_retries):
        try:
            response = client.beta.chat.completions.parse(
                model="gpt-4o",
                messages=[{"role": "user", "content": prompt}],
                response_format=StudySetResponse,
                max_tokens=2500,
            )
            parsed = response.choices[0].message.parsed
            if parsed is None:
                raise ValueError("Model refused or returned unparseable output")
            return parsed

        except RateLimitError as e:
            last_error = e
            logger.warning(f"Rate limited on attempt {attempt + 1}/{max_retries}")
            if attempt < max_retries - 1:
                await asyncio.sleep(2 ** attempt)

        except (APITimeoutError, APIError) as e:
            last_error = e
            logger.warning(f"OpenAI API error on attempt {attempt + 1}/{max_retries}: {e}")
            if attempt < max_retries - 1:
                await asyncio.sleep(1)

        except ValueError as e:
            # Model returned something that didn't fit the schema at all.
            # Not worth retrying with the exact same prompt/input.
            last_error = e
            logger.error(f"Unparseable model output: {e}")
            break

    logger.error(f"Generation failed after {max_retries} attempts: {last_error}")
    raise HTTPException(
        status_code=502,
        detail="Study set generation failed. Please try again."
    )


@app.post("/generate")
async def generate_study_set(body: NotesRequest, authorization: Optional[str] = Header(None)):
    user_id = get_optional_user_id(authorization)

    if not body.notes.strip():
        raise HTTPException(status_code=400, detail="Notes cannot be empty")

    # This raises HTTPException(502) internally on failure, which FastAPI
    # will propagate as-is (see the except HTTPException passthrough below).
    data = await call_openai_with_retry(body.notes)

    shuffled_quiz = []
    quiz_to_insert = []

    for i, q in enumerate(data.quiz):
        options = list(q.options)
        if q.correct < 0 or q.correct >= len(options):
            # Defensive check: schema guarantees types, not that the index
            # is in range. Skip a malformed question rather than crash.
            logger.warning(f"Quiz question {i} had out-of-range correct index, skipping")
            continue
        correct_answer = options[q.correct]
        random.shuffle(options)
        new_correct_index = options.index(correct_answer)
        quiz_to_insert.append({
            "question": q.q,
            "options": options,
            "correct_index": new_correct_index,
            "position": i
        })
        shuffled_quiz.append({
            "q": q.q,
            "options": options,
            "correct": new_correct_index
        })

    try:
        if user_id:
            study_set = supabase.table("study_sets").insert({
                "title": body.title,
                "notes": body.notes,
                "summary": data.summary,
                "user_id": user_id
            }).execute()

            study_set_id = study_set.data[0]["id"]
            created_at = study_set.data[0]["created_at"]

            flashcards_to_insert = [
                {"study_set_id": study_set_id, "question": fc.q, "answer": fc.a, "position": i}
                for i, fc in enumerate(data.flashcards)
            ]
            supabase.table("flashcards").insert(flashcards_to_insert).execute()

            for item in quiz_to_insert:
                item["study_set_id"] = study_set_id
            supabase.table("quiz_questions").insert(quiz_to_insert).execute()

        else:
            study_set_id = str(uuid.uuid4())
            created_at = None

    except Exception as e:
        # A DB failure after a successful (and paid-for) generation call.
        # Logged with full detail server-side; client gets a generic message
        # rather than raw Supabase/Postgres internals.
        logger.error(f"Supabase write failed for /generate: {e}")
        raise HTTPException(status_code=500, detail="Failed to save study set. Please try again.")

    return {
        "id": study_set_id,
        "title": body.title,
        "summary": data.summary,
        "flashcards": [fc.model_dump() for fc in data.flashcards],
        "quiz": shuffled_quiz,
        "created_at": created_at,
        "notes": body.notes
    }


@app.post("/import")
def import_deck(body: ImportRequest, authorization: Optional[str] = Header(None)):
    user_id = get_user_id(authorization)

    try:
        study_set = supabase.table("study_sets").insert({
            "title": body.title,
            "notes": body.notes,
            "summary": body.summary,
            "user_id": user_id,
            "pinned": body.pinned
        }).execute()

        study_set_id = study_set.data[0]["id"]

        flashcards_to_insert = [
            {"study_set_id": study_set_id, "question": fc["q"], "answer": fc["a"], "position": i}
            for i, fc in enumerate(body.flashcards)
        ]
        supabase.table("flashcards").insert(flashcards_to_insert).execute()

        quiz_to_insert = [
            {
                "study_set_id": study_set_id,
                "question": q["q"],
                "options": q["options"],
                "correct_index": q["correct"],
                "position": i
            }
            for i, q in enumerate(body.quiz)
        ]
        supabase.table("quiz_questions").insert(quiz_to_insert).execute()

        if body.times_reviewed and body.times_reviewed > 0:
            supabase.table("deck_stats").insert({
                "study_set_id": study_set_id,
                "quiz_score": body.best_score,
                "cards_reviewed": 0
            }).execute()

    except Exception as e:
        logger.error(f"Supabase write failed for /import: {e}")
        raise HTTPException(status_code=500, detail="Failed to import deck. Please try again.")

    return {"status": "imported", "id": study_set_id}


@app.get("/study-sets")
def get_study_sets(authorization: Optional[str] = Header(None)):
    user_id = get_user_id(authorization)
    try:
        result = supabase.table("study_sets").select("id, title, summary, created_at, pinned").eq("user_id", user_id).order("pinned", desc=True).order("created_at", desc=True).execute()
        decks = result.data
        for deck in decks:
            stats = supabase.table("deck_stats").select("reviewed_at").eq("study_set_id", deck["id"]).order("reviewed_at", desc=True).limit(1).execute()
            deck["last_studied"] = stats.data[0]["reviewed_at"] if stats.data else None
        return decks
    except Exception as e:
        logger.error(f"Supabase read failed for /study-sets: {e}")
        raise HTTPException(status_code=500, detail="Failed to load study sets.")


@app.get("/study-sets/{study_set_id}")
def get_study_set(study_set_id: str, authorization: Optional[str] = Header(None)):
    user_id = get_user_id(authorization)
    try:
        study_set = supabase.table("study_sets").select("*").eq("id", study_set_id).eq("user_id", user_id).single().execute()
        flashcards = supabase.table("flashcards").select("*").eq("study_set_id", study_set_id).order("position").execute()
        quiz = supabase.table("quiz_questions").select("*").eq("study_set_id", study_set_id).order("position").execute()
    except Exception as e:
        logger.error(f"Supabase read failed for /study-sets/{study_set_id}: {e}")
        raise HTTPException(status_code=404, detail="Study set not found.")

    return {
        "id": study_set.data["id"],
        "title": study_set.data["title"],
        "summary": study_set.data["summary"],
        "notes": study_set.data["notes"],
        "created_at": study_set.data["created_at"],
        "flashcards": [{"q": fc["question"], "a": fc["answer"]} for fc in flashcards.data],
        "quiz": [{"q": q["question"], "options": q["options"], "correct": q["correct_index"]} for q in quiz.data]
    }


@app.delete("/study-sets/{study_set_id}")
def delete_study_set(study_set_id: str, authorization: Optional[str] = Header(None)):
    user_id = get_user_id(authorization)
    supabase.table("study_sets").delete().eq("id", study_set_id).eq("user_id", user_id).execute()
    return {"status": "deleted"}


@app.patch("/study-sets/{study_set_id}/pin")
def toggle_pin(study_set_id: str, authorization: Optional[str] = Header(None)):
    user_id = get_user_id(authorization)
    study_set = supabase.table("study_sets").select("pinned").eq("id", study_set_id).eq("user_id", user_id).single().execute()
    new_pinned = not study_set.data["pinned"]
    supabase.table("study_sets").update({"pinned": new_pinned}).eq("id", study_set_id).execute()
    return {"pinned": new_pinned}


@app.post("/study-sets/{study_set_id}/stats")
def record_stats(study_set_id: str, body: StatsRequest, authorization: Optional[str] = Header(None)):
    get_user_id(authorization)
    supabase.table("deck_stats").insert({
        "study_set_id": study_set_id,
        "quiz_score": body.quiz_score,
        "cards_reviewed": body.cards_reviewed
    }).execute()
    return {"status": "recorded"}


@app.get("/study-sets/{study_set_id}/stats")
def get_stats(study_set_id: str, authorization: Optional[str] = Header(None)):
    get_user_id(authorization)
    result = supabase.table("deck_stats").select("*").eq("study_set_id", study_set_id).order("reviewed_at", desc=True).execute()
    data = result.data
    if not data:
        return {
            "times_reviewed": 0,
            "best_score": None,
            "last_reviewed": None,
            "total_cards_revealed": 0
        }
    scores = [d["quiz_score"] for d in data if d["quiz_score"] is not None]
    return {
        "times_reviewed": len(data),
        "best_score": max(scores) if scores else None,
        "last_reviewed": data[0]["reviewed_at"],
        "total_cards_revealed": sum(d["cards_reviewed"] for d in data)
    }


@app.delete("/account")
def delete_account(authorization: Optional[str] = Header(None)):
    user_id = get_user_id(authorization)
    supabase.auth.admin.delete_user(user_id)
    return {"status": "account deleted"}
