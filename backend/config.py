"""
Shared backend configuration. Reads API credentials from environment variables
first (safe for production), falls back to api_config.json (local dev only).

Auto-loads .env from project root if python-dotenv is available.

Environment variables:
    FORMAI_API_KEY     — DashScope API key
    FORMAI_MODEL_CODE  — DashScope model code (default: qwen-plus)
    FORMAI_USE_REMOTE  — set to "false" to disable remote API (default: true)
"""
import json
import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Auto-load .env from project root
_ENV_FILE = PROJECT_ROOT / ".env"
if _ENV_FILE.exists():
    try:
        from dotenv import load_dotenv
        load_dotenv(_ENV_FILE)
    except ImportError:
        pass  # python-dotenv not installed, env vars must be set externally


def load_api_config() -> dict:
    """Load API configuration. Env vars take priority over config file."""

    # 1. Primary: environment variables (never committed to git)
    env_key = os.environ.get("FORMAI_API_KEY", "")
    if env_key:
        return {
            "use_remote": os.environ.get("FORMAI_USE_REMOTE", "true").lower() != "false",
            "api_key": env_key,
            "model_code": os.environ.get("FORMAI_MODEL_CODE", "qwen-plus"),
        }

    # 2. Fallback: config file (gitignored, for local development)
    for name in ["api_config.json", "data/api_config.json"]:
        path = PROJECT_ROOT / name
        if path.exists():
            data = json.loads(path.read_text())
            return {
                "use_remote": data.get("use_remote", False),
                "api_key": data.get("api_key", ""),
                "model_code": data.get("model_code", "qwen-plus"),
            }

    # 3. No configuration found — remote disabled
    return {"use_remote": False, "api_key": "", "model_code": "qwen-plus"}
