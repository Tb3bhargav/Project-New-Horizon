"""
Configuration loader for Project New Horizon.
Reads API keys from environment variables or a local .env file.
Keys are never persisted to project source files.
"""

import os
import pathlib


def _load_dotenv() -> None:
    """
    Parse a .env file in the project root and inject its values into
    os.environ (without overwriting existing env vars).
    """
    env_path = pathlib.Path(__file__).resolve().parent.parent / ".env"
    if not env_path.is_file():
        return

    with open(env_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip()
            # Do not overwrite existing environment variables
            if key and key not in os.environ:
                os.environ[key] = value


def _collect_numbered_keys(prefix: str) -> list[str]:
    """
    Collect keys matching PREFIX_1, PREFIX_2, ... from os.environ.
    Stops at the first missing index.
    """
    keys = []
    for i in range(1, 20):  # Support up to 19 keys
        val = os.environ.get(f"{prefix}_{i}", "").strip()
        if val:
            keys.append(val)
    return keys


def load_whisper_keys() -> list[str]:
    """
    Load Groq Whisper transcription API keys.
    Reads GROQ_WHISPER_KEY_1, GROQ_WHISPER_KEY_2, ... from env vars.
    Falls back to .env file if env vars are not set.
    """
    _load_dotenv()
    return _collect_numbered_keys("GROQ_WHISPER_KEY")


def load_answer_keys() -> list[str]:
    """
    Load Groq GPT-OSS answer API keys (Phase 3).
    Reads GROQ_ANSWER_KEY_1, GROQ_ANSWER_KEY_2, ... from env vars.
    Falls back to load_whisper_keys() if no answer keys are specified.
    """
    _load_dotenv()
    keys = _collect_numbered_keys("GROQ_ANSWER_KEY")
    if not keys:
        keys = load_whisper_keys()
    return keys
