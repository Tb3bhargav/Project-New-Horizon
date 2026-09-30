# Project New Horizon — Architecture

```text
Widget
  Start/Stop
      |
Microphone capture
      |
Voice activity + 1 s silence
      |
Groq Whisper Large V3 Turbo
      |
Local question rules ---- not a question --> resume listening
      |
Session cache (last 5 Q&A)
      |
Groq GPT-OSS 120B (stream)
      |
Animated answer view
```

## Components

### Widget

Owns UI state, the Start/Stop control, short/free toggle, transcript status, answer rendering, and the question queue. It is always on top and positioned top-center.

### Audio pipeline

Capture audio while a session is active. Use voice activity detection to discard silence and complete an utterance after one second without speech. Send only completed utterances for transcription.

### Transcription client

Call Groq's OpenAI-compatible transcription endpoint with `whisper-large-v3-turbo`. On a rate-limit response, try the next configured transcription key. Treat other failures as visible errors.

### Question detector

Use local rules only: interrogative words and auxiliary openings, an ending question mark when provided by the transcript, and direct forms such as “tell me” or “explain”. It must be fast and make no network call.

### Answer client

Send the current question plus at most five recent Q&A pairs when relevant. Request a streamed completion from GPT-OSS 120B. On a rate-limit response, try the next configured answer key.

### Session state

Keep state only in memory:

- active/inactive session
- five Q&A pairs maximum
- current answer buffer
- queued questions
- recent failures and key cooldowns

Starting a new session clears the Q&A cache but does not clear the displayed answer.
