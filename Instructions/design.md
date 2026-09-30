# Project New Horizon — Visual Design

## Direction

A compact, futuristic command widget: dark glass surface, cool blue/violet accent light, readable text, and restrained movement. The UI should feel alive without delaying any interaction.

## Layout

Top-center, always-on-top floating panel:

```text
● New Horizon                         Short | Free
Listening…                       [ Stop ]

What is the capital of France?

Paris is the capital and most populous city of France. |
```

- Keep the panel narrow enough not to dominate the screen.
- Put the primary state and Start/Stop control in the first row.
- Keep the previous answer in place until new streamed text replaces it.
- Use a scroll area only when the answer exceeds the panel height.

## Motion states

| State | Motion |
| --- | --- |
| Idle | Soft breathing accent and a subtle border shimmer. |
| Listening | Audio-reactive waveform and glow driven by input volume. |
| Silence | Waveform contracts over 200–300 ms. |
| Transcribing | Quiet scanning shimmer over the transcript area. |
| Thinking | Three orbiting dots or a compact pulsing light. |
| Streaming | Text fades in as it arrives; a caret pulses at the end. |
| Complete | One brief confirmation pulse, then return to idle. |
| Error | Calm red status text; never a blocking modal for transient failures. |

## Accessibility and performance

- Respect reduced-motion preferences: replace motion with static state changes.
- Maintain strong text contrast and clear keyboard focus.
- Prefer opacity and transform animations; avoid layout-heavy animation.
- Cap visual updates to the display refresh rate and never block audio or network work.
