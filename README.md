<div align="center">

<svg width="760" height="180" viewBox="0 0 760 180" role="img" aria-labelledby="raze-title raze-description" xmlns="http://www.w3.org/2000/svg">
  <title id="raze-title">RAZE Debug Mentor</title>
  <desc id="raze-description">A developer-tool style RAZE terminal header.</desc>
  <rect width="760" height="180" rx="12" fill="#0d0d0f"/>
  <path d="M0 42H760" stroke="#2a2a30"/>
  <circle cx="24" cy="21" r="5" fill="#fb7185"/>
  <circle cx="42" cy="21" r="5" fill="#fbbf24"/>
  <circle cx="60" cy="21" r="5" fill="#4ade80"/>
  <text x="92" y="27" fill="#71717a" font-family="monospace" font-size="13">raze-debug-mentor</text>
  <g font-family="monospace" font-weight="700">
    <text x="42" y="100" fill="#7c6cff" font-size="46">R_&gt;</text>
    <text x="190" y="100" fill="#f4f4f5" font-size="42">RAZE</text>
    <text x="193" y="132" fill="#a1a1aa" font-size="18">DEBUG MENTOR</text>
  </g>
  <path d="M42 151H718" stroke="#2a2a30"/>
  <text x="42" y="169" fill="#71717a" font-family="monospace" font-size="12">execution evidence  /  structured reasoning  /  root-cause clarity</text>
</svg>

# RAZE Debug Mentor

**A calm senior developer sitting beside you, helping you understand what actually went wrong.**

<a href="https://github.com/bilal-dev-0x/RAZE-Debug-Mentor"><img src="https://img.shields.io/badge/repository-RAZE--Debug--Mentor-7c6cff?style=flat-square" alt="Repository"></a>
<img src="https://img.shields.io/badge/Python-3.11%2B-3776AB?style=flat-square&logo=python&logoColor=white" alt="Python 3.11 or newer">
<img src="https://img.shields.io/badge/FastAPI-0.110%2B-009688?style=flat-square&logo=fastapi&logoColor=white" alt="FastAPI">
<img src="https://img.shields.io/badge/Frontend-Vanilla%20JavaScript-F7DF1E?style=flat-square&logo=javascript&logoColor=111114" alt="Vanilla JavaScript">
<img src="https://img.shields.io/badge/License-MIT-71717a?style=flat-square" alt="MIT license declaration">

</div>

RAZE is an evidence-driven debugging mentor for Python-first development. It executes the submitted program, captures runtime evidence, asks two focused reasoning questions, and then explains the root cause and corrected version of the user’s actual code.

<!-- Add RAZE demo screenshot here -->

## Why RAZE?

Traditional coding assistants often jump straight to a fix. RAZE makes the reasoning visible first:

| Traditional coding assistant | RAZE Debug Mentor |
| --- | --- |
| Gives the answer immediately | Starts with execution evidence |
| Centers the fix | Builds an observation from the current program |
| Can encourage copy/paste behavior | Asks two focused reasoning questions |
| May explain the concept generically | Connects the mechanism to the user’s code |
| Conversation can continue indefinitely | Stops after Question 2 with a complete diagnosis |

## Core Workflow

```text
Problem
  ↓
Execution
  ↓
Observation
  ↓
Question 1
  ↓
User Answer
  ↓
Question 2
  ↓
User Answer
  ↓
Root Cause
  ↓
Corrected Code
  ↓
Engineering Lesson
```

The stop rule is intentional: RAZE asks exactly two diagnostic questions, then turns the evidence and answers into a structured five-part solution.

## Key Features

### Real execution evidence

Python submissions run in an isolated subprocess with timeout controls. RAZE captures stdout, stderr, exit codes, traceback type, error line, and error details.

### Structured investigation

The mentor workflow progresses through observation, Question 1, Question 2, and final solution while preserving the current session’s code and evidence.

### Multi-provider diagnosis

External AI providers are attempted sequentially. The frontend receives the same logical diagnosis shape regardless of which provider succeeds.

### Deterministic fallback

When external providers are unavailable, the local analyzer checks the submitted program for grounded patterns such as NameError, ZeroDivisionError, IndexError, SyntaxError, nested shallow copies, and mutable default arguments.

### Session isolation

Each debugging session uses its own UUID-backed `DebugSession`. Reset actions clear the client state and remove the server-side session.

### Engineering-quality output

The final response includes what was found, what happens under the hood, the root-cause concept, corrected code, why the fix works, and a concise lesson.

## AI Failover

```text
Gemini
   ↓ failure
OpenRouter
   ↓ failure
Groq
   ↓ failure
Local Diagnostic Engine
```

The router is implemented in `services/ai_router.py` and stops as soon as a provider returns a valid response. Provider failures are infrastructure events, not programming diagnoses; if all providers fail, RAZE falls back to analysis of the user’s actual code rather than a hardcoded tutorial example.

Configured model names are read from environment settings:

| Provider | Configuration |
| --- | --- |
| Gemini | `GEMINI_API_KEY`, `GEMINI_MODEL` |
| OpenRouter | `OPENROUTER_API_KEY`, `OPENROUTER_MODEL` |
| Groq | `GROQ_API_KEY`, `GROQ_MODEL` |

## Architecture

```text
┌──────────────────────────────┐
│ Browser                      │
│ Jinja template + JS + CSS    │
└──────────────┬───────────────┘
               ↓
┌──────────────────────────────┐
│ FastAPI application           │
│ main.py                       │
└──────────────┬───────────────┘
               ↓
┌──────────────────────────────┐
│ Session + execution flow     │
│ DebugEngine + CodeRunner     │
└──────────────┬───────────────┘
               ↓
┌──────────────────────────────┐
│ Diagnosis context + AI router│
│ diagnosis_service + router   │
└──────────────┬───────────────┘
               ↓
┌──────────────────────────────┐
│ Gemini / OpenRouter / Groq   │
└──────────────┬───────────────┘
               ↓ failure
┌──────────────────────────────┐
│ DeterministicAnalyzer        │
└──────────────────────────────┘
```

## Tech Stack

| Layer | Technology |
| --- | --- |
| Backend | Python, FastAPI, Uvicorn |
| Templates | Jinja2 |
| API models | Pydantic |
| Frontend | Vanilla JavaScript, HTML, CSS |
| AI | `google-genai`, OpenRouter HTTP API, Groq HTTP API |
| Execution | Isolated Python subprocess runner |
| Highlighting | Prism.js |
| Configuration | `python-dotenv` |
| Testing | Python `unittest`, FastAPI `TestClient`, async verification scripts |

## Project Structure

```text
RAZE-Debug-Mentor/
├── main.py
├── config.py
├── models.py
├── requirements.txt
├── prompts/
│   └── system_prompts.py
├── services/
│   ├── ai_router.py
│   ├── code_runner.py
│   ├── debug_engine.py
│   ├── deterministic.py
│   ├── diagnosis_service.py
│   ├── gemini_service.py
│   ├── groq_service.py
│   └── openrouter_service.py
├── templates/
│   └── index.html
├── static/
│   ├── css/style.css
│   ├── images/raze-logo.jpg
│   └── js/app.js
├── test_raze.py
├── test_api_endpoints.py
├── test_gemini_connection.py
├── test_ai_router.py
└── test_deterministic_regressions.py
```

## Getting Started

### 1. Clone the repository

```bash
git clone https://github.com/bilal-dev-0x/RAZE-Debug-Mentor.git
cd RAZE-Debug-Mentor
```

### 2. Install dependencies

```bash
python -m pip install -r requirements.txt
```

### 3. Configure environment variables

Create a local `.env` file from the template:

```powershell
Copy-Item .env.example .env
```

Set the provider keys and model names you intend to use. Keep all credentials in `.env`; never commit them. The repository ignores `.env` through `.gitignore`.

### 4. Start RAZE

```bash
python main.py
```

Open [http://127.0.0.1:8000](http://127.0.0.1:8000).

Without an available external provider, RAZE can still use the deterministic analyzer for supported patterns.

## Testing

Run the main workflow verification:

```bash
python test_raze.py
```

Run the endpoint checks:

```bash
python test_api_endpoints.py
```

Run the router failover tests:

```bash
python -m unittest test_ai_router.py
```

Run deterministic regression tests:

```bash
python -m unittest test_deterministic_regressions.py
```

The test coverage includes execution and traceback capture, session isolation, provider ordering and stop behavior, shallow-copy detection, mutable-default detection, and vague-answer classification. `test_gemini_connection.py` is an optional live Gemini connectivity check and requires a working Gemini credential.

## Example Debugging Session

```python
students = [{"name": "Ali", "scores": {"math": [80, 90]}}]
backup = students.copy()

backup[0]["scores"]["math"][0] += 10
print(students[0]["scores"]["math"])
```

```text
Problem
  → The backup update changes the original student data.
Execution Evidence
  → Both objects show the modified nested score.
Observation
  → students.copy() duplicates only the outer list.
Root Cause
  → Shallow copying of nested mutable data.
Fix
  → backup = copy.deepcopy(students)
Lesson
  → Use deepcopy when nested objects must be independent.
```

## Design Philosophy

RAZE is a debugging workspace, not a generic AI chatbot. Its calm interface keeps execution evidence, structured reasoning, progressive explanation, and the user’s own program at the center. AI assists the investigation; it does not replace the investigation with decoration or an unrelated code dump.

## Roadmap

These are future ideas, not current capabilities:

- More deterministic bug detectors
- Broader language execution and analysis support
- Debugging history
- IDE integrations
- Richer execution visualization

## Contributing

Issues and focused pull requests are welcome. Keep changes grounded in the current debugging workflow, preserve session isolation, and add regression coverage for behavior changes.

## License

The existing project documentation declares the project under the MIT License. A standalone `LICENSE` file is not currently present in the repository.

<div align="center">

---

**RAZE Debug Mentor**  
`Built with Python, curiosity, and a lot of debugging.`

<svg width="220" height="28" viewBox="0 0 220 28" role="img" aria-label="RAZE status line" xmlns="http://www.w3.org/2000/svg">
  <text x="0" y="19" fill="#7c6cff" font-family="monospace" font-size="14">R_&gt;</text>
  <path d="M42 14H210" stroke="#2a2a30"/>
  <circle cx="36" cy="14" r="3" fill="#4ade80">
    <animate attributeName="opacity" values="1;.35;1" dur="2.4s" repeatCount="indefinite"/>
  </circle>
</svg>

</div>
