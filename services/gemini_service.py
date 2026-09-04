"""Gemini API Service wrapper using official google-genai SDK with robust error handling."""

import os
import json
import logging
from typing import Dict, Any, Optional

try:
    from google import genai
    from google.genai import types
    from google.genai.errors import APIError
    GENAI_AVAILABLE = True
except ImportError:
    GENAI_AVAILABLE = False
    types = None
    APIError = Exception

import config
from prompts.system_prompts import RAZE_SYSTEM_PROMPT

logger = logging.getLogger("raze.gemini")

class GeminiService:
    def __init__(self):
        self.api_key = config.GEMINI_API_KEY
        self.model = config.GEMINI_MODEL
        self._client = None
        self._initialize_client()

    def _initialize_client(self):
        """Initialize Google GenAI client if library and key are available."""
        if not GENAI_AVAILABLE:
            logger.warning("google-genai library is not installed.")
            return

        if not self.api_key or self.api_key == "MY_GEMINI_API_KEY":
            logger.info("GEMINI_API_KEY not configured or using placeholder.")
            return

        try:
            self._client = genai.Client(api_key=self.api_key)
            logger.info("Initialized Gemini Client with model: %s", self.model)
        except Exception as e:
            logger.error("Failed to initialize Gemini Client: %s", e)
            self._client = None

    def is_configured(self) -> bool:
        """Check whether the Gemini client is ready to make API calls."""
        return self._client is not None

    def generate_json_response(self, user_prompt: str, system_prompt: Optional[str] = None) -> Dict[str, Any]:
        """Generate content from Gemini and parse as JSON, with error fallback."""
        sys_instruction = system_prompt or RAZE_SYSTEM_PROMPT

        if not self.is_configured():
            logger.warning("Gemini not configured. Using heuristic offline fallback.")
            return {}

        try:
            cfg = types.GenerateContentConfig(
                system_instruction=sys_instruction,
                temperature=0.2,
                response_mime_type="application/json"
            )

            response = self._client.models.generate_content(
                model=self.model,
                contents=user_prompt,
                config=cfg
            )

            if not response or not response.text:
                raise ValueError("Empty response from Gemini API")

            raw_text = response.text.strip()
            # Clean markdown wrappers if present
            if raw_text.startswith("```json"):
                raw_text = raw_text[7:]
            elif raw_text.startswith("```"):
                raw_text = raw_text[3:]
            if raw_text.endswith("```"):
                raw_text = raw_text[:-3]

            return json.loads(raw_text.strip())

        except Exception as e:
            logger.error("Error during Gemini API generation: %s", e)
            return {}
