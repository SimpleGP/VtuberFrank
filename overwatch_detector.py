"""Recognition is limited to the player's lower-left HUD portrait. No OCR/chat."""
from dataclasses import dataclass
from pathlib import Path
import json
import time

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parent
REFERENCE_WIDTH, REFERENCE_HEIGHT = 1920, 1080
ROI = (30, 830, 175, 1040)  # x, y, right, bottom; never health, name, chat or abilities


@dataclass(frozen=True)
class Observation:
    hero: str | None = None
    confidence: float = 0.0
    source: str = "retrato inferior izquierdo"


def normalize(frame):
    if frame is None or frame.ndim != 3 or frame.shape[2] < 3:
        raise ValueError("Se necesita una imagen RGB/BGR")
    return cv2.resize(frame[:, :, :3], (REFERENCE_WIDTH, REFERENCE_HEIGHT))


def portrait(frame):
    normalized = normalize(frame)
    x, y, right, bottom = ROI
    return normalized[y:bottom, x:right]


def portrait_rectangle(client):
    """Capture ONLY the portrait rectangle, not the whole game/screen."""
    x, y, right, bottom = ROI
    left = round(client['width'] * x / REFERENCE_WIDTH)
    top = round(client['height'] * y / REFERENCE_HEIGHT)
    width = max(1, round(client['width'] * right / REFERENCE_WIDTH) - left)
    height = max(1, round(client['height'] * bottom / REFERENCE_HEIGHT) - top)
    return dict(left=client['left'] + left, top=client['top'] + top,
                width=width, height=height)


class Detector:
    def __init__(self, root=ROOT):
        root = Path(root)
        catalog = json.loads((root / 'dist/catalog.json').read_text(encoding='utf-8'))
        self.heroes = tuple(h['id'] for h in catalog['heroes'] if h['id'] != 'base')
        self.templates = {}
        for hero in self.heroes:
            files = [root / 'dist/assets/portraits' / f'{hero}.png']
            files += list((root / 'user-data/templates' / hero).glob('*.png'))
            images = [cv2.imdecode(np.fromfile(str(p), dtype=np.uint8), cv2.IMREAD_COLOR)
                      for p in files if p.is_file()]
            self.templates[hero] = [image for image in images if image is not None]
        if not any(self.templates.values()):
            raise ValueError('Faltan los retratos de referencia')

    def recognize_region(self, region):
        if region is None or not region.size:
            return Observation()
        x, y, right, bottom = ROI
        region = cv2.resize(region[:, :, :3], (right - x, bottom - y))
        ranked = []
        for hero, templates in self.templates.items():
            score = 0.0
            for template in templates:
                height, width = template.shape[:2]
                if height > region.shape[0] or width > region.shape[1]:
                    continue
                result = cv2.matchTemplate(region, template, cv2.TM_CCOEFF_NORMED)
                score = max(score, float(cv2.minMaxLoc(result)[1]))
            ranked.append((score, hero))
        ranked.sort(reverse=True)
        best, hero = ranked[0]
        runner_up = ranked[1][0] if len(ranked) > 1 else 0
        if best >= .72 and best - runner_up >= .08:
            return Observation(hero, best)
        return Observation(confidence=best)

    def recognize(self, frame):
        return self.recognize_region(portrait(frame))


class HeroScanGate:
    """One three-frame burst per physical press: .5s wait, .15s between frames."""
    def __init__(self):
        self.down = False
        self.due = None
        self.remaining = 0

    def request(self, now, delay=.5):
        self.due = now + delay
        self.remaining = 3

    def update(self, down, now, enabled=True):
        rising = down and not self.down
        self.down = down
        if not enabled:
            self.confirmed()
            return False
        if rising:
            self.request(now)
        if self.due is None or now < self.due:
            return False
        self.remaining -= 1
        self.due = now + .15 if self.remaining else None
        return True

    def confirmed(self):
        self.due = None
        self.remaining = 0


def monitor(shared, stop, remember):
    from window_capture import GameWindow
    from mss import MSS
    try:
        game, detector, gate = GameWindow(), Detector(), HeroScanGate()
        candidate, hits = None, 0
        with MSS() as capture:
            while not stop.wait(.025):
                now = time.monotonic()
                snapshot = shared.snapshot()
                if snapshot.get('reload_templates'):
                    detector = Detector()
                    shared.update(reload_templates=False)
                client = game.rectangle()
                enabled = snapshot['hero_mode'] == 'auto' and client is not None
                due = gate.update(game.scan_key_down(), now, enabled)
                request = snapshot.get('scan_request')
                if request is not None and now >= request:
                    if enabled:
                        gate.request(now, delay=0)
                        due = gate.update(False, now, True)
                        shared.update(scan_request=None)
                    elif now >= request + 5:
                        shared.update(scan_request=None, overwatch=dict(
                            status='Abre Overwatch y vuelve a revisar', visible=False, confidence=0))
                if client is None:
                    shared.update(overwatch=dict(status='Abre Overwatch · tecla encima de Tab',
                                                  visible=False, confidence=0))
                    candidate, hits = None, 0
                    continue
                if not due:
                    continue  # No screenshots or continuous recognition between presses.
                if gate.remaining == 2:
                    candidate, hits = None, 0
                region = np.asarray(capture.grab(portrait_rectangle(client)))[:, :, :3]
                observation = detector.recognize_region(region)
                hits = hits + 1 if observation.hero and candidate == observation.hero else (1 if observation.hero else 0)
                candidate = observation.hero
                status = 'Revisando retrato…'
                if observation.hero and hits >= 2:
                    shared.update(hero=observation.hero)
                    remember(observation.hero)
                    gate.confirmed()
                    status = 'Héroe confirmado · revisa de nuevo con la tecla'
                elif gate.due is None:
                    shared.update(hero='base')
                    remember('base')
                    status = 'Sin coincidencia · Richard original'
                with shared.lock:
                    shared.data['hero_scan']['count'] += 1
                    if observation.hero and hits >= 2:
                        shared.data['hero_scan']['confirmed'] += 1
                    shared.data['overwatch'] = dict(status=status, visible=True,
                                                  confidence=round(observation.confidence, 3),
                                                  source=observation.source)
    except Exception as error:
        shared.update(overwatch=dict(status=f'Detección no disponible: {error}', visible=False, confidence=0))

