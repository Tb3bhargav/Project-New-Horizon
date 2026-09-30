"""
Silero VAD Speech & 1-Second Silence Detector for Project New Horizon.
"""

import time
import numpy as np

class SileroVADDetector:
    """
    Wrapper for Silero VAD model with fallback mechanism.
    Evaluates audio frames (16kHz, float32) for speech probability.
    """
    def __init__(self, threshold: float = 0.5):
        self.threshold = threshold
        self.model = None
        self.torch = None
        self.use_silero = False
        self.ambient_noise_floor = 0.001
        self._init_silero()

    def reset(self):
        """Reset internal state/noise floor for a new listening session."""
        self.ambient_noise_floor = 0.001
        if hasattr(self.model, 'reset_states'):
            try:
                self.model.reset_states()
            except Exception:
                pass

    def _init_silero(self):
        try:
            import torch
            import silero_vad
            self.torch = torch
            self.model = silero_vad.load_silero_vad()
            self.use_silero = True
        except Exception:
            try:
                import torch
                self.torch = torch
                model, _ = torch.hub.load(
                    repo_or_dir='snakers4/silero-vad',
                    model='silero_vad',
                    force_reload=False,
                    onnx=False
                )
                self.model = model
                self.use_silero = True
            except Exception:
                self.use_silero = False

    def get_speech_prob(self, chunk: np.ndarray, sample_rate: int = 16000) -> float:
        """
        Calculate probability of speech in audio chunk.
        Audio chunk expected: 1D numpy array of float32 in [-1.0, 1.0].
        """
        if chunk is None or len(chunk) == 0:
            return 0.0

        if self.use_silero and self.model is not None and self.torch is not None:
            try:
                tensor = self.torch.from_numpy(chunk).float()
                if tensor.ndim == 1:
                    tensor = tensor.unsqueeze(0)
                with self.torch.no_grad():
                    prob = self.model(tensor, sample_rate).item()
                return float(prob)
            except Exception:
                pass

        # Robust Adaptive Energy / RMS fallback.
        # Tracks background noise floor dynamically so mic hum or ambient noise
        # doesn't lock the VAD in constant speech state.
        rms = np.sqrt(np.mean(chunk**2)) if len(chunk) > 0 else 0.0
        
        if rms < self.ambient_noise_floor:
            self.ambient_noise_floor = 0.95 * self.ambient_noise_floor + 0.05 * rms
        else:
            self.ambient_noise_floor = 0.998 * self.ambient_noise_floor + 0.002 * rms
            
        noise_gate = max(0.001, self.ambient_noise_floor + 0.002)
        prob = min(1.0, max(0.0, (rms - noise_gate) / 0.005))
        return float(prob)


class SilenceDetector:
    """
    Monitors speech activity and detects 1.0 second of continuous silence
    following speech to signal the end of an utterance.
    """
    def __init__(self, silence_duration_sec: float = 1.0, speech_threshold: float = 0.5):
        self.silence_duration_sec = silence_duration_sec
        self.speech_threshold = speech_threshold
        self.vad = SileroVADDetector(threshold=speech_threshold)
        
        self.speech_active = False
        self.has_spoken = False
        self.silence_start_time = None

    def reset(self):
        """Reset state for a fresh listening session."""
        self.speech_active = False
        self.has_spoken = False
        self.silence_start_time = None
        if hasattr(self.vad, 'reset'):
            try:
                self.vad.reset()
            except Exception:
                pass

    def process_chunk(self, chunk: np.ndarray, sample_rate: int = 16000) -> dict:
        """
        Process audio chunk and update VAD / silence state.
        
        Returns:
            dict with keys:
            - speech_prob (float)
            - is_speech (bool)
            - rms (float)
            - utterance_complete (bool)
        """
        rms = float(np.sqrt(np.mean(chunk**2))) if (chunk is not None and len(chunk) > 0) else 0.0
        prob = self.vad.get_speech_prob(chunk, sample_rate=sample_rate)
        is_speech = prob >= self.speech_threshold

        utterance_complete = False
        now = time.time()

        if is_speech:
            self.speech_active = True
            self.has_spoken = True
            self.silence_start_time = None
        else:
            self.speech_active = False
            if self.has_spoken:
                if self.silence_start_time is None:
                    self.silence_start_time = now
                else:
                    elapsed = now - self.silence_start_time
                    if elapsed >= self.silence_duration_sec:
                        utterance_complete = True
                        # Reset utterance speech flag after completion
                        self.has_spoken = False
                        self.silence_start_time = None

        return {
            "speech_prob": prob,
            "is_speech": is_speech,
            "rms": rms,
            "utterance_complete": utterance_complete
        }
