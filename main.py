import logging
from pathlib import Path
from fastapi import FastAPI, Request, HTTPException, status
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from config import settings
from models import (
    StartSessionRequest,
    SubmitAnswerRequest,
    RunCodeRequest,
    SessionResponse,
    ExecutionResult
)
from services.debug_engine import debug_engine
from services.code_runner import CodeRunner
from services.gemini_service import GeminiService

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("raze.main")

app = FastAPI(
    title="RAZE — AI Debugging Mentor",
    description="Python-first AI-powered debugging mentor web application.",
    version="2.0.0"
)

BASE_DIR = Path(__file__).resolve().parent
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

def _to_response(session) -> SessionResponse:
    return SessionResponse(
        session_id=session.session_id,
        language=session.language,
        stage=session.stage,
        submitted_code=session.submitted_code,
        execution_result=session.execution_result,
        observation=session.observation,
        question_1=session.question_1,
        answer_1=session.answer_1,
        question_2=session.question_2,
        answer_2=session.answer_2,
        final_solution=session.final_solution,
        is_completed=(session.stage.value == "completed"),
        used_deterministic_fallback=session.used_deterministic_fallback,
        ai_unavailable_notice=session.ai_unavailable_notice,
        diagnosis_provider=session.diagnosis_provider,
        answer_1_quality=session.answer_1_quality,
        answer_2_quality=session.answer_2_quality
    )

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "gemini_configured": GeminiService.is_configured(),
            "model_name": settings.GEMINI_MODEL
        }
    )

@app.post("/api/run-code", response_model=ExecutionResult)
async def api_run_code(req: RunCodeRequest):
    """
    Executes code on demand without altering active session state.
    """
    return await CodeRunner.run_code(req.language, req.code)

@app.post("/api/session/start", response_model=SessionResponse)
async def api_start_session(req: StartSessionRequest):
    """
    Creates a new isolated debugging session, executes the code, and generates Observation + Q1.
    """
    if not req.code.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot start debugging session with empty code."
        )
    session = await debug_engine.start_session(req)
    return _to_response(session)

@app.post("/api/session/answer", response_model=SessionResponse)
async def api_submit_answer(req: SubmitAnswerRequest):
    """
    Submits user answer. Advances through Q1 -> Q2 -> Final Solution (enforcing Stop Rule).
    """
    if not req.answer.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Answer cannot be blank."
        )
    try:
        session = await debug_engine.submit_answer(req.session_id, req.answer)
        return _to_response(session)
    except KeyError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        logger.error(f"Error submitting answer: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@app.get("/api/session/{session_id}", response_model=SessionResponse)
async def api_get_session(session_id: str):
    session = debug_engine.get_session(session_id)
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found.")
    return _to_response(session)

@app.post("/api/session/reset")
async def api_reset_session(data: dict):
    session_id = data.get("session_id")
    if session_id:
        debug_engine.delete_session(session_id)
    return {"status": "ok", "message": "Session reset successfully"}

@app.get("/api/health")
async def api_health():
    status_info = GeminiService.get_status()
    return {
        "status": "healthy",
        "gemini_configured": GeminiService.is_configured(),
        "model": settings.GEMINI_MODEL,
        "gemini_configured": status_info["key_present"],
        "key_source": status_info["key_source"],
        "dotenv_exists": status_info["dotenv_exists"],
        "dotenv_path": status_info["dotenv_path"],
        "model": status_info["model"],
        "python_runnable": True
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=settings.HOST, port=settings.PORT)
