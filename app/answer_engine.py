"""
Groq GPT-OSS 120B Streaming Answer Engine for Project New Horizon.
Supports streaming responses, Short/Free answer length modes, multi-key failover,
and 5-pair RAM context integration.
"""

import time
from typing import List, Dict, Generator
from groq import Groq

class AllAnswerKeysExhaustedError(Exception):
    """Raised when all configured GPT-OSS API keys are rate-limited or unavailable."""
    pass

class RateLimitError(Exception):
    """Internal marker for HTTP 429 rate-limit responses."""
    pass

class NetworkOfflineError(Exception):
    """Raised when answer client is offline or network connection fails."""
    pass

class GroqAnswerEngine:
    """
    Streaming Answer Client using Groq's GPT-OSS 120B model.
    Model ID: openai/gpt-oss-120b (Aug 2026: llama-3.3-70b-versatile deprecated -> use openai/gpt-oss-*)
    See https://console.groq.com/docs/deprecations
    """

    PRIMARY_MODEL = "openai/gpt-oss-120b"
    FALLBACK_MODEL = "openai/gpt-oss-20b"
    COOLDOWN_SECONDS = 30

    SYSTEM_PROMPTS = {
        "Short": (
            "You are a concise personal voice assistant widget. "
            "Give extremely brief, direct answers in 1 to 2 sentences maximum. "
            "Never include preambles, intros, or conversational filler."
        ),
        "Free": (
            "You are a helpful personal voice assistant widget. "
            "Provide clear, accurate, and direct answers tailored for desktop viewing."
        )
    }

    def __init__(self, keys: List[str]):
        if not keys:
            raise ValueError("At least one Groq Answer API key is required.")
        self._keys = list(keys)
        self._cooldowns: Dict[int, float] = {}

    def stream_answer(
        self,
        question: str,
        context_messages: List[Dict[str, str]] = None,
        mode: str = "Short"
    ) -> Generator[str, None, None]:
        """
        Stream answer completion tokens for a question.

        Args:
            question: Current user question.
            context_messages: Optional list of past Q&A message dicts (from ContextCache).
            mode: Answer mode ("Short" or "Free").

        Yields:
            str: Incremental text chunks as they arrive from the stream.

        Raises:
            AllAnswerKeysExhaustedError: If all API keys hit rate limits.
        """
        now = time.time()
        eligible = [
            i for i in range(len(self._keys))
            if self._cooldowns.get(i, 0) <= now
        ]

        if not eligible:
            soonest = min(self._cooldowns.values())
            wait = max(0, soonest - now)
            raise AllAnswerKeysExhaustedError(
                f"All {len(self._keys)} answer API keys are rate-limited. "
                f"Next key available in {wait:.0f}s."
            )

        # Assemble full message list
        system_prompt = self.SYSTEM_PROMPTS.get(mode, self.SYSTEM_PROMPTS["Short"])
        messages = [{"role": "system", "content": system_prompt}]

        if context_messages:
            messages.extend(context_messages)

        messages.append({"role": "user", "content": question})

        last_error = None
        for idx in eligible:
            try:
                for chunk in self._call_groq_stream(idx, messages):
                    yield chunk
                return  # Streaming completed successfully
            except RateLimitError as e:
                self._cooldowns[idx] = time.time() + self.COOLDOWN_SECONDS
                last_error = e
                continue

        raise AllAnswerKeysExhaustedError(
            f"All eligible answer API keys were rate-limited. Last error: {last_error}"
        )

    def _call_groq_stream(
        self,
        key_index: int,
        messages: List[Dict[str, str]]
    ) -> Generator[str, None, None]:
        """
        Call Groq streaming API using key at key_index.
        Handles 404 model-not-found (deprecated llama-3.3-70b-versatile after 2026-08-16)
        by falling back to PRIMARY->FALLBACK and surfacing a clear message.
        """
        client = Groq(api_key=self._keys[key_index])

        def _is_rate_limit(exc) -> bool:
            return getattr(exc, "status_code", None) == 429 or "429" in str(exc)

        def _is_model_not_found(exc) -> bool:
            sc = getattr(exc, "status_code", None)
            s = str(exc).lower()
            return sc == 404 or "404" in s or "model_not_found" in s or "model not found" in s or "decommissioned" in s or "deprecated" in s

        def _is_offline(exc) -> bool:
            s = str(exc).lower()
            return "connection" in s or "offline" in s or "nameresolution" in s or "unreachable" in s

        # Try primary model first
        try:
            stream = client.chat.completions.create(
                messages=messages,
                model=self.PRIMARY_MODEL,
                stream=True
            )
            for chunk in stream:
                if chunk.choices and chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
            return
        except Exception as e:
            if _is_rate_limit(e):
                raise RateLimitError(f"Key #{key_index + 1} rate-limited (429)") from e
            if _is_offline(e):
                raise NetworkOfflineError("Network connection offline. Check internet connection.") from e
            # model not found or other error -> try fallback
            primary_err = e
            primary_is_404 = _is_model_not_found(e)

            try:
                stream = client.chat.completions.create(
                    messages=messages,
                    model=self.FALLBACK_MODEL,
                    stream=True
                )
                for chunk in stream:
                    if chunk.choices and chunk.choices[0].delta.content:
                        yield chunk.choices[0].delta.content
                return
            except Exception as inner_e:
                if _is_rate_limit(inner_e):
                    raise RateLimitError(f"Key #{key_index + 1} rate-limited (429)") from inner_e
                if _is_offline(inner_e):
                    raise NetworkOfflineError("Network connection offline. Check internet connection.") from inner_e
                if _is_model_not_found(inner_e) or primary_is_404:
                    raise Exception(
                        f"Groq model not found (404). Primary '{self.PRIMARY_MODEL}' and fallback '{self.FALLBACK_MODEL}' unavailable. "
                        f"Groq deprecated llama-3.3-70b-versatile on 2026-08-16 -> use openai/gpt-oss-120b / openai/gpt-oss-20b. "
                        f"See https://console.groq.com/docs/deprecations — details: {inner_e} (primary: {primary_err})"
                    ) from inner_e
                raise inner_e
            # if we reach here, primary failed for non-404 reason and fallback not attempted -> surface primary
            if primary_is_404:
                raise Exception(
                    f"Groq model not found (404) for '{self.PRIMARY_MODEL}'. Groq deprecated llama-3.3-70b-versatile on 2026-08-16. "
                    f"Update PRIMARY_MODEL to openai/gpt-oss-120b. Details: {primary_err}"
                ) from e
