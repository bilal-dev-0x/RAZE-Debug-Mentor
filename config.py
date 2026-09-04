import os
from pathlib import Path
from dotenv import load_dotenv, dotenv_values

BASE_DIR = Path(__file__).resolve().parent

# Locate .env file
ENV_FILE = BASE_DIR / ".env"
if not ENV_FILE.exists():
    if (BASE_DIR / ".env.example").exists():
        ENV_FILE = BASE_DIR / ".env.example"

# Load with override=True so an empty shell env var cannot shadow the file
if ENV_FILE.exists():
    load_dotenv(dotenv_path=ENV_FILE, override=True)

# Also inspect dotenv_values directly for complete precedence safety
file_vals = dotenv_values(ENV_FILE) if ENV_FILE.exists() else {}

def _resolve_api_key() -> tuple[str, str]:
    """
    Safely resolves the API key and returns (key, source_description).
    Precedence:
    1. Valid non-empty os.environ["GEMINI_API_KEY"] or ["GOOGLE_API_KEY"]
    2. Non-empty value from .env file
    3. Missing
    """
    env_gemini = os.environ.get("GEMINI_API_KEY", "").strip()
    env_google = os.environ.get("GOOGLE_API_KEY", "").strip()
    file_gemini = file_vals.get("GEMINI_API_KEY", "").strip()
    file_google = file_vals.get("GOOGLE_API_KEY", "").strip()

    if env_gemini and not env_gemini.startswith("your_"):
        return env_gemini, "os.environ (GEMINI_API_KEY)"
    if file_gemini and not file_gemini.startswith("your_"):
        return file_gemini, f"{ENV_FILE.name} file (GEMINI_API_KEY)"
    if env_google and not env_google.startswith("your_"):
        return env_google, "os.environ (GOOGLE_API_KEY)"
    if file_google and not file_google.startswith("your_"):
        return file_google, f"{ENV_FILE.name} file (GOOGLE_API_KEY)"

    return "", "missing"

resolved_key, key_source = _resolve_api_key()

class Settings:
    DOTENV_PATH: Path = ENV_FILE
    DOTENV_EXISTS: bool = ENV_FILE.exists()
    KEY_SOURCE: str = key_source

    # Gemini API Configuration
    GEMINI_API_KEY: str = resolved_key
    GEMINI_MODEL: str = (
        os.getenv("GEMINI_MODEL") or file_vals.get("GEMINI_MODEL") or "gemini-3.6-flash"
    ).strip()

    # Code Execution Settings
    CODE_EXEC_TIMEOUT_SECONDS: float = float(
        os.getenv("CODE_EXEC_TIMEOUT_SECONDS") or file_vals.get("CODE_EXEC_TIMEOUT_SECONDS") or "5.0"
    )
    MAX_CODE_LENGTH: int = int(
        os.getenv("MAX_CODE_LENGTH") or file_vals.get("MAX_CODE_LENGTH") or "10000"
    )

    # Session Management
    SESSION_TTL_MINUTES: int = int(
        os.getenv("SESSION_TTL_MINUTES") or file_vals.get("SESSION_TTL_MINUTES") or "60"
    )

    # Server Settings
    HOST: str = os.getenv("HOST", "127.0.0.1")
    PORT: int = int(os.getenv("PORT", "8000"))

settings = Settings()
