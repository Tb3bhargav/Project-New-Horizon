"""
Microphone Audio Recorder for Project New Horizon.
Manages continuous microphone recording with explicit error handling.
"""

import threading
import numpy as np
import sounddevice as sd

class AudioRecorder:
    def __init__(self, sample_rate: int = 16000, block_size: int = 512):
        self.sample_rate = sample_rate
        self.block_size = block_size
        self.stream = None
        self.is_recording = False
        self.lock = threading.Lock()
        self.on_chunk_callback = None
        self.on_error_callback = None

    @staticmethod
    def get_input_devices():
        """Returns list of available audio input devices."""
        try:
            devices = sd.query_devices()
            input_devices = [d for d in devices if d.get('max_input_channels', 0) > 0]
            return input_devices
        except Exception:
            return []

    @classmethod
    def check_microphone_status(cls) -> tuple[bool, str]:
        """
        Diagnostic helper to check if a valid input microphone is available.
        
        Returns:
            (is_available, message)
        """
        try:
            devices = cls.get_input_devices()
            if not devices:
                return False, "No microphone input device detected on system."
            
            # Check default device configuration
            default_input = sd.default.device[0]
            if default_input is not None and default_input < 0:
                return False, "No default microphone input device set."
                
            return True, "Microphone available."
        except Exception as e:
            return False, f"Microphone error: {e}"

    def start_recording(self, on_chunk_callback, on_error_callback):
        """
        Starts microphone recording stream.
        """
        with self.lock:
            if self.is_recording:
                return

            self.on_chunk_callback = on_chunk_callback
            self.on_error_callback = on_error_callback

            # Check input device availability
            devices = self.get_input_devices()
            if not devices:
                if self.on_error_callback:
                    self.on_error_callback("No microphone input device found on your system.")
                return

            def _audio_callback(indata, frames, time_info, status):
                if status:
                    # Non-fatal warnings (underflow/overflow)
                    pass
                if self.is_recording and self.on_chunk_callback:
                    # Pass a copy of 1D float32 audio numpy array
                    chunk = indata[:, 0].astype(np.float32)
                    if hasattr(self, '_resample_ratio') and self._resample_ratio != 1.0:
                        target_len = int(round(len(chunk) * self._resample_ratio))
                        if target_len > 0:
                            old_indices = np.linspace(0, len(chunk) - 1, len(chunk))
                            new_indices = np.linspace(0, len(chunk) - 1, target_len)
                            chunk = np.interp(new_indices, old_indices, chunk).astype(np.float32)
                    self.on_chunk_callback(chunk)

            self._resample_ratio = 1.0
            try:
                self.stream = sd.InputStream(
                    samplerate=self.sample_rate,
                    channels=1,
                    dtype='float32',
                    blocksize=self.block_size,
                    callback=_audio_callback
                )
                self.stream.start()
                self.is_recording = True
            except (sd.PortAudioError, Exception) as primary_err:
                # Try default device sample rate fallback
                try:
                    default_info = sd.query_devices(kind='input')
                    native_rate = int(default_info.get('default_samplerate', 44100))
                    if native_rate != self.sample_rate:
                        self._resample_ratio = self.sample_rate / float(native_rate)
                        native_block = int(round(self.block_size / self._resample_ratio))
                        self.stream = sd.InputStream(
                            samplerate=native_rate,
                            channels=1,
                            dtype='float32',
                            blocksize=native_block,
                            callback=_audio_callback
                        )
                        self.stream.start()
                        self.is_recording = True
                    else:
                        raise primary_err
                except Exception as fallback_err:
                    self.is_recording = False
                    if self.on_error_callback:
                        self.on_error_callback(f"Microphone access error: {primary_err}")

    def stop_recording(self):
        """
        Stops and closes microphone recording stream.
        """
        with self.lock:
            self.is_recording = False
            if self.stream is not None:
                try:
                    self.stream.stop()
                    self.stream.close()
                except Exception:
                    pass
                self.stream = None

    def is_active(self) -> bool:
        """Returns whether recording is currently active."""
        with self.lock:
            return self.is_recording


class UtteranceBuffer:
    """
    Accumulates audio chunks to form a complete utterance.

    Maintains a short rolling pre-speech window so the start of speech is
    not clipped.  After utterance_complete is signalled by the SilenceDetector,
    call get_utterance_audio() to retrieve the full utterance as a contiguous
    float32 numpy array (16 kHz mono), then call reset() before the next
    utterance.
    """

    def __init__(self, pre_speech_chunks: int = 10):
        """
        Args:
            pre_speech_chunks: Number of recent silent chunks to keep as a
                rolling window before speech starts, so the very beginning of
                the utterance is not lost.  At 512 samples / 16 kHz ≈ 32 ms
                per chunk, 10 chunks ≈ 320 ms of look-back.
        """
        from collections import deque

        self.pre_speech_chunks = pre_speech_chunks
        self._pre_buffer: deque = deque(maxlen=pre_speech_chunks)
        self._speech_buffer: list = []
        self._speech_started = False

    def feed(self, chunk: np.ndarray, is_speech: bool) -> None:
        """
        Feed an audio chunk along with its speech classification.

        Args:
            chunk: 1-D float32 numpy array from the microphone.
            is_speech: Whether the VAD considers this chunk speech.
        """
        if is_speech:
            if not self._speech_started:
                # Flush the pre-speech window into the main buffer
                self._speech_buffer.extend(self._pre_buffer)
                self._pre_buffer.clear()
                self._speech_started = True
            self._speech_buffer.append(chunk.copy())
        else:
            if self._speech_started:
                # Still collect trailing silence (part of the utterance boundary)
                self._speech_buffer.append(chunk.copy())
            else:
                # Not yet speaking — keep a rolling pre-speech window
                self._pre_buffer.append(chunk.copy())

    def get_utterance_audio(self) -> np.ndarray | None:
        """
        Return the accumulated utterance as a single float32 numpy array,
        or None if no speech was captured.
        """
        if not self._speech_buffer:
            return None
        return np.concatenate(self._speech_buffer)

    def reset(self) -> None:
        """Clear all buffers for the next utterance."""
        self._pre_buffer.clear()
        self._speech_buffer.clear()
        self._speech_started = False
