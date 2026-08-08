# StudySprinter — Backend

REST API that takes user notes and returns AI-generated summaries, flashcards, and quizzes. Paste your notes, get a study set back — with structured, validated output, retry handling for API failures, and an automated eval suite to catch regressions when the prompt or model changes.

## Stack

- **Python 3.12 / FastAPI** — async REST API
- **OpenAI API (gpt-4o)** — generation, using schema-constrained structured outputs (`.beta.chat.completions.parse()`)
- **Pydantic** — request/response validation and the generation schema itself
- **Supabase (Postgres + Auth)** — persistence and authentication
- **React** (separate repo/folder) — frontend, with a guest mode that mirrors the authenticated API shape via localStorage

## Architecture

```
React frontend
   │
   │  POST /generate  (with or without auth token)
   ▼
FastAPI backend
   │
   ├─ validates input (non-empty, 300+ char minimum)
   │
   ├─ calls OpenAI with a Pydantic-defined schema (StudySetResponse)
   │     └─ retries on rate limit / timeout / transient API errors
   │
   ├─ shuffles quiz answer order (re-indexing the correct answer)
   │
   └─ if authenticated: persists to Supabase (study_sets, flashcards, quiz_questions)
      if guest: returns a generated UUID, frontend stores it in localStorage
```

Guest and authenticated users hit the same `/generate` endpoint and get back the same response shape — the frontend's `guestStorage.js` deliberately mirrors the shape of the authenticated API responses, so the rest of the UI doesn't need to know or care which mode it's in.

## Key design decisions

**Schema-constrained output over free-text JSON parsing.**
Generation uses `client.beta.chat.completions.parse()` with a Pydantic `StudySetResponse` schema, rather than requesting `json_object` mode and manually calling `json.loads()` on the result. The earlier approach could throw an unhandled `KeyError`/`IndexError` if the model omitted a field or changed shape slightly — with schema-constrained output, the response is guaranteed to match the expected structure or the call fails cleanly, with a specific error rather than a downstream crash.

**Retry logic with error-type awareness.**
The OpenAI call is wrapped in a retry loop that distinguishes rate limits (retry with exponential backoff) from other transient API errors (short retry) from genuinely unparseable output (fail fast, retrying won't help). After exhausting retries, the endpoint returns a 502 with a message that's honest about the two real causes — insufficient/unclear input content, or a temporary issue with the AI service — rather than a message that implies retrying will always fix it.

**Server-side input validation, not just frontend.**
The frontend enforces a 300-character minimum on notes before allowing generation. Initially, that check only existed in the React component — meaning anyone calling `/generate` directly (via the API docs, a script, or a modified frontend) could bypass it entirely and submit near-empty input, wasting an API call on a doomed generation. The same check now exists server-side, so the rule holds regardless of how the endpoint is called. This is a general principle, not specific to this app: frontend validation is for UX, backend validation is what actually protects the system.

**JWT verification fix.**
The original auth code decoded the JWT from the `Authorization` header without verifying its signature (`verify_signature: False`), meaning any caller could forge a token with an arbitrary user ID and act as that user. Auth now calls `supabase.auth.get_user(token)`, which verifies the token against Supabase itself before trusting the claimed identity.

**Specific exception handling instead of a single catch-all.**
The original `/generate` endpoint funneled every possible failure — bad input, OpenAI errors, database errors — into one generic `except Exception: return 500`, which returned raw exception text to the client and gave no way to distinguish failure causes. Each failure mode now has its own handling: bad input returns 400 with a clear message, AI generation failures return 502, database failures are logged in full detail server-side but return a generic message to the client (no internals leaked).

## Eval suite

`eval/` contains a small automated eval that runs real requests against a running instance of the API and checks the results — not just "does it return 200," but structural correctness (right card/question counts, valid answer indices, no duplicate flashcards) and content relevance (expected keywords present) for known-good input, alongside deliberate edge cases (empty input, too-short input, gibberish).

Run it with:

```bash
uvicorn main:app --reload &      # in one terminal
cd eval && python run_eval.py    # in another
```

Current result: 10/10 cases passing. This isn't a claim that the app handles all input well — it's a specific, bounded set of checks that catches the failure modes most likely to actually occur, and gives a fast way to check whether a prompt or model change made things better or worse.

## Known limitations

- **Content quality above the length threshold isn't checked.** The 300-character minimum is a length-based proxy for "enough real content," not a quality check. Sufficiently long but low-information or repetitive/padded text will still pass validation and reach the AI — the eval suite includes a case (`long_gibberish_input`) that demonstrates this: nonsense text padded past 300 characters still generates a full, well-formed (but meaningless) study set, since the app has no way to detect that the input lacked real content.
- **The generation failure message can't distinguish cause.** A 502 from `/generate` could mean the input had insufficient real content, or that OpenAI had a transient issue — the retry loop doesn't currently track which cause triggered the final failure, so the message covers both possibilities generically rather than specifically.
- **No caching.** Identical or near-identical notes regenerate from scratch every time, at full API cost.
- **Single model, no fallback.** If `gpt-4o` is unavailable, there's no fallback to a different model.
- **Eval only covers `/generate`.** `/import` and the stats/pin/delete endpoints have no automated test coverage yet.

## What I'd change at scale

- Cache generation results for identical/near-identical notes
- Run the eval suite in CI on every prompt or dependency change, to catch regressions before merge rather than manually
- Add a lightweight content-quality signal (e.g. detecting repetition or a too-narrow vocabulary) rather than relying on character count alone
- Rate-limit generation per user to control cost
- Extend eval coverage to `/import` and the authenticated endpoints

## Setup

```bash
python -m venv venv
source venv/bin/activate      # Mac/Linux
pip install -r requirements.txt
```

Add to `.env`:

```
OPENAI_API_KEY=sk-proj-your-key-here
SUPABASE_URL=your-supabase-url
SUPABASE_SERVICE_KEY=your-supabase-service-key
```

Run:

```bash
uvicorn main:app --reload
```

API at `http://localhost:8000`, interactive docs at `http://localhost:8000/docs`.

## Endpoints

| Method | Path                     | Description                                              |
| ------ | ------------------------ | -------------------------------------------------------- |
| GET    | `/`                      | Health check                                             |
| POST   | `/generate`              | Generate a study set from notes (guest or authenticated) |
| POST   | `/import`                | Import a guest-created deck into an account on sign-up   |
| GET    | `/study-sets`            | List a user's saved study sets                           |
| GET    | `/study-sets/{id}`       | Get a full study set                                     |
| DELETE | `/study-sets/{id}`       | Delete a study set                                       |
| PATCH  | `/study-sets/{id}/pin`   | Toggle pin status                                        |
| POST   | `/study-sets/{id}/stats` | Record a quiz attempt                                    |
| GET    | `/study-sets/{id}/stats` | Get stats for a study set                                |
| DELETE | `/account`               | Delete the authenticated user's account                  |
