# Project New Horizon — Implementation Rules

## Product rules

- The widget listens only after Start and until Stop is pressed.
- One second of silence closes an utterance.
- Non-questions are not sent to the answer model.
- Questions received while an answer is in progress are queued in order.
- Keep only five Q&A pairs in RAM for the active session.
- Reset that cache when a new session starts.
- Keep the latest visible answer after Stop and across a new session until a replacement arrives.
- Do not persist transcripts, answers, or API keys to project files.

## API rules

- Use the configured Whisper keys only for transcription and configured GPT keys only for answers.
- Fail over only after an actual rate-limit response; do not rotate on every request.
- Put rate-limited keys into a short cooldown before trying them again.
- Show an error after all eligible keys fail; do not silently discard an utterance.
- Read keys from environment variables or an ignored local configuration file.

## Engineering rules

- Keep the v1 architecture small: direct components, no speculative plugin system or database.
- Use cancellation on Stop for unfinished audio work; do not corrupt the answer already on screen.
- Validate network responses and handle microphone permission or device errors explicitly.
- Keep UI work separate from recording and network work so animations remain responsive.
- Test each non-trivial pipeline change with a small runnable check.

## Privacy rules

- Audio is sent only to the selected transcription provider for active utterances.
- Session memory is RAM-only and cleared between sessions.
- Do not claim the app is universally invisible to screen capture or sharing software.
