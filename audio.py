import numpy as np
import sounddevice as sd

SAMPLE_RATE = 16000


class MicRecorder:
    """Records from mic while a hotkey is held."""

    def __init__(self):
        self.frames = []
        self.recording = False
        self._stream = None

    def start(self):
        self.frames = []
        self.recording = True
        try:
            self._stream = sd.InputStream(
                samplerate=SAMPLE_RATE,
                channels=1,
                dtype="float32",
                callback=self._cb,
            )
            self._stream.start()
        except Exception as e:
            self.recording = False
            self._stream = None
            raise RuntimeError(self._format_mic_error(e)) from e

    def _cb(self, indata, frames, time, status):
        if self.recording:
            self.frames.append(indata.copy())

    def stop(self) -> np.ndarray:
        self.recording = False
        if self._stream:
            self._stream.stop()
            self._stream.close()
            self._stream = None
        if not self.frames:
            return np.array([], dtype=np.float32)
        return np.concatenate(self.frames, axis=0).flatten()

    def _format_mic_error(self, err: Exception) -> str:
        details = [f"Could not open microphone stream ({err})."]

        try:
            default_device = sd.default.device
            if isinstance(default_device, (list, tuple)) and default_device:
                input_device = default_device[0]
            else:
                input_device = default_device
            details.append(f"Default input device: {input_device}")
        except Exception:
            pass

        try:
            devices = sd.query_devices()
            input_count = sum(1 for d in devices if d.get("max_input_channels", 0) > 0)
            details.append(f"Detected input-capable devices: {input_count}")
        except Exception:
            pass

        details.append("Check Windows mic privacy, default input device, and whether another app is exclusively using the mic.")
        return " ".join(details)
