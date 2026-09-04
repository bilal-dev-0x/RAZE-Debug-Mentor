"""FastAPI application entry point for RAZE — AI Socratic Debugging Mentor."""

import os
import time
from pathlib import Path
from typing import Dict
from collections import defaultdict

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware

import config
from models import (
    StartDebugRequest,
    StartDebugResponse,
    RespondDebugRequest,
    StuckDebugRequest,
    DebugStagesResponse,
    StageInfo,
    DebugResponse,
    RunCodeRequest,
    RunCodeResponse,
)
from prompts.system_prompts import STAGE_NAMES
from services.gemini_service import GeminiService
from services.debug_engine import DebugEngine
from services.code_runner import run_python_safe

# Initialize FastAPI App
app = FastAPI(
    title="RAZE — AI Debugging Mentor",
    description="Socratic AI Debugging Mentor specifically for Python beginners.",
    version="1.0.0",
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Directory paths
BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
TEMPLATES_DIR = BASE_DIR / "templates"

# Ensure directories exist
STATIC_DIR.mkdir(exist_ok=True)
(STATIC_DIR / "css").mkdir(parents=True, exist_ok=True)
(STATIC_DIR / "js").mkdir(parents=True, exist_ok=True)
TEMPLATES_DIR.mkdir(exist_ok=True)

# Mount Static Files and Templates
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

# Initialize Services
gemini_service = GeminiService()
debug_engine = DebugEngine(gemini_service=gemini_service)

# In-Memory Rate Limiter
request_timestamps: Dict[str, list] = defaultdict(list)


@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    """In-memory rate limiter per IP address for API endpoints."""
    if request.url.path.startswith("/api/debug"):
        client_ip = request.client.host if request.client else "unknown"
        now = time.time()
        window_start = now - config.RATE_LIMIT_WINDOW_SECONDS

        # Purge expired timestamps
        request_timestamps[client_ip] = [
            ts for ts in request_timestamps[client_ip] if ts > window_start
        ]

        if len(request_timestamps[client_ip]) >= config.RATE_LIMIT_REQUESTS:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Rate limit exceeded. Please wait a moment before sending another request.",
            )

        request_timestamps[client_ip].append(now)

    response = await call_next(request)
    return response


# --- Frontend Page Routes ---

@app.get("/", response_class=HTMLResponse)
async def serve_index(request: Request):
    """Serve the single-page HTML interface."""
    index_path = TEMPLATES_DIR / "index.html"
    if index_path.exists():
        return HTMLResponse(content=index_path.read_text(encoding="utf-8"))
    return HTMLResponse("<h1>RAZE AI Debugging Mentor</h1><p>Frontend template loading...</p>")


@app.get("/health")
@app.get("/api/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": "RAZE AI Debugging Mentor",
        "gemini_configured": gemini_service.is_configured(),
        "model": config.GEMINI_MODEL,
    }


# --- Live Code Execution ---

@app.post("/api/run", response_model=RunCodeResponse)
async def run_code(payload: RunCodeRequest):
    """Execute a Python snippet in a sandboxed subprocess and return real output.

    Used by the frontend's live editor "Run" action, independent of any
    debugging session.
    """
    language = (payload.language or "python").lower()
    if language not in ("python", "py"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Only Python is supported by the backend execution engine. Requested: {payload.language}",
        )

    if not payload.code or not payload.code.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Source code cannot be empty.",
        )

    result = run_python_safe(payload.code)
    return RunCodeResponse(**result)


# --- Socratic Debugging API Endpoints ---

@app.get("/api/debug/stages", response_model=DebugStagesResponse)
async def get_stages():
    """Returns the list of debugging stages for UI progress tracking."""
    return DebugStagesResponse(
        stages=[StageInfo(**stage) for stage in STAGE_NAMES]
    )


@app.post("/api/debug/start", response_model=StartDebugResponse)
async def start_debug_session(payload: StartDebugRequest):
    """Start a new Socratic debugging session.
    
    Accepts: {code: str, error_message: str | null, expected_result: str, actual_result: str | null}
    Returns: {session_id: str, stage: "observation", message: str, suspicious_lines: list[int]}
    """
    if not payload.code or not payload.code.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Python source code is required to start a debugging session.",
        )

    if not payload.expected_result or not payload.expected_result.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Expected result is required to establish what the program should do.",
        )

    try:
        session_data = debug_engine.start_session(
            code=payload.code,
            error_message=payload.error_message,
            expected_result=payload.expected_result,
            actual_result=payload.actual_result,
        )
        return StartDebugResponse(**session_data)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to initialize debugging session: {str(e)}",
        )


@app.post("/api/debug/respond", response_model=DebugResponse)
async def respond_to_mentor(payload: RespondDebugRequest):
    """Submit user's answer/reflection to advance through the Socratic flow.
    
    Accepts: {session_id: str, user_message: str, stage: str}
    """
    if not payload.session_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="session_id is required.",
        )

    if not payload.user_message or not payload.user_message.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="user_message cannot be empty.",
        )

    try:
        result = debug_engine.process_response(
            session_id=payload.session_id,
            user_message=payload.user_message,
            stage=payload.stage,
        )
        return DebugResponse(**result)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process response: {str(e)}",
        )


@app.post("/api/debug/stuck", response_model=DebugResponse)
async def handle_stuck(payload: StuckDebugRequest):
    """Handle 'I'm Stuck' button by providing progressive hints without dumping solution."""
    if not payload.session_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="session_id is required.",
        )

    try:
        result = debug_engine.process_stuck(
            session_id=payload.session_id, stage=payload.stage
        )
        return DebugResponse(**result)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process stuck request: {str(e)}",
        )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host=config.HOST, port=config.PORT, reload=True)
