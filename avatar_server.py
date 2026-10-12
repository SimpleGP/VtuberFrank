"""Local companion: voice-driven mouth and one requested hero scan; no recordings."""
import argparse
import copy
import json
import mimetypes
import os
from pathlib import Path
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import unquote, urlparse
from voice_activity import effective_threshold

ROOT = Path(__file__).resolve().parent
DIST = ROOT / 'dist'
PORT = 18766  # Does not replace D:\Vtuber's existing service on 18765.
CATALOG = json.loads((DIST / 'catalog.json').read_text(encoding='utf-8'))
HEROES = {hero['id'] for hero in CATALOG['heroes']}
SETTINGS = ROOT / 'settings.json'


class SharedState:
    def __init__(self, settings=None):
        settings = settings or {}
        self.lock = threading.RLock()
        threshold = effective_threshold(settings.get('threshold'))
        self.data = dict(version=1, db=-100, speaking=False, threshold=threshold,
                         microphone='Preparando voz',
                         hero=settings.get('last_hero') if settings.get('last_hero') in HEROES else 'base',
                         hero_mode='manual' if settings.get('hero_mode') == 'manual' else 'auto',
                         scan_request=None,
                         hero_scan=dict(mode='key', delay=.5, scan_code=41, count=0, confirmed=0),
                         overwatch=dict(status='Tecla encima de Tab para revisar', visible=False, confidence=0))

    def update(self, **values):
        with self.lock:
            self.data.update(values)

    def snapshot(self):
        with self.lock:
            return copy.deepcopy(self.data)


def read_settings():
    try:
        value = json.loads(SETTINGS.read_text(encoding='utf-8-sig'))
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError):
        return {}


def create_server(port=PORT, settings=None):
    settings = settings if settings is not None else read_settings()
    shared, stop = SharedState(settings), threading.Event()
    save_lock = threading.Lock()

    def save(**values):
        with save_lock:
            settings.update(values)
            temporary = SETTINGS.with_suffix('.tmp')
            temporary.write_text(json.dumps(settings, ensure_ascii=False, indent=2), encoding='utf-8')
            temporary.replace(SETTINGS)

    allowed_origins = {f'http://127.0.0.1:{port}', f'http://localhost:{port}',
                       'https://simplegp.github.io'}

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def trusted(self):
            return (self.headers.get('Host') in {f'127.0.0.1:{self.server.server_port}',
                                                f'localhost:{self.server.server_port}'}
                    and self.headers.get('Origin') in (None, *allowed_origins))

        def reply(self, value, status=200, mime='application/json'):
            data = value if isinstance(value, bytes) else json.dumps(value, allow_nan=False).encode()
            self.send_response(status)
            self.send_header('Content-Type', mime)
            self.send_header('Content-Length', str(len(data)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            origin = self.headers.get('Origin')
            if origin in allowed_origins:
                self.send_header('Access-Control-Allow-Origin', origin)
                self.send_header('Vary', 'Origin')
                self.send_header('Access-Control-Allow-Private-Network', 'true')
            self.end_headers()
            self.wfile.write(data)

        def do_OPTIONS(self):
            if not self.trusted():
                return self.reply({'error': 'Origen no permitido'}, 403)
            self.send_response(204)
            self.send_header('Access-Control-Allow-Origin', self.headers.get('Origin', f'http://127.0.0.1:{port}'))
            self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
            self.send_header('Access-Control-Allow-Headers', 'Content-Type')
            self.send_header('Access-Control-Allow-Private-Network', 'true')
            self.end_headers()

        def do_GET(self):
            if not self.trusted():
                return self.reply({'error': 'Origen no permitido'}, 403)
            path = unquote(urlparse(self.path).path)
            if path == '/health':
                return self.reply({'service': 'FrankVtuber', 'version': 1})
            if path == '/state':
                return self.reply(shared.snapshot())
            path = {'/': '/index.html', '/avatar': '/avatar.html'}.get(path, path)
            if path.startswith('/screens/'):
                path = '/scenes/' + path.removeprefix('/screens/') + '.html'
            file = (DIST / path.lstrip('/')).resolve()
            if DIST.resolve() not in file.parents or any(part.startswith('.') for part in Path(path).parts):
                return self.reply({'error': 'Archivo no permitido'}, 404)
            if not file.is_file():
                return self.reply({'error': 'Archivo no encontrado'}, 404)
            mime = mimetypes.guess_type(file.name)[0] or 'application/octet-stream'
            if mime.startswith('text/') or mime == 'application/javascript':
                mime += '; charset=utf-8'
            return self.reply(file.read_bytes(), mime=mime)

        def do_POST(self):
            if not self.trusted():
                return self.reply({'error': 'Origen no permitido'}, 403)
            path = urlparse(self.path).path
            try:
                length = int(self.headers.get('Content-Length', '0'))
                if not 0 <= length <= 1024 * 1024:
                    raise ValueError('Solicitud demasiado grande')
                payload = json.loads(self.rfile.read(length)) if length else {}
                if not isinstance(payload, dict):
                    raise ValueError('Se necesita un objeto JSON')
                if path == '/hero':
                    hero = payload.get('hero')
                    if not isinstance(hero, str) or hero not in (*HEROES, 'auto'):
                        raise ValueError('Héroe desconocido')
                    mode = 'auto' if hero == 'auto' else 'manual'
                    with shared.lock:
                        shared.data['hero_mode'] = mode
                        shared.data['scan_request'] = None
                        if hero != 'auto':
                            shared.data['hero'] = hero
                        selected = shared.data['hero']
                    save(hero_mode=mode, last_hero=selected)
                elif path == '/scan':
                    shared.update(hero_mode='auto', scan_request=time.monotonic() + 3)
                    save(hero_mode='auto')
                elif path == '/calibrate':
                    import base64
                    import cv2
                    import numpy as np
                    hero = payload.get('hero')
                    if not isinstance(hero, str) or hero not in HEROES - {'base'}:
                        raise ValueError('Selecciona un héroe para el retrato')
                    raw = base64.b64decode(payload.get('portrait', ''), validate=True)
                    if not raw:
                        raise ValueError('Falta el retrato')
                    image = cv2.imdecode(np.frombuffer(raw, np.uint8), cv2.IMREAD_COLOR)
                    if image is None or image.shape[:2] != (109, 88):
                        raise ValueError('El retrato debe medir 88 × 109')
                    folder = ROOT / 'user-data/templates' / hero
                    folder.mkdir(parents=True, exist_ok=True)
                    cv2.imencode('.png', image)[1].tofile(str(folder / 'custom.png'))
                    shared.update(reload_templates=True)
                elif path == '/shutdown':
                    self.reply({'ok': True})
                    stop.set()
                    threading.Thread(target=self.server.shutdown, daemon=True).start()
                    return
                else:
                    return self.reply({'error': 'Ruta desconocida'}, 404)
                self.reply({'ok': True})
            except (ValueError, KeyError, TypeError, OSError) as error:
                self.reply({'error': str(error)}, 400)

    server = ThreadingHTTPServer(('127.0.0.1', port), Handler)
    server.shared, server.stop = shared, stop
    server.settings, server.remember = settings, lambda hero: save(last_hero=hero)
    return server


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, default=PORT)
    parser.add_argument('--no-devices', action='store_true', help='Prueba HTTP sin audio, teclas, capturas u OBS')
    args = parser.parse_args()
    server = create_server(args.port)
    workers = []
    if args.no_devices or os.name != 'nt':
        server.shared.update(microphone='Vista previa · sin dispositivos')
    else:
        from audio_capture import microphone
        from overwatch_detector import monitor
        for function, arguments in (
            (microphone, (server.shared, server.stop, server.settings)),
            (monitor, (server.shared, server.stop, server.remember))):
            worker = threading.Thread(target=function, args=arguments, daemon=True)
            worker.start()
            workers.append(worker)
    print(f'FrankVtuber listo: http://127.0.0.1:{args.port}/', flush=True)
    try:
        server.serve_forever(poll_interval=.2)
    except KeyboardInterrupt:
        pass
    finally:
        server.stop.set()
        server.server_close()
        for worker in workers:
            worker.join(timeout=2)


if __name__ == '__main__':
    main()
