import math
import unittest

from avatar_server import SharedState
from voice_activity import VoiceGate, pcm_db


class VoiceTests(unittest.TestCase):
    def test_normal_quiet_pcm_opens_without_shouting(self):
        amplitude = round(32768 * 10 ** (-48 / 20))
        samples = [amplitude, -amplitude] * 441
        db = pcm_db(samples)
        self.assertLess(db, -38)  # Previously missed by the old default.
        self.assertTrue(VoiceGate().update(db, 0))

    def test_soft_syllables_and_short_pauses_do_not_flicker(self):
        gate = VoiceGate()
        self.assertTrue(gate.update(-48, 0))
        self.assertTrue(gate.update(-53, .2))
        self.assertTrue(gate.update(-53, .4))
        self.assertTrue(gate.update(-100, .55))
        self.assertFalse(gate.update(-100, .66))

    def test_background_and_empty_audio_do_not_open_at_start(self):
        gate = VoiceGate()
        for now in (0, 1, 20):
            self.assertFalse(gate.update(-60, now))
        self.assertFalse(gate.update(pcm_db([]), 21))
        self.assertEqual(pcm_db([0] * 882), -100)

    def test_quiet_background_does_not_extend_release_forever(self):
        gate = VoiceGate()
        gate.update(-40, 0)
        self.assertTrue(gate.update(-60, .2))
        self.assertFalse(gate.update(-60, .26))

    def test_existing_installations_get_sensitivity_fix_without_editing_settings(self):
        settings = {'threshold': -38, 'microphone_endpoint': 'keep-this-device'}
        self.assertEqual(SharedState(settings).snapshot()['threshold'], -50)
        self.assertEqual(settings, {'threshold': -38, 'microphone_endpoint': 'keep-this-device'})
        self.assertEqual(SharedState({'threshold': -60}).snapshot()['threshold'], -60)
        for value in (None, True, math.nan, math.inf, 'invalid'):
            self.assertEqual(SharedState({'threshold': value}).snapshot()['threshold'], -50)


if __name__ == '__main__':
    unittest.main()
