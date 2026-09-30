"""
Floating Overlay UI for Project New Horizon — Parakeet AI clone dark glass.
Spec: frameless (overrideredirect), topmost, alpha 0.90-0.93 dark glass,
palette #121318 base / #1A1C23 cards / #9CA3AF muted / #10B981 accent,
rounded corners 10-12, draggable header with close ✕, status + card layout.
"""

import sys
import pathlib
import math
import queue
import time
import threading
import tkinter as tk
from tkinter import font as tkfont
try:
    import customtkinter as ctk
except ModuleNotFoundError:
    for _p in [
        pathlib.Path(sys.base_prefix) / "Lib" / "site-packages",
        pathlib.Path(r"C:\Users\nj322ws\AppData\Local\Programs\Python\Python311\Lib\site-packages"),
    ]:
        if _p.is_dir():
            sys.path.insert(0, str(_p))
    import customtkinter as ctk
import numpy as np

from app.audio import AudioRecorder, UtteranceBuffer
from app.vad import SilenceDetector
from app.config import load_whisper_keys, load_answer_keys
from app.transcription import GroqWhisperClient, AllKeysExhaustedError
from app.question_detector import QuestionDetector
from app.context_cache import ContextCache
from app.question_queue import QuestionQueue
from app.answer_engine import GroqAnswerEngine, AllAnswerKeysExhaustedError

HALLUCINATION_PHRASES = {
    "thank you.", "thanks for watching.", "thanks for watching!",
    "subscribe to the channel.", "please subscribe.", "like and subscribe.",
    "thank you for watching.", "see you next time.", "bye.", "bye-bye.",
    "you", "the end.", "thanks.", "thank you very much.",
    "subtitles by the amara.org community", "...", "i'm sorry.",
    "goodbye.", "so,", "hmm.", "huh.", "oh.", "ah.",
    "MBC 뉴스 김경수입니다", "字幕由amara.org社区提供",
    "ご視聴ありがとうございました", "sous-titres réalisés para la communauté d'amara.org",
}

MIN_UTTERANCE_DURATION_SEC = 0.5
MIN_UTTERANCE_RMS = 0.008

# ── Parakeet overlay palette (spec literal) ────────────────────────────────
BASE_BG = "#121318"
CARD_BG = "#1A1C23"
MUTED = "#9CA3AF"
ACCENT = "#10B981"
BORDER = "#232533"
TEXT = "#E8EAF0"

STATE_COLORS = {
    "Idle":         {"accent": MUTED,   "glow": BORDER, "border": BORDER,   "text": MUTED,   "label": "● Idle"},
    "Listening":    {"accent": ACCENT,  "glow": "#065f46","border": "#0f3d2e","text": ACCENT,  "label": "● Listening..."},
    "Speaking":     {"accent": ACCENT,  "glow": "#065f46","border": "#0f3d2e","text": ACCENT,  "label": "● Speaking..."},
    "Transcribing": {"accent": ACCENT,  "glow": "#065f46","border": "#0f3d2e","text": ACCENT,  "label": "● Transcribing..."},
    "Thinking":     {"accent": ACCENT,  "glow": "#065f46","border": "#0f3d2e","text": ACCENT,  "label": "● Thinking..."},
    "Streaming":    {"accent": ACCENT,  "glow": "#065f46","border": "#0f3d2e","text": ACCENT,  "label": "● Streaming..."},
    "Complete":     {"accent": ACCENT,  "glow": "#065f46","border": "#0f3d2e","text": ACCENT,  "label": "● Complete"},
    "Error":        {"accent": "#ef4444","glow": "#7f1d1d","border": "#3f1a1a","text": "#fca5a5","label": "● Error"},
}

FONT_FAMILY = "Segoe UI"


class HorizonApp:
    """Frameless dark-glass overlay: draggable header, status + card layout."""

    def __init__(self, root: ctk.CTk):
        self.root = root
        self.state = "Idle"
        self.answer_mode = "Short"
        self.reduced_motion = False
        self.audio_rms = 0.0
        self.speech_prob = 0.0
        self.error_message = ""
        self.anim_frame = 0
        self.utterance_count = 0
        self._transcribing_timer_id = None
        self.last_transcript = ""
        self.current_question = ""
        self.is_streaming_answer = False
        self.answer_pending = ""
        self.answer_full_text = ""
        self.qa_history_widgets = []
        self._smoothed_rms = 0.0
        self._target_border_color = BORDER
        self._current_border_rgb = self._hex_to_rgb(BORDER)
        self._session_start_time = None

        self.BASE_WIDTH = 400
        self.BASE_HEIGHT = 380
        self.MAX_HEIGHT = 620
        self.current_height = self.BASE_HEIGHT
        self._target_height = self.BASE_HEIGHT

        self.event_queue = queue.Queue()

        self.recorder = AudioRecorder()
        self.silence_detector = SilenceDetector(silence_duration_sec=1.0, speech_threshold=0.5)
        self.utterance_buffer = UtteranceBuffer(pre_speech_chunks=10)

        whisper_keys = load_whisper_keys()
        self.transcriber = GroqWhisperClient(keys=whisper_keys) if whisper_keys else None

        self.question_detector = QuestionDetector()
        self.context_cache = ContextCache(capacity=5)
        self.question_queue = QuestionQueue()
        answer_keys = load_answer_keys()
        self.answer_engine = GroqAnswerEngine(keys=answer_keys) if answer_keys else None

        self._setup_window()
        self._build_ui()

        self.root.after(50, self._process_events)
        self.root.after(33, self._animate)
        self.root.after(50, self._smooth_resize_tick)

    # ── Window ───────────────────────────────────────────────────────────
    def _setup_window(self):
        self.root.title("Project New Horizon")
        screen_w = self.root.winfo_screenwidth()
        x_pos = max(0, (screen_w - self.BASE_WIDTH) // 2)
        y_pos = 18
        self.root.geometry(f"{self.BASE_WIDTH}x{self.BASE_HEIGHT}+{x_pos}+{y_pos}")
        self.root.minsize(self.BASE_WIDTH, self.BASE_HEIGHT)
        self.root.resizable(False, False)
        self.root.wm_attributes("-topmost", True)
        self.root.overrideredirect(True)
        try:
            self.root.wm_attributes("-alpha", 0.92)
        except Exception:
            pass
        self.bg_color = BASE_BG
        self.root.configure(fg_color=self.bg_color)
        self._drag_data = {"x": 0, "y": 0}
        self.root.bind("<Escape>", lambda e: self._on_close())
        self.root.bind("<space>", lambda e: self.toggle_recording())
        self.root.bind("<KeyPress-m>", lambda e: self.toggle_reduced_motion())

    def _start_drag(self, event):
        self._drag_data["x"] = event.x
        self._drag_data["y"] = event.y

    def _do_drag(self, event):
        dx = event.x - self._drag_data["x"]
        dy = event.y - self._drag_data["y"]
        x = self.root.winfo_x() + dx
        y = self.root.winfo_y() + dy
        self.root.geometry(f"+{x}+{y}")

    def _bind_drag(self, widget):
        widget.bind("<Button-1>", self._start_drag)
        widget.bind("<B1-Motion>", self._do_drag)

    # ── Resize ───────────────────────────────────────────────────────────
    def _resize_window(self, new_height: int):
        self._target_height = max(self.BASE_HEIGHT, min(new_height, self.MAX_HEIGHT))

    def _smooth_resize_tick(self):
        if self.current_height != self._target_height:
            diff = self._target_height - self.current_height
            step = int(diff * 0.3) if abs(diff) > 3 else diff
            if step == 0:
                step = 1 if diff > 0 else -1
            self.current_height += step
            x = self.root.winfo_x()
            y = self.root.winfo_y()
            self.root.geometry(f"{self.BASE_WIDTH}x{self.current_height}+{x}+{y}")
        self.root.after(25, self._smooth_resize_tick)

    def _reset_window_height(self):
        self._resize_window(self.BASE_HEIGHT)

    # ── UI ───────────────────────────────────────────────────────────────
    def _build_ui(self):
        # Outer frame — rounded glass shell (#121318 base, corner_radius=12)
        self.outer_frame = ctk.CTkFrame(
            self.root,
            corner_radius=12,
            fg_color="#121318",
            border_width=1,
            border_color=BORDER
        )
        self.outer_frame.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)

        self.inner_frame = ctk.CTkFrame(
            self.outer_frame,
            corner_radius=12,
            fg_color="#121318",
            border_width=0
        )
        self.inner_frame.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)

        # ── Custom Draggable Header ─────────────────────────────────────
        self.header_frame = ctk.CTkFrame(self.inner_frame, fg_color="transparent", height=36, corner_radius=10)
        self.header_frame.pack(fill=tk.X, side=tk.TOP, padx=10, pady=(6, 0))
        self.header_frame.pack_propagate(False)

        self.logo_title_box = ctk.CTkFrame(self.header_frame, fg_color="transparent")
        self.logo_title_box.pack(side=tk.LEFT)

        self.logo_canvas = tk.Canvas(
            self.logo_title_box, width=22, height=22,
            bg="#121318", highlightthickness=0, bd=0
        )
        self.logo_canvas.pack(side=tk.LEFT, padx=(0, 7), pady=7)

        self.title_label = ctk.CTkLabel(
            self.logo_title_box,
            text="NEW HORIZON",
            font=ctk.CTkFont(family=FONT_FAMILY, size=11, weight="bold"),
            text_color=TEXT
        )
        self.title_label.pack(side=tk.LEFT)

        self.version_label = ctk.CTkLabel(
            self.logo_title_box,
            text="v1.0",
            font=ctk.CTkFont(family=FONT_FAMILY, size=8),
            text_color=MUTED,
            width=28
        )
        self.version_label.pack(side=tk.LEFT, padx=(4, 0))

        # Close button (✕) — spec required
        self.close_btn = ctk.CTkButton(
            self.header_frame,
            text="✕", width=26, height=26,
            corner_radius=8,
            fg_color="transparent",
            hover_color=CARD_BG,
            text_color=MUTED,
            font=ctk.CTkFont(size=11, weight="bold"),
            command=self._on_close
        )
        self.close_btn.pack(side=tk.RIGHT, padx=(2, 0))

        # Reduced motion toggle (kept, recolored)
        self.motion_btn = ctk.CTkButton(
            self.header_frame,
            text="⚡", width=26, height=26,
            corner_radius=8,
            fg_color=CARD_BG,
            hover_color=BORDER,
            text_color=MUTED,
            font=ctk.CTkFont(size=10),
            command=self.toggle_reduced_motion
        )
        self.motion_btn.pack(side=tk.RIGHT, padx=1)

        # Pill toggle Short/Free
        self.pill_frame = ctk.CTkFrame(
            self.header_frame, fg_color=CARD_BG,
            corner_radius=10, height=26
        )
        self.pill_frame.pack(side=tk.RIGHT, padx=(0, 4))
        self.pill_frame.pack_propagate(False)

        self.pill_short_btn = ctk.CTkButton(
            self.pill_frame, text="Short", width=48, height=22,
            corner_radius=8,
            fg_color=ACCENT,
            hover_color="#0ea371",
            text_color="#ffffff",
            font=ctk.CTkFont(family=FONT_FAMILY, size=10, weight="bold"),
            command=lambda: self.set_answer_mode("Short")
        )
        self.pill_short_btn.pack(side=tk.LEFT, padx=2, pady=2)

        self.pill_free_btn = ctk.CTkButton(
            self.pill_frame, text="Free", width=48, height=22,
            corner_radius=8,
            fg_color="transparent",
            hover_color=BORDER,
            text_color=MUTED,
            font=ctk.CTkFont(family=FONT_FAMILY, size=10),
            command=lambda: self.set_answer_mode("Free")
        )
        self.pill_free_btn.pack(side=tk.LEFT, padx=2, pady=2)

        # Make header draggable (click-and-drag window movement)
        for w in (self.header_frame, self.logo_title_box, self.logo_canvas, self.title_label, self.version_label):
            self._bind_drag(w)

        # ── Top Status Indicator (spec: ● Listening... ) ─────────────────
        self.status_card = ctk.CTkFrame(
            self.inner_frame,
            corner_radius=10,
            fg_color="#1A1C23",
            border_width=1,
            border_color=BORDER,
            height=30
        )
        self.status_card.pack(fill=tk.X, padx=10, pady=(8, 0))
        self.status_card.pack_propagate(False)

        self.status_dot = tk.Canvas(
            self.status_card, width=10, height=10,
            bg="#1A1C23", highlightthickness=0, bd=0
        )
        self.status_dot.pack(side=tk.LEFT, padx=(10, 6), pady=10)

        self.status_label = ctk.CTkLabel(
            self.status_card,
            text="● Idle",
            font=ctk.CTkFont(family=FONT_FAMILY, size=11),
            text_color="#9CA3AF",
            anchor="w"
        )
        self.status_label.pack(side=tk.LEFT, fill=tk.X, expand=True)

        # ── Control + waveform row ───────────────────────────────────────
        self.main_row = ctk.CTkFrame(self.inner_frame, fg_color="transparent", height=40)
        self.main_row.pack(fill=tk.X, padx=10, pady=(6, 4))
        self.main_row.pack_propagate(False)

        self.action_btn = ctk.CTkButton(
            self.main_row,
            text="● Start", width=88, height=32,
            corner_radius=10,
            fg_color="#1A1C23",
            hover_color=BORDER,
            text_color="#10B981",
            font=ctk.CTkFont(family=FONT_FAMILY, size=11, weight="bold"),
            border_width=1,
            border_color=BORDER,
            command=self.toggle_recording
        )
        self.action_btn.pack(side=tk.LEFT, padx=(0, 8))

        self.viz_canvas = tk.Canvas(
            self.main_row, height=32,
            bg="#121318", highlightthickness=0, bd=0
        )
        self.viz_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # ── Main Card area for live response (#1A1C23 card, corner_radius=12) ─
        self.qa_panel = ctk.CTkFrame(
            self.inner_frame,
            corner_radius=12,
            fg_color="#1A1C23",
            border_width=1,
            border_color=BORDER
        )
        self.qa_panel.pack(fill=tk.BOTH, expand=True, padx=10, pady=(2, 6))

        self.question_row = ctk.CTkFrame(self.qa_panel, fg_color="transparent")
        self.question_row.pack(fill=tk.X, padx=12, pady=(10, 0))

        self.mic_icon = ctk.CTkLabel(
            self.question_row,
            text="🎤",
            font=ctk.CTkFont(size=13),
            width=22,
            text_color="#9CA3AF"
        )
        self.mic_icon.pack(side=tk.LEFT, padx=(0, 6))

        self.question_label = ctk.CTkLabel(
            self.question_row,
            text="Ready for questions…",
            font=ctk.CTkFont(family=FONT_FAMILY, size=11, weight="bold"),
            text_color="#9CA3AF",
            anchor="w",
            justify="left",
            wraplength=300
        )
        self.question_label.pack(side=tk.LEFT, fill=tk.X, expand=True)

        # thin separator line
        self.sep_canvas = tk.Canvas(
            self.qa_panel, height=1, bg="#1A1C23",
            highlightthickness=0, bd=0
        )
        self.sep_canvas.pack(fill=tk.X, padx=14, pady=(8, 4))

        self.answer_textbox = ctk.CTkTextbox(
            self.qa_panel,
            corner_radius=10,
            fg_color="#121318",
            text_color="#E8EAF0",
            font=ctk.CTkFont(family=FONT_FAMILY, size=11),
            border_width=1,
            border_color=BORDER,
            wrap="word",
            height=150,
            activate_scrollbars=True,
            scrollbar_button_color=BORDER,
            scrollbar_button_hover_color="#2e3142"
        )
        self.answer_textbox.pack(fill=tk.BOTH, expand=True, padx=8, pady=(2, 8))
        self.answer_textbox.insert("1.0", "Press Start or Space to begin listening.")
        self.answer_textbox.configure(state="disabled")

        # ── History (hidden until needed) ─────────────────────────────────
        self.history_frame = ctk.CTkScrollableFrame(
            self.inner_frame,
            corner_radius=10,
            fg_color=BASE_BG,
            border_width=0,
            height=0,
            scrollbar_button_color=BORDER,
            scrollbar_button_hover_color="#2e3142"
        )
        self.history_visible = False

        self.shortcut_label = ctk.CTkLabel(
            self.inner_frame,
            text="Drag header to move  ·  Space: mic  ·  Esc: quit",
            font=ctk.CTkFont(family=FONT_FAMILY, size=8),
            text_color="#9CA3AF",
            anchor="e"
        )
        self.shortcut_label.pack(fill=tk.X, padx=12, pady=(0, 3), side=tk.BOTTOM)

        self.answer_font = tkfont.Font(family=FONT_FAMILY, size=11)

    # ── Mode / Recording ───────────────────────────────────────────────
    def _minimize(self):
        self.root.overrideredirect(False)
        self.root.iconify()
        def _restore(event=None):
            self.root.overrideredirect(True)
            self.root.wm_attributes("-topmost", True)
            self.root.unbind("<Map>")
        self.root.bind("<Map>", _restore)

    def toggle_reduced_motion(self):
        self.reduced_motion = not self.reduced_motion
        if self.reduced_motion:
            self.motion_btn.configure(text="⏸", fg_color=BORDER)
        else:
            self.motion_btn.configure(text="⚡", fg_color=CARD_BG)

    def set_answer_mode(self, mode: str):
        self.answer_mode = mode
        if mode == "Short":
            self.pill_short_btn.configure(fg_color=ACCENT, text_color="#ffffff",
                font=ctk.CTkFont(family=FONT_FAMILY, size=10, weight="bold"))
            self.pill_free_btn.configure(fg_color="transparent", text_color=MUTED,
                font=ctk.CTkFont(family=FONT_FAMILY, size=10))
        else:
            self.pill_short_btn.configure(fg_color="transparent", text_color=MUTED,
                font=ctk.CTkFont(family=FONT_FAMILY, size=10))
            self.pill_free_btn.configure(fg_color=ACCENT, text_color="#ffffff",
                font=ctk.CTkFont(family=FONT_FAMILY, size=10, weight="bold"))

    def toggle_recording(self):
        if self.state in ("Idle", "Error"):
            self.start_listening()
        else:
            self.stop_listening()

    def _set_action_button(self, listening: bool):
        if listening:
            self.action_btn.configure(text="■ Stop", fg_color="#2a1a1a", hover_color="#3a1f1f",
                text_color="#f87171", border_color="#4a2525")
        else:
            self.action_btn.configure(text="● Start", fg_color=CARD_BG, hover_color=BORDER,
                text_color=ACCENT, border_color=BORDER)

    # ── Audio Pipeline ─────────────────────────────────────────────────
    def start_listening(self):
        self.error_message = ""
        self._session_start_time = time.time()
        is_mic_ok, mic_msg = self.recorder.check_microphone_status()
        if not is_mic_ok:
            self.state = "Error"
            self.error_message = mic_msg
            self.event_queue.put(("AUDIO_ERROR", mic_msg))
            return
        self.silence_detector.reset()
        self.utterance_buffer.reset()
        self.context_cache.clear()
        self.question_queue.clear()
        self._clear_history_panel()
        self.state = "Listening"
        self._set_action_button(listening=True)
        self.question_label.configure(text="Listening for questions…", text_color=MUTED)
        self.mic_icon.configure(text="🎙️")
        self._set_answer_text("Listening…", color=MUTED)
        self._reset_window_height()

        def audio_chunk_callback(chunk):
            res = self.silence_detector.process_chunk(chunk)
            self.utterance_buffer.feed(chunk, res["is_speech"])
            self.event_queue.put(("AUDIO_METRICS", res))

        def audio_error_callback(msg):
            self.event_queue.put(("AUDIO_ERROR", msg))

        self.recorder.start_recording(on_chunk_callback=audio_chunk_callback, on_error_callback=audio_error_callback)

    def stop_listening(self):
        if self._transcribing_timer_id is not None:
            self.root.after_cancel(self._transcribing_timer_id)
            self._transcribing_timer_id = None
        self.recorder.stop_recording()
        self.silence_detector.reset()
        self.utterance_buffer.reset()
        self.state = "Idle"
        self.audio_rms = 0.0
        self.speech_prob = 0.0
        self._smoothed_rms = 0.0
        self._session_start_time = None
        self._set_action_button(listening=False)
        self.mic_icon.configure(text="🎤")

    # ── Answer helpers ─────────────────────────────────────────────────
    def _set_answer_text(self, text: str, color: str = TEXT):
        self.answer_textbox.configure(state="normal", text_color=color)
        self.answer_textbox.delete("1.0", "end")
        self.answer_textbox.insert("1.0", text)
        self.answer_textbox.configure(state="disabled")

    def _append_answer_text(self, text: str):
        self.answer_textbox.configure(state="normal")
        self.answer_textbox.insert("end", text)
        self.answer_textbox.see("end")
        self.answer_textbox.configure(state="disabled")

    # ── History ────────────────────────────────────────────────────────
    def _show_history_panel(self):
        if not self.history_visible:
            self.history_frame.configure(height=80)
            self.history_frame.pack(fill=tk.X, padx=10, pady=(0, 2), before=self.shortcut_label)
            self.history_visible = True

    def _clear_history_panel(self):
        for w in self.qa_history_widgets:
            w.destroy()
        self.qa_history_widgets.clear()
        if self.history_visible:
            self.history_frame.pack_forget()
            self.history_visible = False

    def _add_history_card(self, question: str, answer: str):
        self._show_history_panel()
        card = ctk.CTkFrame(self.history_frame, corner_radius=10, fg_color=CARD_BG, border_width=1, border_color=BORDER, height=52)
        card.pack(fill=tk.X, padx=2, pady=2)
        card.pack_propagate(False)
        stripe = ctk.CTkFrame(card, fg_color=ACCENT, width=3, corner_radius=2)
        stripe.pack(side=tk.LEFT, fill=tk.Y, padx=(4, 8), pady=4)
        text_container = ctk.CTkFrame(card, fg_color="transparent")
        text_container.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, pady=2)
        q_label = ctk.CTkLabel(text_container, text=question, font=ctk.CTkFont(family=FONT_FAMILY, size=10, weight="bold"), text_color=TEXT, anchor="w", wraplength=300)
        q_label.pack(fill=tk.X, anchor="w")
        display_answer = answer[:140] + "…" if len(answer) > 140 else answer
        a_label = ctk.CTkLabel(text_container, text=display_answer, font=ctk.CTkFont(family=FONT_FAMILY, size=9), text_color=MUTED, anchor="w", justify="left", wraplength=300)
        a_label.pack(fill=tk.X, anchor="w", pady=(1, 0))
        self.qa_history_widgets.append(card)
        while len(self.qa_history_widgets) > 5:
            old = self.qa_history_widgets.pop(0)
            old.destroy()

    def _update_dynamic_height(self):
        try:
            text = self.answer_textbox.get("1.0", "end-1c")
            line_count = text.count("\n") + 1
            answer_line_height = 18
            content_lines = max(8, line_count)
            overhead = 160
            history_h = 80 if self.history_visible else 0
            needed = overhead + (content_lines * answer_line_height) + history_h
            self._resize_window(needed)
        except Exception:
            pass

    # ── Event Processing ───────────────────────────────────────────────
    def _process_events(self):
        try:
            while not self.event_queue.empty():
                evt_type, data = self.event_queue.get_nowait()
                if evt_type == "AUDIO_METRICS":
                    if self.state == "Listening":
                        self.audio_rms = data["rms"]
                        self.speech_prob = data["speech_prob"]
                        if data["utterance_complete"]:
                            self.utterance_count += 1
                            utterance_audio = self.utterance_buffer.get_utterance_audio()
                            self._last_utterance_audio = utterance_audio
                            self.state = "Transcribing"
                            self._start_transcription(utterance_audio)
                elif evt_type == "TRANSCRIPTION_DONE":
                    transcript = str(data).strip()
                    self.last_transcript = transcript
                    if not transcript or transcript in (".", ",", "?", "!"):
                        self._return_to_listening()
                    else:
                        self.question_label.configure(text=f"\u201c{transcript}\u201d", text_color=TEXT)
                        is_q = self.question_detector.is_question(transcript)
                        if is_q:
                            if self.is_streaming_answer:
                                self.question_queue.enqueue(transcript)
                            else:
                                self._start_answer_stream(transcript)
                        else:
                            self.question_label.configure(text=f"\u201c{transcript}\u201d", text_color=MUTED)
                            self._set_answer_text("Statement heard — ask a question to get an answer.", color=MUTED)
                            self._return_to_listening()
                elif evt_type == "TRANSCRIPTION_ERROR":
                    self.state = "Error"
                    self.error_message = str(data)
                    self.question_label.configure(text="Transcription error", text_color="#fca5a5")
                    self._set_answer_text(str(data), color="#f87171")
                    self._transcribing_timer_id = self.root.after(2500, self._return_to_listening)
                elif evt_type == "ANSWER_FIRST_TOKEN":
                    self.is_streaming_answer = True
                    self.state = "Streaming"
                    self.answer_full_text = ""
                    self._set_answer_text("", color=TEXT)
                elif evt_type == "ANSWER_CHUNK":
                    chunk_text = str(data)
                    self.answer_full_text += chunk_text
                    self._append_answer_text(chunk_text)
                    self._update_dynamic_height()
                elif evt_type == "ANSWER_DONE":
                    full_answer = str(data)
                    self.is_streaming_answer = False
                    if self.current_question:
                        self.context_cache.add(self.current_question, full_answer)
                        self._add_history_card(self.current_question, full_answer)
                    self.answer_textbox.configure(text_color=TEXT)
                    self.state = "Complete"
                    self._transcribing_timer_id = self.root.after(500 if not self.reduced_motion else 10, self._finish_complete_and_listen)
                elif evt_type == "ANSWER_ERROR":
                    self.is_streaming_answer = False
                    err_msg = str(data)
                    self.state = "Error"
                    self.error_message = err_msg
                    self._set_answer_text(f"Answer error: {err_msg}", color="#f87171")
                    self._transcribing_timer_id = self.root.after(3000, self._return_to_listening)
                elif evt_type == "AUDIO_ERROR":
                    self.recorder.stop_recording()
                    self.state = "Error"
                    self.error_message = str(data)
                    self._set_action_button(listening=False)
                    self._set_answer_text(str(data), color="#f87171")
        except Exception:
            pass
        finally:
            self.root.after(40, self._process_events)

    def _start_transcription(self, audio):
        if self.transcriber is None:
            self.event_queue.put(("TRANSCRIPTION_ERROR", "No Whisper API keys configured in .env."))
            return
        if audio is None or len(audio) == 0:
            self.event_queue.put(("TRANSCRIPTION_ERROR", "No audio captured."))
            return
        duration_sec = len(audio) / 16000.0
        if duration_sec < MIN_UTTERANCE_DURATION_SEC:
            self._return_to_listening()
            return
        rms = float(np.sqrt(np.mean(audio ** 2)))
        if rms < MIN_UTTERANCE_RMS:
            self._return_to_listening()
            return
        def _transcribe_worker():
            try:
                text = self.transcriber.transcribe(audio, sample_rate=16000).strip()
                if text.lower() in HALLUCINATION_PHRASES:
                    self.event_queue.put(("TRANSCRIPTION_DONE", ""))
                    return
                words = text.split()
                if len(words) >= 3 and len(set(words)) == 1:
                    self.event_queue.put(("TRANSCRIPTION_DONE", ""))
                    return
                self.event_queue.put(("TRANSCRIPTION_DONE", text))
            except AllKeysExhaustedError as e:
                self.event_queue.put(("TRANSCRIPTION_ERROR", str(e)))
            except Exception as e:
                self.event_queue.put(("TRANSCRIPTION_ERROR", str(e)))
        threading.Thread(target=_transcribe_worker, daemon=True).start()

    def _start_answer_stream(self, question: str):
        if self.answer_engine is None:
            self.event_queue.put(("ANSWER_ERROR", "No Answer API keys configured in .env."))
            return
        self.current_question = question
        self.state = "Thinking"
        self._reset_window_height()
        self._set_answer_text("Reasoning…", color=ACCENT)
        context_msgs = self.context_cache.get_context_messages()
        mode = self.answer_mode
        def _answer_worker():
            full_response = []
            first_token_sent = False
            try:
                for chunk in self.answer_engine.stream_answer(question=question, context_messages=context_msgs, mode=mode):
                    if not first_token_sent:
                        self.event_queue.put(("ANSWER_FIRST_TOKEN", None))
                        first_token_sent = True
                    full_response.append(chunk)
                    self.event_queue.put(("ANSWER_CHUNK", chunk))
                self.event_queue.put(("ANSWER_DONE", "".join(full_response)))
            except AllAnswerKeysExhaustedError as e:
                self.event_queue.put(("ANSWER_ERROR", str(e)))
            except Exception as e:
                self.event_queue.put(("ANSWER_ERROR", str(e)))
        threading.Thread(target=_answer_worker, daemon=True).start()

    def _finish_complete_and_listen(self):
        self._transcribing_timer_id = None
        self._return_to_listening()
        next_q = self.question_queue.dequeue()
        if next_q:
            self.root.after(100, lambda q=next_q: self._start_answer_stream(q))

    def _return_to_listening(self):
        self._transcribing_timer_id = None
        if self.state in ("Transcribing", "Thinking", "Streaming", "Complete", "Error"):
            self.silence_detector.reset()
            self.utterance_buffer.reset()
            self.audio_rms = 0.0
            self.speech_prob = 0.0
            self.state = "Listening"

    # ── Animation ──────────────────────────────────────────────────────
    def _animate(self):
        self.anim_frame += 1
        target_rms = self.audio_rms
        self._smoothed_rms += (target_rms - self._smoothed_rms) * 0.18
        self._draw_logo_orb()
        self._draw_status_dot()
        self._draw_separator()
        self._render_visualizer()
        self._update_border_glow()
        self.root.after(33, self._animate)

    def _draw_separator(self):
        # subtle line tinted with accent at center, muted edges
        try:
            c = self.sep_canvas
            c.delete("all")
            cw = c.winfo_width()
            if cw <= 1:
                cw = 300
            r, g, b = self._hex_to_rgb(ACCENT)
            segments = 20
            for i in range(segments):
                x0 = int(cw * i / segments)
                x1 = int(cw * (i + 1) / segments)
                t = abs(i - segments // 2) / (segments // 2)
                intensity = max(0.06, 0.35 * (1.0 - t * t))
                color = f"#{int(r*intensity):02x}{int(g*intensity):02x}{int(b*intensity):02x}"
                c.create_line(x0, 1, x1, 1, fill=color, width=1)
        except Exception:
            pass

    def _update_border_glow(self):
        sc = self._get_state_colors()
        target = self._hex_to_rgb(sc["border"])
        cr, cg, cb = self._current_border_rgb
        tr, tg, tb = target
        lerp = 0.08
        nr = int(cr + (tr - cr) * lerp)
        ng = int(cg + (tg - cg) * lerp)
        nb = int(cb + (tb - cb) * lerp)
        self._current_border_rgb = (nr, ng, nb)
        color = f"#{nr:02x}{ng:02x}{nb:02x}"
        try:
            self.outer_frame.configure(border_color=color)
            self.status_card.configure(border_color=color if self.state != "Idle" else BORDER)
            self.qa_panel.configure(border_color=color if self.state != "Idle" else BORDER)
        except Exception:
            pass

    def _draw_logo_orb(self):
        try:
            c = self.logo_canvas
            c.delete("all")
            cx, cy = 11, 11
            sc = self._get_state_colors()
            accent = sc["accent"]
            glow = sc["glow"]
            pulse = (math.sin(self.anim_frame * 0.07) + 1) / 2
            pulse2 = (math.sin(self.anim_frame * 0.12 + 1.5) + 1) / 2
            if self.reduced_motion:
                pulse = 0.5
                pulse2 = 0.5
            r3 = 10 + int(pulse * 1)
            ar, ag, ab = self._hex_to_rgb(glow)
            dim = f"#{ar//4:02x}{ag//4:02x}{ab//4:02x}"
            c.create_oval(cx-r3, cy-r3, cx+r3, cy+r3, outline=dim, width=1)
            r2 = 7 + int(pulse2 * 1)
            c.create_oval(cx-r2, cy-r2, cx+r2, cy+r2, outline=accent, width=1.2)
            r1 = 5
            c.create_oval(cx-r1, cy-r1, cx+r1, cy+r1, fill=accent, outline="")
            c.create_oval(cx-2, cy-3, cx+1, cy-1, fill="#ffffff", outline="")
        except Exception:
            pass

    def _draw_status_dot(self):
        try:
            c = self.status_dot
            c.delete("all")
            sc = self._get_state_colors()
            accent = sc["accent"]
            pulse = (math.sin(self.anim_frame * 0.1) + 1) / 2 if not self.reduced_motion else 0.8
            r = 3 + int(pulse * 1)
            c.create_oval(5-r, 5-r, 5+r, 5+r, fill=accent, outline="")
            self.status_label.configure(text=sc["label"], text_color=sc["text"])
        except Exception:
            pass

    def _render_visualizer(self):
        try:
            c = self.viz_canvas
            c.delete("all")
            cw = c.winfo_width()
            ch = c.winfo_height()
            if cw <= 1:
                cw, ch = 200, 32
            mid_y = ch // 2
            sc = self._get_state_colors()
            accent = sc["accent"]
            glow = sc["glow"]
            if self.state == "Idle":
                amp = 1.2
                speed = 0.04
            elif self.state in ("Listening", "Speaking"):
                scaled_rms = min(1.0, self._smoothed_rms * 22.0)
                amp = 2.0 + scaled_rms * 12.0
                speed = 0.12 + scaled_rms * 0.16
            elif self.state == "Transcribing":
                amp = 4.5
                speed = 0.26
            elif self.state == "Thinking":
                amp = 3.5
                speed = 0.16
            elif self.state == "Streaming":
                amp = 5.0 + math.sin(self.anim_frame * 0.05) * 1.5
                speed = 0.20
            elif self.state == "Complete":
                amp = 2.0
                speed = 0.07
            else:
                amp = 1.2
                speed = 0.04
            if self.reduced_motion:
                c.create_line(0, mid_y, cw, mid_y, fill=accent, width=1.5)
                return
            pts1 = self._calc_wave_points(cw, mid_y, amp * 0.55, speed * 0.5, freq=0.035, phase_offset=0.8)
            if pts1:
                r, g, b = self._hex_to_rgb(glow)
                dim_glow = f"#{r//5:02x}{g//5:02x}{b//5:02x}"
                c.create_line(pts1, fill=dim_glow, width=4, smooth=True)
            pts2 = self._calc_wave_points(cw, mid_y, amp, speed, freq=0.055, phase_offset=0.0)
            if pts2:
                c.create_line(pts2, fill=accent, width=1.6, smooth=True)
        except Exception:
            pass

    def _calc_wave_points(self, cw, mid_y, amplitude, speed, freq=0.05, phase_offset=0.0):
        points = []
        x_step = 3
        num_points = cw // x_step + 1
        for i in range(num_points):
            x = i * x_step
            envelope = math.sin(math.pi * (x / cw)) if cw > 0 else 1.0
            phase = self.anim_frame * speed + phase_offset
            y = mid_y + math.sin(x * freq + phase) * amplitude * envelope
            points.extend([x, y])
        return points if len(points) >= 4 else None

    def _get_state_colors(self) -> dict:
        if self.state == "Listening" and self.speech_prob >= 0.5:
            return STATE_COLORS["Speaking"]
        return STATE_COLORS.get(self.state, STATE_COLORS["Idle"])

    @staticmethod
    def _hex_to_rgb(hex_color: str) -> tuple:
        h = hex_color.lstrip("#")
        return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))

    def _on_close(self):
        self.stop_listening()
        self.root.destroy()
        sys.exit(0)
