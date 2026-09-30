# Project New Horizon — Product Requirements

## Goal

Create a personal Windows desktop voice assistant that continuously listens during a session, turns spoken questions into fast streamed answers, and stays lightweight.

## V1 user flow

1. The user opens the top-center floating widget.
2. Pressing **Start** begins listening; the button becomes **Stop**.
3. Voice activity detection waits for one second of silence.
4. The completed speech segment is transcribed with Groq Whisper Large V3 Turbo.
5. A local rule-based question detector decides whether the transcript is a question.
6. Questions go to GPT-OSS 120B through Groq and stream their answer into the widget.
7. Listening continues until the user presses **Stop**.

## Requirements

- Always-on-top Windows widget, fixed at the top center.
- Start/Stop continuous listening.
- One-second silence boundary before transcription.
- Groq Whisper Large V3 Turbo for speech-to-text.
- GPT-OSS 120B for answers, with streamed output.
- Short/Free answer-length toggle.
- Keep the visible answer until a new answer starts arriving.
- Queue questions received while an answer is streaming.
- Keep up to five in-memory question-and-answer pairs per session; clear the cache when a new session starts.
- Show clear states: idle, listening, transcribing, thinking, streaming, error.

## Non-goals for V1

- Saving conversation history.
- Accounts, cloud sync, plugins, OCR, screenshots, text-to-speech, or a global hotkey.
- Guaranteed exclusion from screen capture or screen sharing.
