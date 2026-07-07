from fastapi import FastAPI, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from openai import OpenAI
from supabase import create_client, Client
import json
import os
import random
import jwt
import uuid
from typing import Optional
from dotenv import load_dotenv

load_dotenv()

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


def get_user_id(authorization: str = Header(None)) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Not authenticated")
    token = authorization.split(" ")[1]
    try:
        payload = jwt.decode(token, options={"verify_signature": False})
        return payload.get("sub")
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token")


def get_optional_user_id(authorization: Optional[str]) -> Optional[str]:
    if not authorization or not authorization.startswith("Bearer "):
        return None
    try:
        token = authorization.split(" ")[1]
        payload = jwt.decode(token, options={"verify_signature": False})
        return payload.get("sub")
    except Exception:
        return None


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


@app.post("/generate")
def generate_study_set(body: NotesRequest, authorization: Optional[str] = Header(None)):
    user_id = get_optional_user_id(authorization)

    if not body.notes.strip():
        raise HTTPException(status_code=400, detail="Notes cannot be empty")

    prompt = f"""You are a study assistant. Generate study materials STRICTLY based on the provided notes only. Do NOT invent, assume, or add any information not explicitly present in the notes. For each quiz question, double check that the correct index accurately points to the right answer. Return ONLY valid JSON with this exact structure:
{{
  "summary": "3-4 sentence plain-English summary of the key concepts",
  "flashcards": [
    {{"q": "question", "a": "answer"}},
    {{"q": "question", "a": "answer"}},
    {{"q": "question", "a": "answer"}},
    {{"q": "question", "a": "answer"}},
    {{"q": "question", "a": "answer"}},
    {{"q": "question", "a": "answer"}},
    {{"q": "question", "a": "answer"}},
    {{"q": "question", "a": "answer"}},
    {{"q": "question", "a": "answer"}},
    {{"q": "question", "a": "answer"}}
  ],
  "quiz": [
    {{"q": "Multiple choice question?", "options": ["Option A", "Option B", "Option C", "Option D"], "correct": 0}},
    {{"q": "Multiple choice question?", "options": ["Option A", "Option B", "Option C", "Option D"], "correct": 1}},
    {{"q": "Multiple choice question?", "options": ["Option A", "Option B", "Option C", "Option D"], "correct": 2}},
    {{"q": "Multiple choice question?", "options": ["Option A", "Option B", "Option C", "Option D"], "correct": 3}},
    {{"q": "Multiple choice question?", "options": ["Option A", "Option B", "Option C", "Option D"], "correct": 0}},
    {{"q": "Multiple choice question?", "options": ["Option A", "Option B", "Option C", "Option D"], "correct": 1}},
    {{"q": "Multiple choice question?", "options": ["Option A", "Option B", "Option C", "Option D"], "correct": 2}},
    {{"q": "Multiple choice question?", "options": ["Option A", "Option B", "Option C", "Option D"], "correct": 3}},
    {{"q": "Multiple choice question?", "options": ["Option A", "Option B", "Option C", "Option D"], "correct": 0}},
    {{"q": "Multiple choice question?", "options": ["Option A", "Option B", "Option C", "Option D"], "correct": 1}}
  ]
}}

Notes:
{body.notes}"""

    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            max_tokens=2500,
        )
        data = json.loads(response.choices[0].message.content)

        shuffled_quiz = []
        quiz_to_insert = []

        for i, q in enumerate(data["quiz"]):
            options = q["options"]
            correct_answer = options[q["correct"]]
            random.shuffle(options)
            new_correct_index = options.index(correct_answer)
            quiz_to_insert.append({
                "question": q["q"],
                "options": options,
                "correct_index": new_correct_index,
                "position": i
            })
            shuffled_quiz.append({
                "q": q["q"],
                "options": options,
                "correct": new_correct_index
            })

        if user_id:
            study_set = supabase.table("study_sets").insert({
                "title": body.title,
                "notes": body.notes,
                "summary": data["summary"],
                "user_id": user_id
            }).execute()

            study_set_id = study_set.data[0]["id"]
            created_at = study_set.data[0]["created_at"]

            flashcards_to_insert = [
                {"study_set_id": study_set_id, "question": fc["q"], "answer": fc["a"], "position": i}
                for i, fc in enumerate(data["flashcards"])
            ]
            supabase.table("flashcards").insert(flashcards_to_insert).execute()

            for item in quiz_to_insert:
                item["study_set_id"] = study_set_id
            supabase.table("quiz_questions").insert(quiz_to_insert).execute()

        else:
            study_set_id = str(uuid.uuid4())
            created_at = None

        return {
            "id": study_set_id,
            "title": body.title,
            "summary": data["summary"],
            "flashcards": data["flashcards"],
            "quiz": shuffled_quiz,
            "created_at": created_at,
            "notes": body.notes
        }

    except json.JSONDecodeError:
        raise HTTPException(status_code=500, detail="AI returned invalid JSON")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/import")
def import_deck(body: ImportRequest, authorization: Optional[str] = Header(None)):
    user_id = get_user_id(authorization)

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

    return {"status": "imported", "id": study_set_id}


@app.get("/study-sets")
def get_study_sets(authorization: Optional[str] = Header(None)):
    user_id = get_user_id(authorization)
    result = supabase.table("study_sets").select("id, title, summary, created_at, pinned").eq("user_id", user_id).order("pinned", desc=True).order("created_at", desc=True).execute()
    decks = result.data
    for deck in decks:
        stats = supabase.table("deck_stats").select("reviewed_at").eq("study_set_id", deck["id"]).order("reviewed_at", desc=True).limit(1).execute()
        deck["last_studied"] = stats.data[0]["reviewed_at"] if stats.data else None
    return decks


@app.get("/study-sets/{study_set_id}")
def get_study_set(study_set_id: str, authorization: Optional[str] = Header(None)):
    user_id = get_user_id(authorization)
    study_set = supabase.table("study_sets").select("*").eq("id", study_set_id).eq("user_id", user_id).single().execute()
    flashcards = supabase.table("flashcards").select("*").eq("study_set_id", study_set_id).order("position").execute()
    quiz = supabase.table("quiz_questions").select("*").eq("study_set_id", study_set_id).order("position").execute()

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
