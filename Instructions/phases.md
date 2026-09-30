# Project New Horizon — Delivery Phases

## Phase 1 — Working audio loop

- Create the always-on-top top-center widget.
- Add Start/Stop and state text.
- Capture microphone audio.
- Detect voice and one second of silence.

**Done when:** a spoken utterance reliably changes the UI from listening to transcribing.

## Phase 2 — Transcription

- Connect Groq Whisper Large V3 Turbo.
- Add configured-key failover on rate limits.
- Display the completed transcript for debugging.

**Done when:** normal speech becomes a transcript and rate-limit handling is visible and safe.

## Phase 3 — Answers

- Add local question detection.
- Connect GPT-OSS 120B streaming.
- Add the short/free toggle, five-pair RAM cache, and FIFO queue.

**Done when:** a question streams an answer and a follow-up can use recent context.

## Phase 4 — Polish

- Add the motion states and reduced-motion support.
- Keep the previous answer until replacement begins.
- Improve errors, microphone permissions, and offline behavior.

**Done when:** the widget feels responsive in normal daily use without lost questions or unexplained failures.

## Later, only if needed

- Global shortcut.
- Local transcription fallback.
- OCR/screenshot analysis.
- Text-to-speech.
