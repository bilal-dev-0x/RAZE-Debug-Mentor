# RAZE — AI Debugging Mentor

> **"A calm senior developer sitting beside the programmer, helping them understand what actually went wrong."**

RAZE is a Python-first, AI-powered debugging mentor web application built for beginner and intermediate developers. Unlike generic chatbots or terminal simulations, RAZE strictly enforces an absolute correctness chain:

$$\text{User Code} \rightarrow \text{Execution Evidence} \rightarrow \text{Observation} \rightarrow \text{Q1} \rightarrow \text{Answer 1} \rightarrow \text{Q2} \rightarrow \text{Answer 2} \rightarrow \text{5-Part Solution} + \text{Lesson}$$

---

## ✦ Core Architectural Pillars

### 1. Python-First, Single Backend Architecture
- **Single Source of Truth**: One FastAPI backend, Uvicorn server, Jinja2 templates, and vanilla JavaScript.
- **Zero Node.js, Zero React, Zero duplicate backends**: Eliminates competing server layers and state drift.

### 2. Strict Session Isolation (UUIDv4)
- Every new debugging session instantiates an isolated `DebugSession` object.
- **Client-Side Race Guard**: The frontend tags every outgoing request with the active `session_id` and immediately drops any asynchronous response that does not match the active session.
- **Zero State Bleed**: Clicking **"New Problem"** or **"Debug Another Problem"** flushes all state—editor, error, expected, actual, console, conversation, and solution cards.

### 3. Anti-Failure Safety & The Zero-Generic-Fallback Rule
- **Previous Failure Eliminated**: Older AI debuggers fell back to a hardcoded `numbers = [1, 2, 3, 4, 5]` loop mutation example whenever the AI was unreachable, leading to confusing and irrelevant responses.
- **Deterministic Current-Code Analyzer**: When the Gemini API is unreachable or not configured, RAZE executes an AST and traceback parser on the **user's actual submitted code**:
  - Automatically identifies runtime exceptions (`NameError`, `ZeroDivisionError`, `IndexError`, `SyntaxError`).
  - Detects variable typos by analyzing AST scope (e.g. `age` defined vs `ages` referenced).
  - Detects shallow copy bugs (`students.copy()`) and in-place list mutation during loops (`scores.remove(score)`).
- **Honest Feedback**: If the bug cannot be diagnosed safely via heuristics and AI is offline, RAZE honestly reports that deep AI synthesis is unavailable—**it will never fabricate confidence or return unrelated code**.

### 4. Enforced Stop Rule
- RAZE asks **Question 1**, receives your answer, asks **Question 2**, receives your answer, and then **STOPS**.
- No Question 3. No endless Socratic loops. The user immediately receives the comprehensive 5-part diagnosis:
  1. `01 — What I Found`: Root cause referring directly to your submitted code.
  2. `02 — What's Happening`: Runtime step-by-step mechanism.
  3. `03 — Root Cause`: Actual programming concept name.
  4. `04 — Corrected Code`: The fixed version of **your actual program**.
  5. `05 — Why This Fix Works`: Explanation of why the fix resolves the bug.
  6. `★ Lesson`: Concise engineering principle.

---

## ✦ Tech Stack

- **Backend**: Python 3.11+, FastAPI, Uvicorn, Jinja2, Pydantic v2
- **AI SDK**: Official Google Gemini Python SDK (`google-genai`)
- **Execution**: Subprocess-isolated Python code runner with timeout controls
- **Frontend**: Vanilla JavaScript (ES6+), Modern Responsive CSS with Deep Navy & Ice Blue palette, Prism.js syntax highlighting

---

## ✦ Getting Started

### 1. Prerequisites
- Python 3.11 or higher installed on your system.

### 2. Clone & Install Dependencies
```bash
git clone https://github.com/bilal-dev-0x/RAZE-Debug-Mentor.git
cd RAZE-Debug-Mentor
pip install -r requirements.txt
```

### 3. Configure Environment Variables (Optional)
Copy `.env.example` to `.env`:
```bash
copy .env.example .env
```
Add your Gemini API Key from Google AI Studio:
```env
GEMINI_API_KEY=your_gemini_api_key_here
GEMINI_MODEL=gemini-2.6-flash
CODE_EXEC_TIMEOUT_SECONDS=5.0
```
*(Note: If you run without an API key, RAZE automatically operates in Deterministic Fallback Mode, accurately diagnosing code-level errors on the user's actual program.)*

### 4. Start the Application
```bash
python main.py
```
Open your browser and navigate to:
```text
http://127.0.0.1:8000
```

---

## ✦ Verification & Automated Tests

To run the verification suite testing the required scenarios from the specification:
```bash
python test_raze.py
```

This verifies:
1. **TEST A — Shallow Copy & Mutation Bug**: Confirms diagnosis of nested data structures and list mutation on the `students` dictionary.
2. **TEST B — Simple NameError**: Confirms live execution capture and variable typo diagnosis (`age` vs `ages`).
3. **TEST C — Completely New Session**: Confirms zero context bleed between consecutive debugging problems.
4. **TEST D — API Failure & Fallback Safety**: Confirms honest deterministic fallback on user code without generic tutorial fallbacks.

To run the API endpoint suite:
```bash
python test_api_endpoints.py
```

---

## ✦ License
MIT License. Built with clean, reliable architecture.

