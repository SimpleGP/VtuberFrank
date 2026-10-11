import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch
from urllib.request import Request, urlopen
from urllib.error import HTTPError

import avatar_server


class ServerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory()
        cls.settings_patch = patch.object(avatar_server, 'SETTINGS', Path(cls.temporary.name) / 'settings.json')
        cls.settings_patch.start()
        cls.server = avatar_server.create_server(0, settings={})
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base = f'http://127.0.0.1:{cls.server.server_port}'

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.thread.join(timeout=2)
        cls.server.server_close()
        cls.settings_patch.stop()
        cls.temporary.cleanup()

    def get(self, path):
        with urlopen(self.base + path, timeout=3) as response:
            return response.status, response.read()

    def post(self, path, value, headers=None):
        request = Request(self.base + path, data=json.dumps(value).encode(),
                          headers={'Content-Type': 'application/json', **(headers or {})})
        try:
            with urlopen(request, timeout=3) as response:
                return response.status, json.load(response)
        except HTTPError as error:
            return error.code, json.load(error)

    def test_static_pages_and_all_sprite_pairs(self):
        for path in ['/', '/avatar.html', '/style.css', '/catalog.json', '/app.js']:
            self.assertEqual(self.get(path)[0], 200)
        for hero in avatar_server.CATALOG['heroes']:
            self.assertEqual(self.get('/' + hero['idle'])[0], 200)
            self.assertEqual(self.get('/' + hero['talk'])[0], 200)

    def test_manual_selection_and_auto_mode_persist(self):
        self.assertEqual(self.post('/hero', {'hero': 'ashe'})[0], 200)
        state = json.loads(self.get('/state')[1])
        self.assertEqual((state['hero'], state['hero_mode']), ('ashe', 'manual'))
        self.assertEqual(self.post('/hero', {'hero': 'auto'})[0], 200)
        state = json.loads(self.get('/state')[1])
        self.assertEqual((state['hero'], state['hero_mode']), ('ashe', 'auto'))
        self.assertNotIn('controls', state)
        self.assertNotIn('input_status', state)

    def test_invalid_payloads_and_foreign_origins(self):
        for payload in [{'hero': '../../settings.json'}, {'hero': None}, {'hero': []}, []]:
            self.assertEqual(self.post('/hero', payload)[0], 400)
        self.assertEqual(self.post('/hero', {'hero': 'sigma'}, {'Origin': 'https://example.org'})[0], 403)
        self.assertEqual(self.post('/threshold', {'threshold': -30})[0], 404)
        self.assertEqual(self.post('/calibrate', {'hero': 'sigma', 'portrait': ''})[0], 400)
        self.assertEqual(self.post('/hero', {'hero': 'sigma'}, {'Origin': 'https://simplegp.github.io'})[0], 200)

    def test_private_files_and_parent_directories_are_not_served(self):
        for path in ['/settings.json', '/avatar_server.py', '/%2e%2e/settings.json', '/.git/config']:
            with self.assertRaises(HTTPError) as caught:
                self.get(path)
            self.assertEqual(caught.exception.code, 404)

    def test_explicit_ui_scan_waits_for_return_to_game(self):
        self.assertEqual(self.post('/scan', {})[0], 200)
        state = json.loads(self.get('/state')[1])
        self.assertEqual(state['hero_mode'], 'auto')
        self.assertIsNotNone(state['scan_request'])


if __name__ == '__main__':
    unittest.main()
