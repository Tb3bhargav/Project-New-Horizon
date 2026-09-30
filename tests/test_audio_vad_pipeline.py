"""
Runnable test checks for VAD audio pipeline, utterance buffer, and
continuous state transition logic.

Verifies:
1. Single utterance path: Start -> Listening -> speak -> 1s silence -> Transcribing
2. Utterance buffer accumulates speech audio correctly
3. Consecutive utterances: the loop returns to Listening and detects again
"""

import time
import numpy as np
from app.vad import SilenceDetector
from app.audio import UtteranceBuffer


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

SAMPLE_RATE = 16000
CHUNK_SAMPLES = 512  # ~32 ms per chunk


def make_silence_chunk():
    """Return a low-amplitude noise chunk that the VAD will classify as silence."""
    return np.random.normal(0, 0.001, CHUNK_SAMPLES).astype(np.float32)


def make_speech_chunk():
    """Return a sine-wave chunk with speech-level amplitude."""
    t = np.linspace(0, CHUNK_SAMPLES / SAMPLE_RATE, CHUNK_SAMPLES, endpoint=False)
    return (0.3 * np.sin(2 * np.pi * 440 * t)).astype(np.float32)


def make_quiet_speech_chunk():
    """Return a realistic low-level microphone speech signal."""
    t = np.linspace(0, CHUNK_SAMPLES / SAMPLE_RATE, CHUNK_SAMPLES, endpoint=False)
    return (0.009 * np.sin(2 * np.pi * 440 * t)).astype(np.float32)


# ---------------------------------------------------------------------------
# Test 1 — Original VAD silence pipeline
# ---------------------------------------------------------------------------

def test_vad_silence_pipeline():
    print("=" * 60)
    print("TEST 1: VAD & 1-Second Silence State Machine")
    print("=" * 60)

    detector = SilenceDetector(silence_duration_sec=1.0, speech_threshold=0.5)
    detector.reset()
    print("[STEP 1] State: Start -> Listening (Recorder active)")

    silence_chunk = make_silence_chunk()

    # Feed 0.5 sec of initial silence
    for _ in range(15):
        res = detector.process_chunk(silence_chunk, sample_rate=SAMPLE_RATE)
        assert not res["utterance_complete"], "Utterance should not complete during initial silence"

    print("[STEP 2] Initial silence processed — no false utterance triggers.")

    # Simulate speech
    speech_chunk = make_speech_chunk()
    print("[STEP 3] User begins speaking...")
    for _ in range(10):
        res = detector.process_chunk(speech_chunk, sample_rate=SAMPLE_RATE)

    assert detector.has_spoken, "Detector should flag that user has spoken"
    print("  -> Speech detected successfully! VAD active.")

    # Silero is optional; the RMS fallback must still detect normal mic levels.
    quiet_detector = SilenceDetector(silence_duration_sec=1.0, speech_threshold=0.5)
    quiet_result = quiet_detector.process_chunk(make_quiet_speech_chunk(), sample_rate=SAMPLE_RATE)
    assert quiet_result["is_speech"], "RMS fallback should detect quiet microphone speech"

    # User stops — wait for 1s silence threshold
    print("[STEP 4] User stops speaking — 1.0 second silence timer running...")
    start_silence_time = time.time()
    utterance_triggered = False

    while time.time() - start_silence_time < 1.2:
        res = detector.process_chunk(silence_chunk, sample_rate=SAMPLE_RATE)
        if res["utterance_complete"]:
            utterance_triggered = True
            elapsed = time.time() - start_silence_time
            print(f"  -> Utterance complete triggered after {elapsed:.2f} seconds of silence!")
            break
        time.sleep(0.03)

    assert utterance_triggered, "1-second silence threshold should trigger utterance_complete"
    print("\n[VERIFICATION PASSED] Path Verified:")
    print("  Start -> Listening -> speak -> 1 second silence -> Transcribing")
    print("=" * 60)


# ---------------------------------------------------------------------------
# Test 2 — Utterance buffer accumulation
# ---------------------------------------------------------------------------

def test_utterance_buffer():
    print()
    print("=" * 60)
    print("TEST 2: Utterance Buffer Accumulation")
    print("=" * 60)

    buf = UtteranceBuffer(pre_speech_chunks=5)
    silence_chunk = make_silence_chunk()
    speech_chunk = make_speech_chunk()

    # Feed some pre-speech silence
    for _ in range(8):
        buf.feed(silence_chunk, is_speech=False)
    print("[STEP 1] Fed 8 silence chunks (only last 5 kept in pre-buffer).")

    # No speech yet — should return None
    assert buf.get_utterance_audio() is None, "Buffer should be empty before speech"
    print("[STEP 2] get_utterance_audio() returns None — correct.")

    # Feed speech chunks
    num_speech = 10
    for _ in range(num_speech):
        buf.feed(speech_chunk, is_speech=True)
    print(f"[STEP 3] Fed {num_speech} speech chunks.")

    # Feed trailing silence (post-speech)
    num_trailing = 3
    for _ in range(num_trailing):
        buf.feed(silence_chunk, is_speech=False)
    print(f"[STEP 4] Fed {num_trailing} trailing silence chunks.")

    # Retrieve utterance
    audio = buf.get_utterance_audio()
    assert audio is not None, "Buffer should contain audio after speech"

    # Expected: 5 pre-speech + 10 speech + 3 trailing = 18 chunks
    expected_chunks = 5 + num_speech + num_trailing
    expected_samples = expected_chunks * CHUNK_SAMPLES
    assert len(audio) == expected_samples, (
        f"Expected {expected_samples} samples, got {len(audio)}"
    )
    print(f"[STEP 5] Utterance audio: {len(audio)} samples "
          f"({expected_chunks} chunks) — correct!")

    assert audio.dtype == np.float32, "Audio should be float32"
    print("[STEP 6] Audio dtype is float32 — correct.")

    # Reset and verify clean state
    buf.reset()
    assert buf.get_utterance_audio() is None, "Buffer should be empty after reset"
    print("[STEP 7] Buffer reset — get_utterance_audio() returns None.")

    print("\n[VERIFICATION PASSED] Utterance buffer accumulates correctly.")
    print("=" * 60)


# ---------------------------------------------------------------------------
# Test 3 — Consecutive utterances (continuous loop state machine)
# ---------------------------------------------------------------------------

def test_consecutive_utterances():
    print()
    print("=" * 60)
    print("TEST 3: Consecutive Utterances — Continuous Loop")
    print("=" * 60)

    detector = SilenceDetector(silence_duration_sec=1.0, speech_threshold=0.5)
    buf = UtteranceBuffer(pre_speech_chunks=5)

    silence_chunk = make_silence_chunk()
    speech_chunk = make_speech_chunk()

    for utterance_num in range(1, 3):
        print(f"\n--- Utterance #{utterance_num} ---")

        # Reset for this utterance (simulates _return_to_listening)
        detector.reset()
        buf.reset()

        # Simulate state = "Listening"
        state = "Listening"
        print(f"  State: {state}")

        # Feed initial silence
        for _ in range(5):
            res = detector.process_chunk(silence_chunk, sample_rate=SAMPLE_RATE)
            buf.feed(silence_chunk, res["is_speech"])
            assert not res["utterance_complete"]

        # Feed speech
        for _ in range(10):
            res = detector.process_chunk(speech_chunk, sample_rate=SAMPLE_RATE)
            buf.feed(speech_chunk, res["is_speech"])
        print(f"  Speech detected: has_spoken={detector.has_spoken}")
        assert detector.has_spoken, f"Utterance #{utterance_num}: speech not detected"

        # Feed silence until utterance completes
        start_t = time.time()
        utterance_triggered = False
        while time.time() - start_t < 1.3:
            res = detector.process_chunk(silence_chunk, sample_rate=SAMPLE_RATE)
            buf.feed(silence_chunk, res["is_speech"])
            if res["utterance_complete"]:
                utterance_triggered = True
                break
            time.sleep(0.03)

        assert utterance_triggered, f"Utterance #{utterance_num}: silence threshold not reached"

        # Verify buffer contains audio
        audio = buf.get_utterance_audio()
        assert audio is not None, f"Utterance #{utterance_num}: buffer is empty"
        assert len(audio) > 0, f"Utterance #{utterance_num}: buffer has zero samples"

        state = "Transcribing"
        print(f"  State: {state} — utterance audio: {len(audio)} samples")

        # Simulate _return_to_listening (after 1.5s delay in GUI)
        state = "Listening"
        print(f"  State: {state} (returned from Transcribing)")

    print("\n[VERIFICATION PASSED] Two consecutive utterances detected and buffered.")
    print("  Listening -> Transcribing -> Listening -> Transcribing [OK]")
    print("=" * 60)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    test_vad_silence_pipeline()
    test_utterance_buffer()
    test_consecutive_utterances()
    print("\n" + "=" * 60)
    print("ALL PHASE 1 TESTS PASSED [OK]")
    print("=" * 60)
