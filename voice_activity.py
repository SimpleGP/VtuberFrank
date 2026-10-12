"""Volume-only mouth activity; no audio recording or speech transcription."""
import math

DEFAULT_THRESHOLD = -50


def effective_threshold(value=DEFAULT_THRESHOLD):
    # Older installations used -38 dBFS, which misses quiet normal speech.
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        value = DEFAULT_THRESHOLD
    return max(-70, min(DEFAULT_THRESHOLD, value))


def pcm_db(samples):
    if not samples:
        return -100.0
    rms = math.sqrt(sum(sample * sample for sample in samples) / len(samples)) / 32768
    return round(20 * math.log10(max(rms, .00001)), 1)


class VoiceGate:
    def __init__(self, threshold=DEFAULT_THRESHOLD):
        self.threshold = effective_threshold(threshold)
        self.hold_until = float('-inf')
        self.speaking = False

    def update(self, db, now):
        # Start on normal speech; sustain softer syllables once the mouth opens.
        threshold = self.threshold - 4 if self.speaking else self.threshold
        if db >= threshold:
            self.hold_until = now + .25
        self.speaking = now < self.hold_until
        return self.speaking
