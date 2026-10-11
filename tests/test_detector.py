import json
import os
from pathlib import Path
import unittest

import cv2
import numpy as np

from overwatch_detector import Detector, HeroScanGate, ROI, portrait_rectangle

ROOT = Path(__file__).resolve().parents[1]


class DetectionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.detector = Detector(ROOT)

    def fixture(self, hero):
        template = self.detector.templates[hero][0]
        frame = np.full((1080, 1920, 3), 95, dtype=np.uint8)
        x, y = 62, 888
        frame[y:y + template.shape[0], x:x + template.shape[1]] = template
        return frame

    def test_supported_icons_without_other_game_content(self):
        for hero in self.detector.heroes:
            with self.subTest(hero=hero):
                self.assertEqual(self.detector.recognize(self.fixture(hero)).hero, hero)

    def test_only_lower_left_portrait_can_select_a_hero(self):
        frame = np.full((1080, 1920, 3), 90, dtype=np.uint8)
        template = self.detector.templates['sigma'][0]
        for x, y in [(1600, 870), (200, 600), (820, 400)]:
            frame[y:y + template.shape[0], x:x + template.shape[1]] = template
        self.assertIsNone(self.detector.recognize(frame).hero)

    def test_changing_chat_abilities_and_world_cannot_change_result(self):
        frame = self.fixture('sombra')
        altered = np.random.default_rng(4).integers(0, 256, frame.shape, dtype=np.uint8)
        x, y, right, bottom = ROI
        altered[y:bottom, x:right] = frame[y:bottom, x:right]
        self.assertEqual(self.detector.recognize(altered).hero, 'sombra')

    def test_blank_or_unknown_portrait_is_not_a_guess(self):
        self.assertIsNone(self.detector.recognize(np.zeros((1080, 1920, 3), dtype=np.uint8)).hero)
        frame = np.random.default_rng(5).integers(0, 256, (1080, 1920, 3), dtype=np.uint8)
        self.assertIsNone(self.detector.recognize(frame).hero)

    def test_resolution_and_brightness_variation(self):
        for hero in ('sigma', 'ramattra', 'mauga', 'ashe', 'sojourn', 'illari', 'genji'):
            frame = self.fixture(hero)
            frame = np.clip(frame.astype(float) * .8 + 8, 0, 255).astype(np.uint8)
            frame = cv2.resize(frame, (1280, 720))
            with self.subTest(hero=hero):
                self.assertEqual(self.detector.recognize(frame).hero, hero)

    def test_actual_user_screenshots_when_provided(self):
        path = os.environ.get('FRANK_TEST_SCREENSHOTS')
        if not path:
            self.skipTest('Private screenshots are intentionally not published')
        references = json.loads(Path(path).read_text(encoding='utf-8'))
        self.assertEqual(len(references), 9)
        for expected, file in references.items():
            frame = cv2.imdecode(np.fromfile(file, dtype=np.uint8), cv2.IMREAD_COLOR)
            with self.subTest(hero=expected):
                self.assertEqual(self.detector.recognize(frame).hero, expected)
                resized = cv2.resize(frame, (1280, 720))
                self.assertEqual(self.detector.recognize(resized).hero, expected)

    def test_live_capture_is_only_a_small_portrait_rectangle(self):
        area = portrait_rectangle(dict(left=100, top=50, width=1920, height=1080))
        self.assertEqual(area, dict(left=130, top=880, width=145, height=210))
        self.assertLess(area['width'] * area['height'], 1920 * 1080 / 50)


class GateTests(unittest.TestCase):
    def test_delay_burst_and_hold_do_not_continuously_capture(self):
        gate = HeroScanGate()
        self.assertFalse(gate.update(True, 0))
        self.assertFalse(gate.update(True, .49))
        self.assertTrue(gate.update(True, .5))
        self.assertFalse(gate.update(True, .64))
        self.assertTrue(gate.update(True, .66))
        self.assertTrue(gate.update(True, .82))
        for now in (1, 3, 100):
            self.assertFalse(gate.update(True, now))
        self.assertFalse(gate.update(False, 101))
        self.assertFalse(gate.update(True, 102))
        self.assertTrue(gate.update(True, 102.5))

    def test_lost_foreground_cancels_request(self):
        gate = HeroScanGate()
        gate.update(True, 0)
        self.assertFalse(gate.update(True, .6, enabled=False))
        self.assertFalse(gate.update(True, .7, enabled=True))


if __name__ == '__main__':
    unittest.main()
