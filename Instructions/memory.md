# Project New Horizon — Development Memory / Knowledge Transfer

> **Last updated:** 2026-07-27  
> **Scope covered:** Phase 1 completion — Working Audio Loop

---

## Starting State (Before Changes)

When work began, the codebase already had a partial Phase 1 implementation with the following files:

### Existing Files

| File | Purpose | Status at start |
|---|---|---|
| `main.py` | Entry point — creates `tk.Tk()`, instantiates `HorizonApp`, runs mainloop | Complete, untouched |
| `app/__init__.py` | Package marker, `__version__ = "0.1.0"` | Complete, untouched |
| `app/audio.py` | `AudioRecorder` class — `sounddevice.InputStream` wrapper with start/stop, chunk callback, error callback, device detection | Complete, untouched |
| `app/vad.py` | `SileroVADDetector` (Silero VAD with RMS fallback) + `SilenceDetector` (1-second silence state machine) | Complete, untouched |
| `app/gui.py` | `HorizonApp` — Tkinter always-on-top widget, Start/Stop button, animated visualizer, state machine, event queue | **Incomplete — had a critical gap** |
| `app/placeholders.py` | Stub classes for Phase 2/3 components (transcriber, question detector, answer engine, context cache) | Complete, untouched |
| `tests/test_audio_vad_pipeline.py` | Single test verifying VAD silence detection path | Complete but limited |

### What Worked

- The widget launched correctly as an always-on-top, borderless, dark-glass floating panel at top-center.
- Start/Stop button toggled recording on/off.
- Microphone audio was captured via `sounddevice` and processed through `SilenceDetector`.
- Voice activity detection correctly identified speech vs. silence using Silero VAD (or RMS energy fallback).
- After speech followed by 1 second of silence, `utterance_complete` fired correctly.
- The GUI transitioned from "Listening" to "Transcribing" on utterance completion.
- The existing test (`test_vad_silence_pipeline`) passed.

### What Was Broken / Missing

1. **Dead-end state**: When the GUI entered "Transcribing", it stayed there **forever**. There was no code to transition back to "Listening". The continuous loop was broken — the widget could only detect one utterance per session.

2. **No audio buffering**: The audio chunks from the microphone were processed by the VAD for classification but **never stored**. When Phase 2 needs to send the utterance to Groq Whisper for transcription, there would be no audio data available. The architecture requires "Send only completed utterances for transcription."

3. **No continuous loop verification**: The test only checked a single utterance. There was no test proving the system could detect two consecutive utterances (the fundamental requirement for a "working audio loop").

---

## Changes Made

### 1. Added `UtteranceBuffer` class to `app/audio.py`

**What:** A new class appended after the existing `AudioRecorder` class (no modifications to `AudioRecorder`).

**Why:** The architecture doc states audio should be accumulated and "only completed utterances" sent for transcription. Without a buffer, the raw audio chunks are processed and discarded — Phase 2 would have nothing to send to Whisper.

**How it works:**

```

Audio chunks flow in via feed(chunk, is_speech):

  Before speech starts:
    └─ chunks go into a rolling deque (pre-buffer, maxlen=10)
       This keeps ~320ms of pre-speech audio so the beginning
       of an utterance isn't clipped.

  When speech starts (first is_speech=True):
    └─ pre-buffer contents are flushed into the main speech_buffer
    └─ all subsequent chunks go directly into speech_buffer

  After speech ends (is_speech=False but speech_started=True):
    └─ trailing silence chunks still go into speech_buffer
       (they're part of the utterance boundary)

  On get_utterance_audio():
    └─ np.concatenate(speech_buffer) → single float32 array
    └─ Returns None if no speech was captured

  On reset():
    └─ Clears both buffers, resets speech_started flag
```

**Design decisions:**
- `pre_speech_chunks=10` default → 10 × 512 samples at 16 kHz = 320ms lookback. Enough to capture plosive onsets without excessive memory.
- Uses `chunk.copy()` to avoid holding references to the sounddevice callback buffer.
- The trailing silence after speech is included in the buffer because the VAD boundary may cut slightly into the last phoneme.
- `collections.deque(maxlen=N)` for the pre-buffer gives O(1) append with automatic eviction.

**Lines added:** 65 lines (class definition + methods), appended at end of file after `AudioRecorder.is_active()`.

---

### 2. Updated `app/gui.py` — Continuous Loop + Buffer Wiring

**What:** Five targeted edits to the existing `HorizonApp` class. No structural changes to the UI layout or animation system.

#### Edit 2a: Import change (line 14)

```python
# Before:
from app.audio import AudioRecorder

# After:
from app.audio import AudioRecorder, UtteranceBuffer
```

#### Edit 2b: New state variables (after line 34)

```python
self.utterance_count = 0           # Running count of completed utterances
self._transcribing_timer_id = None # Tracks the after() timer for Transcribing → Listening
```

**Why:** `utterance_count` gives the user visual proof the loop is working. `_transcribing_timer_id` is needed so Stop can cancel a pending return-to-listening timer (prevents the widget from unexpectedly resuming listening after the user already pressed Stop).

#### Edit 2c: Instantiate UtteranceBuffer (after SilenceDetector init)

```python
self.utterance_buffer = UtteranceBuffer(pre_speech_chunks=10)
```

#### Edit 2d: Wire buffer into audio callback (`start_listening` method)

```python
def audio_chunk_callback(chunk):
    res = self.silence_detector.process_chunk(chunk)
    # NEW: Feed the utterance buffer with speech classification
    self.utterance_buffer.feed(chunk, res["is_speech"])
    self.event_queue.put(("AUDIO_METRICS", res))
```

**Why:** Every audio chunk must go to both the SilenceDetector (for timing) and the UtteranceBuffer (for accumulation). The `is_speech` flag from the VAD result drives the buffer's internal state machine.

Also added `self.utterance_buffer.reset()` at the start of `start_listening()`.

#### Edit 2e: Updated `stop_listening` method

```python
def stop_listening(self):
    # Cancel any pending transcribing→listening timer
    if self._transcribing_timer_id is not None:
        self.root.after_cancel(self._transcribing_timer_id)
        self._transcribing_timer_id = None
    self.recorder.stop_recording()
    self.silence_detector.reset()
    self.utterance_buffer.reset()  # NEW
    self.state = "Idle"
    self.audio_rms = 0.0
    self.speech_prob = 0.0
    self.action_btn.config(text="Start", bg="#3b82f6", activebackground="#2563eb")
```

**Why:** If the user presses Stop while in "Transcribing", the pending `root.after(1500, _return_to_listening)` timer must be cancelled. Otherwise the callback fires later and sets `self.state = "Listening"` even though the user already stopped — violating the rule "The widget listens only after Start and until Stop is pressed."

#### Edit 2f: Updated `_process_events` — utterance completion handling

```python
if data["utterance_complete"]:
    # Transition: Listening -> speak -> 1s silence -> Transcribing
    self.utterance_count += 1
    # Retrieve completed utterance audio (for Phase 2)
    utterance_audio = self.utterance_buffer.get_utterance_audio()
    self._last_utterance_audio = utterance_audio
    self.state = "Transcribing"
    # Schedule return to Listening after brief visual confirmation
    self._transcribing_timer_id = self.root.after(
        1500, self._return_to_listening
    )
```

**Why:** This is the core of the continuous loop. When an utterance completes:
1. Increment the counter (visual feedback).
2. Retrieve the buffered audio and store it on the instance (Phase 2 will use `self._last_utterance_audio`).
3. Set state to "Transcribing" (triggers the purple scanning animation).
4. Schedule automatic return to "Listening" after 1500ms.

**Why 1500ms?** Long enough for the user to see the state change (the scanning shimmer animation is clearly visible), short enough not to miss the next utterance in rapid conversation. In Phase 2 this timer will be replaced by the actual transcription API call duration.

#### Edit 2g: New `_return_to_listening` method

```python
def _return_to_listening(self):
    """Transition from Transcribing back to Listening for the next utterance."""
    self._transcribing_timer_id = None
    if self.state == "Transcribing":
        # Reset VAD and buffer for the next utterance
        self.silence_detector.reset()
        self.utterance_buffer.reset()
        self.audio_rms = 0.0
        self.speech_prob = 0.0
        self.state = "Listening"
```

**Why:** The guard `if self.state == "Transcribing"` ensures this is a no-op if the user already pressed Stop (state would be "Idle") or if an error occurred (state would be "Error"). The VAD and buffer are reset so the next utterance starts with clean state — no stale silence timers or leftover audio from the previous utterance.

#### Edit 2h: Updated Transcribing animation text

```python
# Before:
text="Transcribing..."

# After:
text=f"Transcribing... (utterance #{self.utterance_count})"
```

**Why:** Gives the user visible proof the loop is cycling. When testing manually you can speak, wait, see "#1", speak again, see "#2", etc.

---

### 3. Rewrote `tests/test_audio_vad_pipeline.py`

**What:** Replaced the single test with three comprehensive tests, plus shared helpers.

#### Helpers added:

```python
SAMPLE_RATE = 16000
CHUNK_SAMPLES = 512

def make_silence_chunk():  # Low-amplitude Gaussian noise
def make_speech_chunk():   # 440 Hz sine wave at 0.3 amplitude
```

#### Test 1: `test_vad_silence_pipeline` (preserved original logic)

- Same as the original test, refactored to use the shared helpers.
- Verifies: initial silence → no false triggers → speech detected → 1s silence → `utterance_complete`.

#### Test 2: `test_utterance_buffer` (new)

- Creates an `UtteranceBuffer(pre_speech_chunks=5)`.
- Feeds 8 silence chunks → verifies only the last 5 are kept (deque maxlen).
- Verifies `get_utterance_audio()` returns `None` before any speech.
- Feeds 10 speech chunks + 3 trailing silence chunks.
- Verifies the returned audio has exactly `(5 + 10 + 3) × 512 = 9216` samples.
- Verifies dtype is `float32`.
- Calls `reset()` → verifies buffer is empty.

#### Test 3: `test_consecutive_utterances` (new)

- Runs a full Listening → Transcribing → Listening → Transcribing cycle **twice**.
- For each utterance: resets detector + buffer (simulating `_return_to_listening`), feeds silence, feeds speech, feeds silence until `utterance_complete`, retrieves audio, verifies non-empty.
- Proves the state machine works for consecutive utterances — the fundamental requirement of Phase 1.

#### Encoding fix:

- Replaced Unicode checkmark `✓` with `[OK]` in print statements. Windows cp1252 console encoding cannot render `✓`, causing `UnicodeEncodeError`. This was caught and fixed during the test run.

---

## Files NOT Modified

| File | Reason |
|---|---|
| `main.py` | No changes needed — already correctly creates `HorizonApp` and handles close protocol |
| `app/__init__.py` | No changes needed |
| `app/vad.py` | Already complete and correct — `SileroVADDetector` + `SilenceDetector` work as designed |
| `app/placeholders.py` | These are Phase 2/3 stubs — intentionally untouched until their respective phases |

---

## Test Results

```
============================================================
TEST 1: VAD & 1-Second Silence State Machine
============================================================
[STEP 1] State: Start -> Listening (Recorder active)
[STEP 2] Initial silence processed — no false utterance triggers.
[STEP 3] User begins speaking...
  -> Speech detected successfully! VAD active.
[STEP 4] User stops speaking — 1.0 second silence timer running...
  -> Utterance complete triggered after 1.02 seconds of silence!

[VERIFICATION PASSED] Path Verified:
  Start -> Listening -> speak -> 1 second silence -> Transcribing
============================================================

============================================================
TEST 2: Utterance Buffer Accumulation
============================================================
[STEP 1] Fed 8 silence chunks (only last 5 kept in pre-buffer).
[STEP 2] get_utterance_audio() returns None — correct.
[STEP 3] Fed 10 speech chunks.
[STEP 4] Fed 3 trailing silence chunks.
[STEP 5] Utterance audio: 9216 samples (18 chunks) — correct!
[STEP 6] Audio dtype is float32 — correct.
[STEP 7] Buffer reset — get_utterance_audio() returns None.

[VERIFICATION PASSED] Utterance buffer accumulates correctly.
============================================================

============================================================
TEST 3: Consecutive Utterances — Continuous Loop
============================================================

--- Utterance #1 ---
  State: Listening
  Speech detected: has_spoken=True
  State: Transcribing — utterance audio: 25088 samples
  State: Listening (returned from Transcribing)

--- Utterance #2 ---
  State: Listening
  Speech detected: has_spoken=True
  State: Transcribing — utterance audio: 25088 samples
  State: Listening (returned from Transcribing)

[VERIFICATION PASSED] Two consecutive utterances detected and buffered.
  Listening -> Transcribing -> Listening -> Transcribing [OK]
============================================================

============================================================
ALL PHASE 1 TESTS PASSED [OK]
============================================================
```

---

## Architecture State After Phase 1

```
Widget (gui.py — HorizonApp)
  State machine: Idle → Listening → Transcribing → Listening → ... → Idle
  Start/Stop button
  Animated visualizer (canvas with state-dependent rendering)
  Event queue (thread-safe bridge from audio thread to UI thread)
      |
  AudioRecorder (audio.py)
    sounddevice.InputStream → float32 chunks at 16 kHz
      |
  SilenceDetector (vad.py)
    SileroVADDetector (Silero VAD or RMS fallback)
    1-second silence timer → utterance_complete signal
      |
  UtteranceBuffer (audio.py) ← NEW
    Pre-speech rolling window (10 chunks / 320ms)
    Speech accumulation
    get_utterance_audio() → float32 numpy array ready for Phase 2
      |
  [Phase 2: Groq Whisper — placeholder]
  [Phase 3: Question detector + GPT-OSS 120B — placeholder]
```

---

## Dependency Versions Verified

| Package | Version |
|---|---|
| Python | 3.11 |
| numpy | 2.2.6 |
| sounddevice | 0.5.3 |
| Silero VAD | Available (with fallback to RMS energy if not installed) |

---

## Known Limitations / Notes for Future Phases

1. **Phase 2 Resolved**: The 1500ms fixed delay has been replaced with actual Groq Whisper API calls running in background threads. `self._last_utterance_audio` is now actively consumed by `GroqWhisperClient`.

2. **The audio stream stays open during Transcribing.** This is intentional — the microphone continues capturing during transcription. Chunks arriving during "Transcribing" state are silently discarded by the `if self.state == "Listening"` guard in `_process_events`.

3. **The `utterance_count` is never reset.** It persists across Start/Stop cycles within the same app session as a debug aid.

4. **Windows console encoding:** Any print statements in tests avoid Unicode characters outside cp1252 (using `[OK]` instead of `✓`).

---

## Phase 2 — Transcription

> **Added:** 2026-07-27  
> **Scope covered:** Groq Whisper Large V3 Turbo Integration, Rate-Limit Failover & UI Transcript Display

### Goal & Requirements
- Connect Groq Whisper Large V3 Turbo for speech-to-text.
- Implement rate-limit failover across multiple configured API keys (3 keys configured).
- Display the completed transcript in the UI for debugging / user feedback.
- Maintain smooth non-blocking execution using background threading.

---

### Files Added / Modified in Phase 2

#### 1. Created `.gitignore`, `.env.example`, and `.env`
- `.gitignore`: Ensures `.env`, `__pycache__`, and build artifacts are git-ignored to comply with privacy & security rules.
- `.env.example`: Template showing required key structure (`GROQ_WHISPER_KEY_1`, `GROQ_WHISPER_KEY_2`, `GROQ_WHISPER_KEY_3`, `GROQ_ANSWER_KEY_1`, `GROQ_ANSWER_KEY_2`).
- `.env`: Local configuration file populated with 3 active Groq Whisper API keys.

#### 2. Created `app/config.py`
- `_load_dotenv()`: Dynamically parses local `.env` file without overwriting existing environment variables.
- `load_whisper_keys()`: Collects all numbered `GROQ_WHISPER_KEY_1..N` variables.
- `load_answer_keys()`: Prepares key collection for Phase 3 GPT-OSS answer keys.

#### 3. Created `app/transcription.py`
- `GroqWhisperClient`: Core client using model `whisper-large-v3-turbo`.
- `_audio_to_wav(audio, sample_rate)`: Converts 1D float32 numpy arrays ([-1, 1]) to 16-bit mono PCM WAV bytes in-memory using `io.BytesIO` and `wave`.
- Rate-limit handling: On HTTP 429 (`RateLimitError`), puts the current key into a 30-second cooldown (`COOLDOWN_SECONDS = 30`) and attempts the next eligible key.
- `AllKeysExhaustedError`: Raised if all configured keys are in active cooldown or fail with rate-limits.

#### 4. Updated `app/placeholders.py`
- Removed `Phase2TranscriberPlaceholder` (replaced by production `GroqWhisperClient`).

#### 5. Updated `app/gui.py`
- Expanded window dimensions from `440x110` to `440x180` to accommodate transcript display area.
- Added `transcript_label` styled with dark glass aesthetic (`#0f111a` background, soft violet text `#c4b5fd` for success, soft red `#fca5a5` for errors).
- Threading: Replaced fixed 1.5s timer with `_start_transcription(utterance_audio)` which runs in a background thread `_transcribe_worker`.
- Event Queue Integration: Worker posts `TRANSCRIPTION_DONE` (with transcript text) or `TRANSCRIPTION_ERROR` (with error message) back to `event_queue`.
- Error recovery: Soft error notification displayed without crashing; widget automatically returns to listening after 2.5 seconds on error.

#### 6. Created `tests/test_transcription.py`
- 5 comprehensive automated tests using `unittest.mock`:
  1. `test_wav_conversion`: Verifies PCM 16-bit 16kHz mono header generation.
  2. `test_successful_transcription`: Mocks Groq client API response.
  3. `test_rate_limit_failover`: Mocks 429 on Key 1, verifies failover to Key 2.
  4. `test_cooldown_tracking`: Verifies active cooldown keys are skipped.
  5. `test_all_keys_exhausted`: Verifies `AllKeysExhaustedError` when all keys return 429.

---

### Verification & Test Summary

All 8 tests across Phase 1 and Phase 2 passed cleanly:
- `python -m tests.test_audio_vad_pipeline` (3/3 PASSED)
- `python -m tests.test_transcription` (5/5 PASSED)
- Live key verification confirmed 3 Groq API keys loaded from `.env`.

---

---

## Phase 3 — Answers & Streaming Engine

> **Added:** 2026-07-27  
> **Scope covered:** Local Question Detection, Groq GPT-OSS 120B Streaming, 5-Pair RAM Context Cache, FIFO Question Queue, Short/Free Mode Toggle & Answer UI View

### Goal & Requirements
- Add local rule-based question detection (0 network calls).
- Connect Groq GPT-OSS 120B (`openai/gpt-oss-120b`) for streaming completions.
- Implement rate-limit failover across 3 dedicated answer API keys (`GROQ_ANSWER_KEY_1..3`).
- Add Short / Free answer length toggle.
- Maintain a 5-pair RAM-only session context cache (FIFO eviction, reset on new session).
- Add FIFO question queue for questions received while an answer is currently streaming.
- Render dark-glass streaming answer view with animated `Thinking` and `Streaming` motion states.

---

### Files Added / Modified in Phase 3

#### 1. Updated `.env` and `.env.example`
- `.env`: Populated with 3 dedicated Groq GPT-OSS 120B API keys (`GROQ_ANSWER_KEY_1`, `GROQ_ANSWER_KEY_2`, `GROQ_ANSWER_KEY_3`).
- `.env.example`: Updated template showing answer key configurations.

#### 2. Created `app/question_detector.py`
- `QuestionDetector`: Fast, rule-based classification evaluating transcript text:
  - Explicit question marks (`?`).
  - Interrogative starters (`who`, `what`, `where`, `when`, `why`, `how`, `which`, `whose`, `whom`).
  - Auxiliary sentence openers (`is`, `are`, `can`, `could`, `do`, `does`, `would`, `should`, `have`, `has`, etc.).
  - Direct request/command phrases (`tell me`, `explain`, `describe`, `show me`, `define`, `list`, `give me`).
- Zero network calls, sub-millisecond local execution.

#### 3. Created `app/context_cache.py`
- `ContextCache`: RAM-only FIFO memory holding up to 5 recent `{"question": q, "answer": a}` pairs.
- Evicts oldest entry when 5-pair capacity limit is exceeded.
- Formats messages into OpenAI/Groq chat structure (`user` / `assistant`).
- Cleared when a new listening session starts; never saved to disk.

#### 4. Created `app/question_queue.py`
- `QuestionQueue`: Thread-safe FIFO queue (`queue.Queue` wrapper) for questions received while an answer is currently streaming.
- Dequeues and triggers next answer stream automatically upon completion of current answer.

#### 5. Created `app/answer_engine.py`
- `GroqAnswerEngine`: Streaming completion client using model `openai/gpt-oss-120b` (with fallback to `llama-3.3-70b-versatile`).
- System prompts tailored for modes:
  - **Short**: Concise, direct answers in 1–2 sentences maximum without preamble.
  - **Free**: Natural, complete responses.
- Multi-key failover: On HTTP 429 (`RateLimitError`), puts key into a 30-second cooldown (`COOLDOWN_SECONDS = 30`) and fails over to the next eligible key.
- `AllAnswerKeysExhaustedError`: Raised if all answer keys are rate-limited.

#### 6. Updated `app/config.py`
- `load_answer_keys()`: Loads `GROQ_ANSWER_KEY_1..N` with fallback to `load_whisper_keys()` if answer keys are not set.

#### 7. Updated `app/placeholders.py`
- Removed Phase 3 placeholder stubs (`Phase3QuestionDetectorPlaceholder`, `Phase3AnswerEnginePlaceholder`, `Phase3ContextCachePlaceholder`) as all systems are fully implemented.

#### 8. Updated `app/gui.py`
- Window height expanded from `440x180` to `440x260` to fit dark-glass answer view.
- Added **💬 Short | Free** mode toggle button in top header bar.
- Added scrollable dark-glass answer text area (`self.answer_text`).
- Preserves previous answer text across sessions until new answer text begins arriving.
- Integrated background answer worker thread dispatches events:
  - `ANSWER_FIRST_TOKEN`: Clears answer view, sets state to `Streaming`.
  - `ANSWER_CHUNK`: Appends text chunk, auto-scrolls, updates pulsing caret.
  - `ANSWER_DONE`: Saves pair to `ContextCache`, returns to `Listening`, processes queued question if present.
  - `ANSWER_ERROR`: Displays error message, handles graceful recovery.
- Motion States: Added `Thinking` (pulsing amber indicator) and `Streaming` (active emerald pulse).

#### 9. Created `tests/test_answer_pipeline.py`
- 5 unit & integration tests:
  1. `test_question_detector`: Tests questions vs statements across rules.
  2. `test_context_cache`: Tests 5-pair capacity limit, FIFO eviction, formatting, clear.
  3. `test_question_queue`: Tests FIFO ordering & thread safety.
  4. `test_answer_engine_streaming`: Mocks Groq GPT-OSS 120B streaming tokens.
  5. `test_answer_engine_failover`: Mocks 429 rate limit on Key 1, verifies failover to Key 2.

---

### Verification & Test Summary

All 13 tests across Phase 1, Phase 2, and Phase 3 passed cleanly:
- `python -m tests.test_audio_vad_pipeline` (3/3 PASSED)
- `python -m tests.test_transcription` (5/5 PASSED)
- `python -m tests.test_answer_pipeline` (5/5 PASSED)
- Live key verification confirmed 3 dedicated answer keys loaded from `.env`.

---

## Phase 4 — Polish & Resilience

> **Added:** 2026-07-27  
> **Scope covered:** Complete Motion Table Alignment, Reduced Motion Compliance, Answer Preservation Lifecycle, Microphone Diagnostics & Offline Network Error Resilience

### Goal & Requirements
- Implement motion table animations (`Idle` breathing, `Silence` waveform contraction, `Thinking` orbiting dots, `Streaming` active pulse, `Complete` confirmation pulse).
- Full `Reduced Motion` accessibility support replacing animations with static indicators.
- Preserve previous answer text across sessions and UI transitions until new answer text starts arriving.
- Microphone permission and diagnostic device status check (`AudioRecorder.check_microphone_status()`).
- Offline network error resilience mapping (`NetworkOfflineError`) to prevent UI crashes and afford smooth recovery.

---

### Files Added / Modified in Phase 4

#### 1. Updated `app/audio.py`
- Added `check_microphone_status()` class method to `AudioRecorder` to inspect input device availability and default audio device configuration before streaming.

#### 2. Updated `app/transcription.py` & `app/answer_engine.py`
- Defined `NetworkOfflineError` exception classes.
- Explicitly catch connection failures, DNS resolution errors, and offline network exceptions (`APIConnectionError`, `URLError`, `gaierror`).
- Returns human-readable error messages for calm non-blocking UI status display.

#### 3. Updated `app/gui.py`
- Integrated `AudioRecorder.check_microphone_status()` check into `start_listening()`.
- Implemented complete motion table from `design.md`:
  - **`Idle`**: Soft breathing blue accent + subtle border glow (Static blue in Reduced Motion).
  - **`Listening`**: Volume-reactive 16-bar frequency visualizer.
  - **`Silence`**: Smooth 250ms waveform contraction when speech ends before transcription.
  - **`Transcribing`**: Quiet scanning shimmer line.
  - **`Thinking`**: 3 orbiting/pulsing amber dots.
  - **`Streaming`**: Active emerald pulse visualizer.
  - **`Complete`**: 400ms emerald pulse confirmation visual before returning to `Listening`.
  - **`Error`**: Soft red status label (`#fca5a5`) without blocking modals.
- Answer Text Preservation: Answer text view is preserved across state transitions and cleared ONLY when replacement text actually begins arriving (`ANSWER_FIRST_TOKEN`).

#### 4. Created `tests/test_phase4_polish.py`
- 3 comprehensive unit & integration tests:
  1. `test_microphone_status_check`: Validates `AudioRecorder.check_microphone_status()`.
  2. `test_transcription_network_offline_error`: Tests offline connection error mapping in `GroqWhisperClient`.
  3. `test_answer_engine_network_offline_error`: Tests offline connection error mapping in `GroqAnswerEngine`.

---

### Full System Test Summary

All 16 unit & integration tests across Phase 1, Phase 2, Phase 3, and Phase 4 passed cleanly:
- `python -m tests.test_audio_vad_pipeline` (3/3 PASSED)
- `python -m tests.test_transcription` (5/5 PASSED)
- `python -m tests.test_answer_pipeline` (5/5 PASSED)
- `python -m tests.test_phase4_polish` (3/3 PASSED)

---

### Final Project Architecture State

```
Widget (gui.py — HorizonApp)
  State machine: Idle → Listening → Transcribing → Thinking → Streaming → Complete → Listening → ... → Idle
  Header controls: Start/Stop, Motion Mode (Standard / Reduced), Short/Free Mode Toggle
  Display Panels: Audio visualizer (440x44), Transcript (440x30), Answer view (440x100)
  Event Queue: AUDIO_METRICS, TRANSCRIPTION_DONE, ANSWER_FIRST_TOKEN, ANSWER_CHUNK, ANSWER_DONE, ...
  Resilience: AudioRecorder.check_microphone_status(), NetworkOfflineError handling, non-blocking UI
      |
  AudioRecorder (audio.py) → SilenceDetector (vad.py) + UtteranceBuffer (audio.py)
      | (on utterance completion)
  GroqWhisperClient (app/transcription.py) [Background Worker Thread]
    Model: whisper-large-v3-turbo (Multi-key failover + 30s cooldown + NetworkOfflineError handling)
      | (on transcript completion)
  QuestionDetector (app/question_detector.py) [Fast Local Rule Check - 0 network calls]
      ├─ Not a Question ──> Display transcript → Return to Listening
      └─ Is a Question ──> Check if currently streaming:
                               ├─ Streaming Active ──> QuestionQueue (app/question_queue.py)
                               └─ Idle / Ready ─────> GroqAnswerEngine (app/answer_engine.py)
                                                        Model: openai/gpt-oss-120b (Stream=True)
                                                        Config: load_answer_keys() from .env
                                                        Context: ContextCache (app/context_cache.py) [Last 5 Q&A]
                                                        Mode: System Prompt ("Short" vs "Free")
```

---

## Phase 5 — Premium Glass UI & Answer Motion

> **Added:** 2026-07-28  
> **Scope covered:** premium dark-glass visual refresh, colored controls, and native streaming-answer motion.

### Changes

- Updated `app/gui.py` to a larger `520x330` floating glass surface with layered dark panels, brighter borders, and a clearer response hierarchy.
- Applied semantic action colors: **Start** uses a glass-yellow surface; **Stop** switches to a glass-red surface; answer mode, motion, and close controls use restrained dark-glass surfaces.
- Converted the secondary controls from click-bound labels to native buttons, preserving keyboard activation and pressed states.
- Replaced emoji control labels with text labels for consistent Windows rendering.
- Replaced the streaming `Text` widget with a native Tk canvas renderer:
  - queued model chunks reveal left-to-right at four characters per animation frame;
  - completed lines stay above the incoming line in normal top-to-bottom reading order;
  - a warm caret shows the active streaming position;
  - the newest six lines remain visible in the compact widget.
- Reduced Motion remains supported: answer text renders immediately and line movement resolves without animation.
- The completion transition waits for the visual queue to finish, preventing a queued question from replacing a still-animating answer.

### Design Notes

- Tkinter cannot provide real translucent blur or per-line transforms. The layered surfaces, fine borders, and canvas translation supply the glass depth and motion without adding a UI dependency or changing the live backend flow.
- The animation updates only the existing 30 FPS loop and uses canvas drawing, so it does not introduce a second timer or block audio/network events.
- **Correction:** the widget is now a fixed compact top-center surface; vertical reordering was removed because it inverted answer order and harmed readability.
