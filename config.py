"""Configuration settings for RAZE AI Debugging Mentor."""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env if present
BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

# Gemini API Configuration
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.6-flash").strip()

# Server Configuration
# 127.0.0.1 by default so the address a local `python main.py` run prints
# (and any auto-generated VS Code link) is actually clickable in a browser.
# 0.0.0.0 is a valid BIND address but not something a browser can visit —
# set HOST=0.0.0.0 explicitly (e.g. via .env) if you need the server
# reachable from another device or from inside a container.
HOST = os.getenv("HOST", "127.0.0.1")
PORT = int(os.getenv("PORT", 3000))
APP_ENV = os.getenv("APP_ENV", "development")

# Rate Limiting (in-memory requests per window)
RATE_LIMIT_REQUESTS = int(os.getenv("RATE_LIMIT_REQUESTS", 60))
RATE_LIMIT_WINDOW_SECONDS = int(os.getenv("RATE_LIMIT_WINDOW_SECONDS", 60))