# Parakeet AI Frontend Clone Guide

**Purpose:** This document is a complete visual and interaction specification for an AI coding agent. Follow it literally when rebuilding a product UI that *looks and feels* like Parakeet AI (https://www.parakeet-ai.com).

**Scope:** Visual design, layout, components, copy tone, motion, and page/screen structure only. Do **not** copy trademarks, the official parrot logo artwork, or marketing claims. Do **not** implement “undetectable / stealth / hidden-from-interviewer” behavior. Build a legitimate real-time call / interview *practice* assistant.

**Brand substitute:** Use a new product name and a simple geometric bird mark (not the official cartoon parrot). Keep the *design system* below.

---

## 1. Product surfaces to clone

Parakeet AI is not one screen. Recreate these four surfaces:

| Surface | Role | Theme |
|---|---|---|
| **Marketing site** | Landing, features, reviews, privacy, pricing | Light, airy, high-trust SaaS |
| **Auth** | Sign in / create account | Light, centered, minimal |
| **Web app / dashboard** | Sessions, credits, prepare a call, live session | Light product UI |
| **Desktop overlay** | Compact always-on-top assistant during a call | Dark glass, dense, glanceable |
| **Mobile web** | Same flows, stacked, large tap targets | Light, `/mobile` layout |

The overlay is the signature product UI. The marketing site is the signature brand UI. Both must be implemented.

---

## 2. Design principles (follow these first)

1. **One composition, not a dashboard.** The first viewport of the marketing site is a single hero composition: logo bar, social proof strip, huge headline, two CTAs, soft gradient. No cards, no sidebar, no 12-widget grid.
2. **Calm confidence.** Lots of white. One green accent. Almost no decoration besides the parrot/bird mark and soft radial washes.
3. **Pill geometry.** Nav bar, CTAs, chips, and toggles are stadium/pill shaped (`border-radius: 9999px`). Cards use 16–24px radius. Overlay uses tighter 8–10px radius.
4. **Green is meaning, not wallpaper.** Green appears on the hero keyword, primary CTA, active states, “listening / done” status, and success. Everything else is near-black, gray, or white.
5. **Glanceable during a call.** Overlay text is small, high-contrast, scrollable, and never fights the meeting. Status is always visible. Primary action is always one large button.
6. **Two typefaces max.** One geometric sans for UI. One monospace for transcripts, shortcuts, and code.
7. **Motion is functional.** 150–200ms color/opacity transitions. Recording pulse. Spinner. No hero parallax, no bounce, no purple gradients, no glassmorphism on the marketing site.
8. **Trust before features.** Avatars, star rating, “used by X people,” platform logos, and short first-person reviews sit above or immediately after the fold.

---

## 3. Design tokens

### 3.1 Marketing / web app (light)

```css
:root[data-theme="light"] {
  --bg: #ffffff;
  --bg-wash-a: rgba(180, 245, 220, 0.45);   /* mint, bottom-left */
  --bg-wash-b: rgba(235, 250, 170, 0.40);   /* pale lime, bottom-right */
  --surface: #ffffff;
  --surface-2: #f7f8f8;
  --text: #111111;
  --text-secondary: #5b6168;
  --muted: #8b929a;
  --line: #e7e9ec;
  --accent: #22c55e;          /* hero keyword + primary CTA */
  --accent-hover: #16a34a;
  --accent-ink: #ffffff;
  --ink-button: #111111;      /* “Try for Free” in nav */
  --ink-button-text: #ffffff;
  --star: #f5b301;
  --shadow-nav: 0 8px 28px rgba(17, 17, 17, 0.06);
  --shadow-card: 0 1px 2px rgba(17, 17, 17, 0.04), 0 12px 32px rgba(17, 17, 17, 0.06);
  --radius-pill: 9999px;
  --radius-card: 20px;
  --radius-input: 12px;
  --nav-height: 64px;
}
```

Approximate hero green is a vivid mid-green, closer to `#22C55E` than teal. Do not use purple, indigo, or neon cyan on marketing.

### 3.2 Desktop overlay (dark glass)

```css
:root[data-theme="overlay"] {
  --bg: rgba(10, 11, 15, 0.93);
  --surface: rgba(255, 255, 255, 0.04);
  --border: rgba(255, 255, 255, 0.08);
  --text: #e8eaf0;
  --muted: rgba(255, 255, 255, 0.38);
  --accent: #00d4aa;          /* parrot-teal, overlay only */
  --accent-dim: rgba(0, 212, 170, 0.12);
  --primary: #3b82f6;         /* generate-answer */
  --primary-dim: rgba(59, 130, 246, 0.12);
  --danger: #ff4757;
  --danger-dim: rgba(255, 71, 87, 0.12);
  --radius: 10px;
}
```

Overlay uses `backdrop-filter: blur(24px)`. Body behind the overlay is transparent.

### 3.3 Typography

| Role | Face | Weight | Size (marketing) | Size (overlay) |
|---|---|---|---|---|
| Display H1 | Geometric sans (Inter Tight / Geist / Satoshi) | 700–800 | 56–72px, tight tracking, 1.05 line-height | — |
| Section H2 | Same | 700 | 32–40px | — |
| Body | Inter or Geist | 400–500 | 16–18px, #5b6168 | — |
| Nav / buttons | Same | 500–600 | 14–15px | 11–13px |
| Logo wordmark | Same | 700 | 18px | 13px |
| Transcript / status / code | JetBrains Mono or IBM Plex Mono | 400 | 13–14px | 11–12px |
| Overline / hint | Same sans | 500, uppercase optional | 12px | 10px |

Hero treatment: two-line headline. The middle phrase **Real-Time** is `--accent` green. Surrounding words are `--text` near-black.

```
Your [Real-Time]          ← green
AI Call Assistant         ← black
```

### 3.4 Iconography

- Simple, 1.5–2px stroke, rounded caps.
- Marketing: outline icons in feature rows (mic, sparkles, code, shield).
- Overlay: text + tiny symbols only (🦜 or custom mark, ✕, 🎙️, 🔊, trash, arrows).
- Platform row: official-style monochrome or color logos for Zoom, Meet, Teams, HackerRank, LeetCode — as simple SVG marks.

---

## 4. Marketing website specification

### 4.1 Global chrome

**Floating pill nav** (sticky):

- Centered, max-width ~1120px, sits 16–20px from the top.
- White fill, 1px `#eee` border, large pill radius, soft shadow.
- Left: bird mark + wordmark **Parakeet** + tiny black **AI** badge.
- Center links (gray, 14px): Features · Reviews · Privacy · Pricing.
- Right: `Sign in` (white, 1px border, pill) and `Try for Free` (solid black pill).
- Hover on text links: color → near-black.

**Page background:** pure white with two large, heavily blurred radial gradients near the bottom of the hero (mint left, lime right). Gradients fade to white. No grid, no noise texture.

**Footer:** simple columns — product links, support email, legal. Small, gray. No fat mega-footer.

### 4.2 Homepage sections (in order)

Replicate this information architecture. Do not invent extra sections.

1. **Nav**
2. **Social proof strip** — overlapping circular avatars (3 people) + “Trusted by 1.5M+ people” + gold stars + “4.86 from 340K+ reviews” + divider + laurel “No. 1 Viral App” + SimilarWeb “#1 AI Call Assistant”.
3. **Hero** — H1 as specified, one sentence subtitle in `--text-secondary`, two CTAs:
   - Primary: green pill `Try ParakeetAI for Free →`
   - Secondary: white pill with play icon `Demo Video`
4. **How it works** — three short steps, large numbers or simple icons:
   - Create a session
   - Check mic and audio
   - Get answers instantly
5. **Session builder preview** — a light card that looks like the real “create session” form (see §6). This is a product screenshot-style composition, not a stock photo.
6. **Works with any platform** — logo row.
7. **Feature split sections** (alternate left/right):
   - Programming / coding interview support
   - Blazing-fast transcription
   - AI answers (model choice)
   Keep one H2, one short paragraph, one visual (code block, transcript pane, or answer card).
8. **“Set up once” capability grid** — Auto Answer, Auto-detect meetings, Documents, AI Notes, Mock Sessions. 2–3 columns of quiet cards (`--surface-2`, 20px radius, no heavy border).
9. **Testimonials** — first-name + initial, short quote, date. Light cards. No wall of 50 reviews on the homepage; link to Reviews.
10. **Privacy / “private advantage”** — simple checklist of privacy claims that are *honest for your clone* (local audio, no joining the call as a bot, etc.). Do not claim “invisible in Task Manager.”
11. **Desktop / browser / mobile trio**
12. **FAQ accordion**
13. **Pricing cards**
14. **Final CTA** — same green button, “no credit card” microcopy.

### 4.3 Marketing UI rules

- One H1 only.
- Max two typefaces.
- Max one accent color.
- Buttons are pills. Height ~44–48px. Never sharp rectangles.
- Feature visuals sit in a white rounded frame with a hairline border and soft shadow — like a product photo of the overlay or session form.
- Code samples use a dark mini-editor (overlay tokens) even on the light page.
- Avoid: purple SaaS gradients, 3D blobs, generic dashboard mockups, Inter-everywhere-with-blue-600.

### 4.4 Auth page

- Same bird mark centered or top-left.
- Heading: “Sign in or create an account”
- One-line purpose sentence.
- Full-width pill `Continue with Google`
- Centered `OR` divider
- Full-width pill `Continue with Email`
- Tiny legal line under buttons.
- Optional note: stay signed in on one desktop and one mobile.
- No illustration required. Lots of whitespace.

### 4.5 Pricing

Three equal cards: Weekly / Monthly / Yearly.

- Monthly has a small “Most popular” chip in green.
- Price is huge, billing period is muted.
- 3–5 check rows.
- CTA on each card: dark or green pill `Get Weekly` / `Get Monthly` / `Get Yearly`.
- Mention a short free session + credit packs as an alternative, not a fourth card unless needed.

---

## 5. Web app / dashboard specification

Light theme. After login the marketing nav is replaced by a compact product shell.

### 5.1 Shell

**Left or top utility rail** (keep it light, not a heavy Slack sidebar):

- Support
- Tutorials
- Support chat
- Free plan / Upgrade
- Theme toggle (`Theme Light`)
- Open Desktop App
- Log out
- User chip: avatar initials + name + email

**Main column:**

- Page title: `Call Sessions`
- Subtitle: `Prepare for calls and review past sessions.`
- Primary button: green `New session`

### 5.2 Session list

Rows or cards:

- Session title (company or “Untitled call”)
- Type chip: Interview | Regular call | Coding
- Relative date
- Duration / credit use
- Status: Draft · Ready · Completed
- Hover: hairline lift + `Open`

Empty state: bird mark, one sentence, green `Create your first session`.

### 5.3 Create / prepare session (critical screen)

A single scrolling form, not a wizard with 7 steps. Groups:

**Session type** — segmented control (pill): `Interview` | `Regular Call`  
**Company** — text; optional “autofill from job URL”  
**Job description** — large textarea  
**Context** — attach resume / documents / extra notes  
**Output settings**
- Model select (show 3 options as radio cards, e.g. Fast / Balanced / Strong)
- Language dropdown
**Behavior**
- Auto answer toggle
- Save transcript toggle

Footer of form: `Cancel` (ghost) + `Start session` (green pill).

Visual: labels 13px muted, inputs 14–16px, 12px radius, 1px `--line`. Focus ring is 2px `--accent` at 30% opacity.

### 5.4 Live web session

A three-zone workspace on desktop:

```
┌────────────┬──────────────────────────────┐
│ Transcript │ Answer                       │
│ (left,     │ (right, larger)              │
│  ~38%)     │ markdown + code              │
├────────────┴──────────────────────────────┤
│  [Answer] [Screenshot] [Chat] [Clear]     │
│  listening indicator · language · model   │
└───────────────────────────────────────────┘
```

**Toolbar buttons** (match official labels):

| Button | Style | Meaning |
|---|---|---|
| Answer | Primary green or blue | Generate answer from latest transcript |
| Screenshot | Secondary | Capture screen / shared coding problem |
| Chat | Secondary | Manual question box |
| Clear | Ghost / muted | Clear transcript or answers (two actions or a split) |

Also show:

- Listening / paused indicator (green pulsing dot vs gray)
- Optional mic connect
- Auto-scroll toggle
- Copy on code blocks
- Previous / next answer arrows when history exists

**Answer typography:** readable 15–16px, generous line-height, markdown headings, fenced code with copy button top-right of the block. Coding answers: problem recap → solution code → complexity note.

**Mobile web (`/mobile`):** stack transcript above answer; sticky bottom action bar with the four buttons; no multi-column.

---

## 6. Desktop overlay specification (signature UI)

A compact, frameless, always-on-top panel. Default width ~360–420px. User can drag, resize from a bottom-right handle, and hide/show with a shortcut.

### 6.1 Window chrome

```
┌─────────────────────────────────────────┐
│ 🦜 Name     [Interview | Coding]    ✕  │  ← drag handle
├─────────────────────────────────────────┤
│ status: Listening · Thinking · Ready    │
│ [optional device select]                │
│                                         │
│ Heard:                                  │
│ …transcript…                            │
│                                         │
│ Answer:                                 │
│ …streamed markdown…                     │
│                                         │
│ [ Start / Answer / Capture ]            │
│ [ Clear ]                               │
│ Drag top · shortcut to hide             │
└─────────────────────────────────────────┘
```

**Header**

- Left: mark + wordmark (accent teal, 13px, bold).
- Center: segmented `Interview` / `Coding` (6px radius track, active segment filled `--accent-dim` with `--accent` text).
- Right: close `✕` (muted, danger on hover).
- Entire header is the drag region (`cursor: move`).
- 10×14px padding, hairline `--border` bottom.

**Overflow menu (⋯)** on a more complete clone of the official desktop app:

- Account / credits remaining
- Buy credits
- Open dashboard in browser
- Zoom in / out / reset
- Log out
- Move
- Hide

Official desktop also shows credits at the top and a red close.

### 6.2 Status bar

Monospace 11px, 6px radius, full width inside padded column.

| Status | Color |
|---|---|
| idle | muted |
| recording / listening | danger or live red, optional pulse |
| transcribing | primary blue |
| thinking | primary blue |
| done | accent teal |
| error | danger |

### 6.3 Interview mode controls

1. Device `<select>` (system audio vs mic), disabled while recording.
2. Big action button:
   - Idle: `Start Recording` / `Start listening` — `--primary`
   - Live: `Stop` — `--danger` + 1.5s opacity pulse
3. `Answer` / `AI help` — generates from current transcript.
4. `Clear context` / `Clear` — secondary.
5. Optional `Chat` for typed questions.

### 6.4 Coding mode controls

- Primary: `Capture & Solve` / `Analyze screen`
- Answer label becomes `Solution`
- Render fenced code with syntax highlight on the dark panel
- Copy button

### 6.5 Content sections

`.section` — 1px `--border`, 10px radius, 10px padding, 14px side margins.

- Label: 10px, uppercase or small, muted.
- Transcript: 11px mono, max-height, custom 3px scrollbar.
- Answer: 12px sans or mono, streamed tokens, same scroll rules.
- While busy and no text yet: 18px spinner (border `--border`, top `--accent`, spin 0.7s linear).

Hint line under controls, 10px, 40% opacity:  
`Drag top · Esc to hide`

### 6.6 Overlay CSS skeleton (use this)

```css
.overlay {
  display: flex;
  flex-direction: column;
  gap: 8px;
  min-height: 100vh;
  padding-bottom: 10px;
  background: var(--bg);
  backdrop-filter: blur(24px);
  -webkit-backdrop-filter: blur(24px);
  color: var(--text);
  font-family: Inter, Geist, system-ui, sans-serif;
  border-radius: var(--radius);
  overflow: hidden;
}
.action-btn {
  width: 100%;
  border: 0;
  border-radius: 10px;
  padding: 10px 12px;
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.15s;
}
.action-btn.primary { background: var(--primary); color: #fff; }
.action-btn.danger  { background: var(--danger);  color: #fff; animation: pulse 1.5s ease-in-out infinite; }
.action-btn.secondary { background: var(--surface); color: var(--muted); border: 1px solid var(--border); }
```

### 6.7 Overlay interaction map

Implement as *visible product shortcuts* (do not build stealth/click-through-for-cheating):

- Hide / show overlay
- Move window
- Resize
- Trigger answer
- Trigger screenshot analysis
- Clear

Show shortcut tooltips on button hover, 10px mono.

### 6.8 Optional “focus layout”

A wider layout for practice: transcript left, answer right, meeting remains in the user’s other window. Do not fake a meeting in the middle unless you are building a mock-interview player.

---

## 7. Component inventory (build these once)

Reuse across marketing + app.

1. **BirdMark** — 32px (nav) / 20px (overlay)
2. **PillButton** — variants: `green`, `black`, `white`, `outline`, `danger`, `ghost`
3. **SegmentedControl** — 2–3 options
4. **NavBar** — marketing pill
5. **ProofStrip** — avatars + rating + badges
6. **FeatureSplit** — text + framed visual
7. **QuietCard** — 20px radius, hairline or none
8. **TestimonialCard**
9. **PricingCard** — popular badge
10. **FAQItem** — accordion
11. **AuthButtonRow**
12. **SessionForm**
13. **SessionRow**
14. **TranscriptPane**
15. **AnswerPane** — markdown + copy
16. **StatusBar**
17. **OverlayHeader**
18. **CreditsChip**
19. **KbdHint**
20. **EmptyState**

---

## 8. Motion and states

| Event | Motion |
|---|---|
| Button hover | 150ms background darken, no scale > 1.02 |
| Nav sticky | already floating, no hide-on-scroll |
| Listening | 8px green/red dot, opacity pulse 1.5s |
| Token stream | answers appear incrementally, no typewriter cursor needed |
| Spinner | 0.7s linear rotate |
| Overlay open | 120ms fade + 4px translateY |
| Toast | top-center, 3s, dark on light or inverse |
| Form error | 1px danger border, 12px helper text |
| Disabled | 50% opacity, no pointer |

Do not use bounce, spring overshoot, or page-wide fade-ins.

---

## 9. Copy tone

- Short. Direct. Benefit-first.
- Headlines name the job: “Your Real-Time AI Call Assistant.”
- Subheads explain the moment: get the answer while you are still talking.
- Buttons are verbs: Try for Free, Start session, Answer, Analyze screen, Clear.
- Avoid hype adjectives stacked together. Avoid “revolutionary / next-gen / unlock.”
- Reviews on the site are plain and specific, not marketing-speak.

For the clone, write original copy in this voice. Do not paste long copyrighted page text.

---

## 10. Agent implementation plan

Build in this order so the UI stays coherent:

### Phase A — Design system
1. CSS variables from §3.
2. Global reset, fonts (Inter Tight + Inter + JetBrains Mono).
3. PillButton, SegmentedControl, inputs, cards.

### Phase B — Marketing
4. Nav + hero + proof strip (must match the screenshot composition).
5. Remaining landing sections in the listed order.
6. Auth, pricing, FAQ pages.

### Phase C — App
7. Dashboard shell + session list.
8. Create-session form.
9. Live session (transcript + answer + toolbar).

### Phase D — Overlay
10. Dark-glass overlay as a separate route or desktop webview.
11. Interview vs Coding modes.
12. Status, streaming answer, screenshot action, keyboard hints.

### Phase E — Polish
13. Mobile landing + `/mobile` session layout.
14. Empty / loading / error / streaming states.
15. Light/dark only where the official product has it (marketing stays light; overlay stays dark; dashboard may include a Light toggle).

---

## 11. Layout numbers (do not improvise)

**Marketing**

- Content width: 1080–1120px
- Hero H1: 64px desktop / 36–40px mobile
- CTA gap: 12px
- Section padding: 96px desktop / 64px mobile
- Card gap: 20–24px
- Nav inner padding: 8px + 16px

**Dashboard**

- Main max-width: 960–1040px
- Form label → field gap: 6px
- Field stack gap: 16–20px

**Overlay**

- Width: 380px default
- Header height: ~44px
- Section max transcript height: ~120px
- Section max answer height: ~220px
- Control gap: 6px
- Side padding: 14px

---

## 12. Visual QA checklist

The clone is correct when all of these are true:

- [ ] Marketing hero is a single composition on white with mint/lime washes, not a dashboard.
- [ ] “Real-Time” (or your equivalent keyword) is the only green phrase in the H1.
- [ ] Nav is a floating white pill with bird mark, gray links, outline Sign in, black Try for Free.
- [ ] Primary marketing CTA is a green pill; secondary is a white pill.
- [ ] Social proof sits *above* the headline, not below the fold.
- [ ] No purple, no neon mesh, no 5-font chaos.
- [ ] Overlay is dark, blurred, compact, header-draggable.
- [ ] Overlay has Interview / Coding toggle, status bar, one dominant action button.
- [ ] Transcript is mono and secondary; answer is the visual focus.
- [ ] Coding answers look like an editor (highlighted code + copy).
- [ ] Live web session uses Answer / Screenshot / Chat / Clear.
- [ ] Create-session screen collects type, company, JD, context, model, language.
- [ ] Mobile is a single column with a sticky action bar.
- [ ] All interactive states (hover, focus, listening, thinking, error) are defined.

---

## 13. What not to copy

- Official parrot illustration and “Parakeet AI” wordmark as your production brand.
- False stealth claims (hidden process name, hidden from screen share, etc.).
- Long verbatim marketing paragraphs, review text, or video scripts.
- Pixel-identical logo badge.

Clone the **system**: light green-accent marketing, pill chrome, proof-first hero, session form, four-button live toolbar, and a dark glass overlay with interview/coding modes.

---

## 14. Suggested file map for the clone

```
src/
  styles/tokens.css
  styles/global.css
  components/ui/   PillButton, SegmentedControl, Card, FAQItem, Kbd
  components/brand/BirdMark, NavBar, ProofStrip, Footer
  components/session/SessionForm, TranscriptPane, AnswerPane, SessionToolbar
  components/overlay/OverlayRoot, OverlayHeader, StatusBar
  pages/marketing/Home, Pricing, Reviews, Privacy
  pages/auth/SignIn
  pages/app/Dashboard, SessionLive
  pages/overlay/OverlayApp
```

Stack that matches the original product’s era: **Next.js + React + CSS** (or Tailwind mapped to the tokens above). Desktop shell may be Tauri or Electron wrapping `OverlayApp`. Keep CSS explicit; do not let a default shadcn/Tailwind look leak through.

---

## 15. One-screen reference (for the agent)

**If you can only get one screen right, get this:**

A white page. Floating pill nav with a small green bird. Three avatars and a 4.86 star line. A huge black headline with one green phrase. Gray one-line subhead. A green pill button beside a white pill button. Soft mint and lime light at the bottom of the viewport. Then, in the product, a small dark frosted panel: bird name, Interview/Coding switch, live status, transcript, streamed answer, one fat action button.

That is Parakeet AI’s frontend.
