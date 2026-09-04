# RAZE — Socratic AI Debugging Mentor for Python Developers

> **Tagline:** *"Don't copy the fix. Discover the bug."*

RAZE is an AI-powered Socratic debugging mentor designed specifically for Python beginners. It never immediately reveals the corrected code or the exact fix. Instead, it guides the user through an interactive 3-stage learning process (Observation & Question 1 → Diagnostic Question 2 → Complete Solution) where the user isolates the bug, tests hypotheses, and discovers the underlying mechanism themselves before the fix is revealed.

> **Note:** `main.py` (FastAPI) is the primary, canonical backend. A parallel Node/Express implementation (`server.ts`) also exists in this repo for historical reasons (see Section 14 of the handoff report) but is not the one this README documents.

---

## 1. Tech Stack

- **Backend:** Python 3.11+, FastAPI, Uvicorn
- **AI Service:** Google Gemini API (`google-genai` SDK)
- **Frontend:** Pure HTML5, CSS3, Vanilla JavaScript (no React, no TypeScript, no npm build step)
- **Syntax Highlighting:** Highlight.js (CDN)
- **Styling:** Custom CSS with a modern dark developer theme (`#0d1117`)

---

## 2. Architecture & File Structure

```
.
├── main.py                   # FastAPI app, routing, static/template mounting, rate limiting
├── config.py                 # Configuration settings and environment variables
├── models.py                 # Pydantic data schemas for requests and responses
├── requirements.txt          # Python dependencies
├── .env.example              # Example environment variables
├── README.md                 # Project documentation and setup guide
├── services/
│   ├── gemini_service.py     # Google GenAI API client and JSON parsing
│   ├── debug_engine.py       # 3-stage session state engine and heuristic fallbacks
│   └── code_runner.py        # Sandboxed subprocess execution of Python snippets
├── prompts/
│   └── system_prompts.py     # Strict Socratic LLM system prompts and stage builders
├── static/
│   ├── css/
│   │   └── style.css         # Dark theme custom stylesheet
│   └── js/
│       └── app.js            # Vanilla JS UI interaction and session management
└── templates/
    └── index.html            # Two-stage single page application template
```

---

## 3. The 3-Stage Senior-Dev Progression

RAZE strictly enforces the following sequence (`services/debug_engine.py`):

1. **OBSERVATION & QUESTION 1:** Analyzes code, error trace, expected vs. actual outcomes, and the code's *real* execution output (ground truth — the user's self-reported "actual result" is never blindly trusted). Highlights suspicious line numbers and asks one diagnostic question, without revealing the fix.
2. **DIAGNOSTIC QUESTION 2:** Briefly evaluates the answer to Question 1, then asks one final, focused diagnostic question.
3. **RESOLUTION:** No further questions. Delivers the full root-cause explanation, a hidden-problem breakdown, before/after code snippets, the corrected code, why the fix works, a reusable lesson, and a live re-execution of the corrected code to prove it actually works.

At any point, **"I'm Stuck"** returns one hint grounded in that session's own code and question — never a generic or unrelated example.

### "I'm Stuck" Button
In any stage, users can click **"I'm Stuck"** to receive progressive hints without breaking the learning loop. Full solutions are never dumped before Stage 8.

---

## 4. Quickstart & Setup

### Prerequisites
- Python 3.11+
- Google Gemini API Key

### Installation

1. **Clone or navigate to the repository:**
   ```bash
   cd raze
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure Environment:**
   Copy `.env.example` to `.env` and provide your Gemini API key:
   ```bash
   cp .env.example .env
   # Edit .env and set GEMINI_API_KEY=your_key_here
   ```

4. **Run the Application:**
   ```bash
   uvicorn main:app --host 0.0.0.0 --port 3000 --reload
   ```

5. **Open in Browser:**
   Navigate to [http://localhost:3000](http://localhost:3000).

---

## 5. API Endpoints

- `GET /` — Serves the two-stage interactive debugging web app.
- `GET /api/health` — Service health and Gemini configuration status.
- `GET /api/debug/stages` — Returns list of all 3 stages for stepper tracking.
- `POST /api/debug/start` — Starts a new debugging session.
  - Body: `{"code": "...", "error_message": null, "expected_result": "...", "actual_result": "..."}`
- `POST /api/debug/respond` — Submits user reflection and advances through the Socratic flow.
  - Body: `{"session_id": "...", "user_message": "...", "stage": "..."}`
- `POST /api/debug/stuck` — Handles progressive hint requests.
  - Body: `{"session_id": "...", "stage": "..."}`

---

