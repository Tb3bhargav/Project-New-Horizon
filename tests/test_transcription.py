"""
Tests for the transcription module (Phase 2).

Tests cover:
1. WAV conversion from float32 numpy arrays
2. Successful transcription (mocked Groq API)
3. Rate-limit failover between keys
4. Cooldown tracking for rate-limited keys
5. AllKeysExhaustedError when all keys are rate-limited
"""

import io
import wave
import time
import numpy as np
from unittest.mock import patch, MagicMock

from app.transcription import GroqWhisperClient, AllKeysExhaustedError, RateLimitError


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

SAMPLE_RATE = 16000

def make_test_audio(duration_sec: float = 0.5) -> np.ndarray:
    """Create a short sine wave audio array for testing."""
    samples = int(SAMPLE_RATE * duration_sec)
    t = np.linspace(0, duration_sec, samples, endpoint=False)
    return (0.3 * np.sin(2 * np.pi * 440 * t)).astype(np.float32)


# ---------------------------------------------------------------------------
# Test 1 - WAV conversion
# ---------------------------------------------------------------------------

def test_wav_conversion():
    print("=" * 60)
    print("TEST 1: WAV Conversion (float32 -> 16-bit PCM WAV)")
    print("=" * 60)

    audio = make_test_audio(0.5)
    wav_bytes = GroqWhisperClient._audio_to_wav(audio, SAMPLE_RATE)

    # Verify it's valid WAV
    buf = io.BytesIO(wav_bytes)
    with wave.open(buf, "rb") as wf:
        assert wf.getnchannels() == 1, "WAV should be mono"
        assert wf.getsampwidth() == 2, "WAV should be 16-bit (2 bytes)"
        assert wf.getframerate() == SAMPLE_RATE, f"WAV sample rate should be {SAMPLE_RATE}"
        n_frames = wf.getnframes()
        expected_frames = len(audio)
        assert n_frames == expected_frames, (
            f"Expected {expected_frames} frames, got {n_frames}"
        )

    print(f"  WAV bytes: {len(wav_bytes)} bytes")
    print(f"  Channels: 1, Sample width: 2, Rate: {SAMPLE_RATE}")
    print(f"  Frames: {len(audio)}")
    print("\n[VERIFICATION PASSED] WAV conversion produces valid file.")
    print("=" * 60)


# ---------------------------------------------------------------------------
# Test 2 - Successful transcription (mocked)
# ---------------------------------------------------------------------------

def test_successful_transcription():
    print()
    print("=" * 60)
    print("TEST 2: Successful Transcription (Mocked Groq API)")
    print("=" * 60)

    client = GroqWhisperClient(keys=["test_key_1"])
    audio = make_test_audio(0.5)

    mock_groq = MagicMock()
    mock_groq.audio.transcriptions.create.return_value = "Hello world"

    with patch("app.transcription.Groq", return_value=mock_groq):
        result = client.transcribe(audio, sample_rate=SAMPLE_RATE)

    assert result == "Hello world", f"Expected 'Hello world', got '{result}'"
    print(f"  Transcript: '{result}'")
    print("\n[VERIFICATION PASSED] Transcription returns expected text.")
    print("=" * 60)


# ---------------------------------------------------------------------------
# Test 3 - Rate-limit failover
# ---------------------------------------------------------------------------

def test_rate_limit_failover():
    print()
    print("=" * 60)
    print("TEST 3: Rate-Limit Failover Between Keys")
    print("=" * 60)

    client = GroqWhisperClient(keys=["key_1", "key_2", "key_3"])
    audio = make_test_audio(0.5)

    call_count = {"n": 0}

    def mock_groq_constructor(api_key=None):
        mock = MagicMock()
        call_count["n"] += 1

        if api_key == "key_1":
            # First key returns 429
            err = Exception("Rate limit exceeded")
            err.status_code = 429
            mock.audio.transcriptions.create.side_effect = err
        else:
            # Second key succeeds
            mock.audio.transcriptions.create.return_value = "Transcribed text"
        return mock

    with patch("app.transcription.Groq", side_effect=mock_groq_constructor):
        result = client.transcribe(audio, sample_rate=SAMPLE_RATE)

    assert result == "Transcribed text", f"Expected 'Transcribed text', got '{result}'"

    # Key 1 should now be in cooldown
    assert 0 in client._cooldowns, "Key 0 should be in cooldown after 429"
    print(f"  Key 1 hit 429 -> cooldown set")
    print(f"  Key 2 succeeded -> transcript: '{result}'")
    print("\n[VERIFICATION PASSED] Failover from rate-limited key works.")
    print("=" * 60)


# ---------------------------------------------------------------------------
# Test 4 - Cooldown tracking
# ---------------------------------------------------------------------------

def test_cooldown_tracking():
    print()
    print("=" * 60)
    print("TEST 4: Cooldown Tracking")
    print("=" * 60)

    client = GroqWhisperClient(keys=["key_1", "key_2"])

    # Manually set key_1 into cooldown (30 seconds from now)
    client._cooldowns[0] = time.time() + 30

    audio = make_test_audio(0.5)

    def mock_groq_constructor(api_key=None):
        mock = MagicMock()
        assert api_key == "key_2", f"Should skip key_1 (in cooldown), got key: {api_key}"
        mock.audio.transcriptions.create.return_value = "From key 2"
        return mock

    with patch("app.transcription.Groq", side_effect=mock_groq_constructor):
        result = client.transcribe(audio, sample_rate=SAMPLE_RATE)

    assert result == "From key 2", f"Expected 'From key 2', got '{result}'"
    print(f"  Key 1 in cooldown -> skipped")
    print(f"  Key 2 used -> transcript: '{result}'")
    print("\n[VERIFICATION PASSED] Cooldown key is skipped correctly.")
    print("=" * 60)


# ---------------------------------------------------------------------------
# Test 5 - All keys exhausted
# ---------------------------------------------------------------------------

def test_all_keys_exhausted():
    print()
    print("=" * 60)
    print("TEST 5: All Keys Exhausted Error")
    print("=" * 60)

    client = GroqWhisperClient(keys=["key_1", "key_2"])
    audio = make_test_audio(0.5)

    def mock_groq_constructor(api_key=None):
        mock = MagicMock()
        err = Exception("Rate limit exceeded")
        err.status_code = 429
        mock.audio.transcriptions.create.side_effect = err
        return mock

    with patch("app.transcription.Groq", side_effect=mock_groq_constructor):
        try:
            client.transcribe(audio, sample_rate=SAMPLE_RATE)
            assert False, "Should have raised AllKeysExhaustedError"
        except AllKeysExhaustedError as e:
            print(f"  AllKeysExhaustedError raised: {e}")

    # Both keys should be in cooldown
    assert 0 in client._cooldowns, "Key 0 should be in cooldown"
    assert 1 in client._cooldowns, "Key 1 should be in cooldown"
    print(f"  Key 1 cooldown: set")
    print(f"  Key 2 cooldown: set")
    print("\n[VERIFICATION PASSED] AllKeysExhaustedError raised correctly.")
    print("=" * 60)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    test_wav_conversion()
    test_successful_transcription()
    test_rate_limit_failover()
    test_cooldown_tracking()
    test_all_keys_exhausted()
    print("\n" + "=" * 60)
    print("ALL PHASE 2 TRANSCRIPTION TESTS PASSED [OK]")
    print("=" * 60)
