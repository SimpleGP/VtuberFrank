import json
import os
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, patch

import cv2
import numpy as np

from avatar_server import SharedState
from overwatch_detector import Detector, HeroScanGate, ROI, monitor, portrait_rectangle

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

    def test_reported_cassidy_genji_and_junker_queen_hud_regressions(self):
        for hero in ('cassidy', 'genji', 'junker-queen'):
            region = cv2.imread(str(ROOT / 'tests/fixtures' / f'{hero}-hud.png'))
            with self.subTest(hero=hero):
                self.assertEqual(self.detector.recognize_region(region).hero, hero)
                altered = np.clip(region.astype(float) * .8 + 10, 0, 255).astype(np.uint8)
                encoded = cv2.imencode('.jpg', altered, [cv2.IMWRITE_JPEG_QUALITY, 60])[1]
                compressed = cv2.imdecode(encoded, cv2.IMREAD_COLOR)
                self.assertEqual(self.detector.recognize_region(compressed).hero, hero)

    def test_portrait_size_and_aspect_changes(self):
        for hero in ('cassidy', 'genji', 'junker-queen'):
            template = self.detector.templates[hero][-1]
            for sx, sy in ((.65, 1), (.8, .85), (1.2, 1.15)):
                scaled = cv2.resize(template, None, fx=sx, fy=sy)
                height, width = scaled.shape[:2]
                region = np.full((210, 145, 3), 70, dtype=np.uint8)
                region[30:30 + height, 10:10 + width] = scaled
                with self.subTest(hero=hero, width=sx, height=sy):
                    self.assertEqual(self.detector.recognize_region(region).hero, hero)


class GateTests(unittest.TestCase):
    def test_one_check_after_half_second_and_hold_does_not_repeat(self):
        gate = HeroScanGate()
        self.assertFalse(gate.update(True, 0))
        self.assertFalse(gate.update(True, .49))
        self.assertTrue(gate.update(True, .5))
        self.assertFalse(gate.update(True, .64))
        self.assertFalse(gate.update(True, .66))
        self.assertFalse(gate.update(True, .82))
        for now in (1, 3, 100):
            self.assertFalse(gate.update(True, now))
        self.assertFalse(gate.update(False, 101))
        self.assertFalse(gate.update(True, 102))
        self.assertTrue(gate.update(True, 102.5))

    def test_manual_mode_cancels_request(self):
        gate = HeroScanGate()
        gate.update(True, 0)
        self.assertFalse(gate.update(True, .6, enabled=False))
        self.assertFalse(gate.update(True, .7, enabled=True))


class MonitorTests(unittest.TestCase):
    def run_scan(self, region, visible=True):
        shared = SharedState({'last_hero': 'ramattra', 'hero_mode': 'auto'})
        shared.update(speaking=True)
        times, index, decisions = [0, .49, .5, 1, 10], [-1], []
        stop = MagicMock()

        def wait(_):
            index[0] += 1
            if index[0] == len(times):
                return True
            if times[index[0]] < .5:
                self.assertEqual(shared.snapshot()['hero'], 'ramattra')
            return False

        stop.wait.side_effect = wait
        game, capture = MagicMock(), MagicMock()
        game.rectangle.return_value = (dict(left=0, top=0, width=1920, height=1080)
                                       if visible else None)
        game.scan_key_down.return_value = True
        capture.__enter__.return_value = capture
        capture.grab.return_value = region
        modules = {'window_capture': SimpleNamespace(GameWindow=lambda: game),
                   'mss': SimpleNamespace(MSS=lambda: capture)}
        with patch.dict(sys.modules, modules), patch('overwatch_detector.time.monotonic',
                                                     side_effect=lambda: times[index[0]]):
            monitor(shared, stop, lambda hero: decisions.append((times[index[0]], hero)))
        self.assertEqual(len(decisions), 1)
        self.assertEqual(decisions[0][0], .5)
        self.assertTrue(shared.snapshot()['speaking'])
        self.assertEqual(shared.snapshot()['hero_scan']['count'], 1)
        self.assertEqual(capture.grab.call_count, 1 if visible else 0)
        return shared.snapshot(), decisions[0][1]

    def test_unknown_portrait_returns_original_at_half_second(self):
        state, selected = self.run_scan(np.zeros((210, 145, 4), dtype=np.uint8))
        self.assertEqual((state['hero'], selected), ('base', 'base'))
        self.assertEqual(state['hero_scan']['confirmed'], 0)

    def test_missing_game_portrait_also_returns_original(self):
        state, selected = self.run_scan(None, visible=False)
        self.assertEqual((state['hero'], selected), ('base', 'base'))
        self.assertFalse(state['overwatch']['visible'])

    def test_recognized_portrait_changes_skin_in_the_same_check(self):
        template = Detector(ROOT).templates['sigma'][0]
        region = np.zeros((210, 145, 4), dtype=np.uint8)
        height, width = template.shape[:2]
        region[58:58 + height, 32:32 + width, :3] = template
        state, selected = self.run_scan(region)
        self.assertEqual((state['hero'], selected), ('sigma', 'sigma'))
        self.assertEqual(state['hero_scan']['confirmed'], 1)


if __name__ == '__main__':
    unittest.main()
