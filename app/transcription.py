"""
Groq Whisper Large V3 Turbo transcription client for Project New Horizon.
Supports multiple API keys with rate-limit failover and cooldown tracking.
"""

import io
import time
import wave
import numpy as np
from groq import Groq


class AllKeysExhaustedError(Exception):
    """Raised when all configured API keys are rate-limited or unavailable."""
    pass


class GroqWhisperClient:
    """
    Transcription client using Groq's whisper-large-v3-turbo model.

    Accepts multiple API keys.  On a rate-limit (HTTP 429) response the
    current key enters a cooldown period and the next eligible key is tried.
    Keys are only rotated after an *actual* rate-limit response — not on
    every request.
    """

    MODEL = "whisper-large-v3-turbo"
    FALLBACK_MODEL = "whisper-large-v3"
    COOLDOWN_SECONDS = 30

    def __init__(self, keys: list[str]):
        if not keys:
            raise ValueError("At least one Groq Whisper API key is required.")
        self._keys = list(keys)
        # Maps key index -> timestamp when cooldown expires
        self._cooldowns: dict[int, float] = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def transcribe(self, audio: np.ndarray, sample_rate: int = 16000) -> str:
        """
        Transcribe a float32 numpy audio array to text.

        Args:
            audio: 1-D float32 numpy array (mono, values in [-1, 1]).
            sample_rate: Sample rate in Hz (default 16000).

        Returns:
            Transcribed text string.

        Raises:
            AllKeysExhaustedError: All keys are rate-limited.
            Exception: Non-rate-limit API errors.
        """
        wav_bytes = self._audio_to_wav(audio, sample_rate)

        now = time.time()
        eligible = [
            i for i in range(len(self._keys))
            if self._cooldowns.get(i, 0) <= now
        ]

        if not eligible:
            # All keys are in cooldown — find the soonest expiry
            soonest = min(self._cooldowns.values())
            wait = max(0, soonest - now)
            raise AllKeysExhaustedError(
                f"All {len(self._keys)} API keys are rate-limited. "
                f"Next key available in {wait:.0f}s."
            )

        last_error = None
        for idx in eligible:
            try:
                return self._call_groq(idx, wav_bytes)
            except RateLimitError as e:
                self._cooldowns[idx] = time.time() + self.COOLDOWN_SECONDS
                last_error = e
                continue

        # All eligible keys hit rate limits during this attempt
        raise AllKeysExhaustedError(
            f"All eligible API keys were rate-limited. "
            f"Last error: {last_error}"
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _call_groq(self, key_index: int, wav_bytes: bytes) -> str:
        """
        Make a single transcription API call with the given key.
        Handles 404 model-not-found by falling back to whisper-large-v3.

        Raises:
            RateLimitError: on HTTP 429.
            Exception: on other API failures with clear 404 hint.
        """
        client = Groq(api_key=self._keys[key_index])

        def _is_404(exc) -> bool:
            sc = getattr(exc, "status_code", None)
            s = str(exc).lower()
            return sc == 404 or "404" in s or "model_not_found" in s or "model not found" in s

        try:
            transcription = client.audio.transcriptions.create(
                file=("utterance.wav", wav_bytes),
                model=self.MODEL,
                response_format="text",
                language="en",
            )
            result = str(transcription).strip()
            return result
        except Exception as e:
            status = getattr(e, "status_code", None)
            if status == 429:
                raise RateLimitError(f"Key #{key_index + 1} rate-limited (429)") from e
            err_str = str(e).lower()
            if "connection" in err_str or "offline" in err_str or "nameresolution" in err_str or "unreachable" in err_str:
                raise NetworkOfflineError("Network connection offline. Check internet connection.") from e
            if _is_404(e):
                # try fallback model once
                try:
                    transcription = client.audio.transcriptions.create(
                        file=("utterance.wav", wav_bytes),
                        model=self.FALLBACK_MODEL,
                        response_format="text",
                        language="en",
                    )
                    return str(transcription).strip()
                except Exception as fe:
                    if getattr(fe, "status_code", None) == 429:
                        raise RateLimitError(f"Key #{key_index + 1} rate-limited (429)") from fe
                    if _is_404(fe):
                        raise Exception(
                            f"Transcription model not found (404). Tried '{self.MODEL}' and fallback '{self.FALLBACK_MODEL}'. "
                            f"Check https://console.groq.com/docs/models — details: {fe} (primary: {e})"
                        ) from fe
                    raise fe
            raise

    @staticmethod
    def _audio_to_wav(audio: np.ndarray, sample_rate: int) -> bytes:
        """
        Convert a float32 numpy array to in-memory WAV bytes (16-bit PCM).

        Args:
            audio: 1-D float32 array with values in [-1.0, 1.0].
            sample_rate: Sample rate in Hz.

        Returns:
            WAV file content as bytes.
        """
        # Clip and convert to 16-bit PCM
        audio_clipped = np.clip(audio, -1.0, 1.0)
        pcm_16 = (audio_clipped * 32767).astype(np.int16)

        buf = io.BytesIO()
        with wave.open(buf, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)  # 16-bit = 2 bytes
            wf.setframerate(sample_rate)
            wf.writeframes(pcm_16.tobytes())

        return buf.getvalue()


class RateLimitError(Exception):
    """Internal marker for a 429 rate-limit response from Groq."""
    pass


class NetworkOfflineError(Exception):
    """Raised when transcription client is offline or network connection fails."""
    pass
