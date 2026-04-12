import threading
import keyboard
import numpy as np

from audio import MicRecorder
from transcriber import Transcriber
from paste import paste_text
import snippets as snippet_module

MIN_AUDIO_SAMPLES = 3200  # 0.2 s at 16 kHz — ignore accidental taps


class DictationMode:
    def __init__(self, transcriber: Transcriber, hotkey: str = "ctrl+space",
                 on_status=None, indicator=None, on_mic_error=None):
        self.transcriber = transcriber
        self.hotkey = hotkey
        self.recorder = MicRecorder()
        self.on_status = on_status or (lambda msg: None)
        self.indicator = indicator
        self.on_mic_error = on_mic_error or (lambda msg: None)
        self._active = False
        self._recording = False

        if "+" in self.hotkey:
            parts = self.hotkey.split("+")
            self._trigger_key = parts[-1]
            self._modifier = "+".join(parts[:-1])
        else:
            self._trigger_key = self.hotkey
            self._modifier = None

    # ------------------------------------------------------------------ public

    def start(self):
        self._active = True
        keyboard.on_press_key(self._trigger_key, self._on_press, suppress=False)
        keyboard.on_release_key(self._trigger_key, self._on_release, suppress=False)
        self.on_status(f"Ready — hold {self.hotkey.upper()} to speak")

    def stop(self):
        self._active = False
        try:
            keyboard.unhook_all()
        except Exception:
            pass

    # ----------------------------------------------------------------- private

    def _modifier_held(self) -> bool:
        if not self._modifier:
            return True
        return keyboard.is_pressed(self._modifier)

    def _on_press(self, _):
        if self._active and not self._recording and self._modifier_held():
            self._recording = True
            try:
                self.recorder.start()
            except Exception as e:
                self._recording = False
                print(f"Mic start error: {e}", flush=True)
                self.on_status("Mic unavailable — check input device/permissions")
                self.on_mic_error(str(e))
                if self.indicator:
                    self.indicator.show("Mic unavailable for freewispr", state="error")
                    self.indicator.hide(delay_ms=2200)
                return
            self.on_status("Listening…")
            if self.indicator:
                self.indicator.show("Listening…", state="listen")

    def _on_release(self, _):
        if self._active and self._recording:
            self._recording = False
            audio = self.recorder.stop()
            if len(audio) < MIN_AUDIO_SAMPLES:
                self.on_status(f"Ready — hold {self.hotkey.upper()} to speak")
                if self.indicator:
                    self.indicator.hide(delay_ms=0)
                return
            self.on_status("Transcribing…")
            if self.indicator:
                self.indicator.show("Transcribing…", state="transcribe")
            threading.Thread(target=self._transcribe, args=(audio,), daemon=True).start()

    def _transcribe(self, audio: np.ndarray):
        print("Transcribing...", flush=True)
        try:
            text = self.transcriber.transcribe(audio)
            # Apply snippet expansion — if full text is a trigger, replace it
            text = snippet_module.expand(text)
            print(f"Result: '{text}'", flush=True)
            if text.strip():
                paste_text(text)
                self.on_status(f"Pasted — hold {self.hotkey.upper()} to speak again")
                if self.indicator:
                    self.indicator.show("Pasted ✓", state="done")
                    self.indicator.hide(delay_ms=1800)
            else:
                self.on_status(f"Nothing detected — hold {self.hotkey.upper()} to speak")
                if self.indicator:
                    self.indicator.hide(delay_ms=0)
        except Exception as e:
            print(f"Transcribe error: {e}", flush=True)
            self.on_status(f"Ready — hold {self.hotkey.upper()} to speak")
            if self.indicator:
                self.indicator.hide(delay_ms=0)
