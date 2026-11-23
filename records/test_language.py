"""Language persistence and private HTTP boundary; interpreted only, no release build."""
import http.client
import json
from pathlib import Path
import tempfile
import threading
from records.app import Engine, AppServer


def main():
    with tempfile.TemporaryDirectory() as directory:
        data = Path(directory)
        engine = Engine(data, monitor=False)
        assert engine.state()['language'] == 'en'
        engine.set_auto(False)
        engine.set_language('es')
        restored = Engine(data, monitor=False)
        assert restored.state()['language'] == 'es'
        assert restored.settings['auto_capture'] is False
        for invalid in ('fr', None, {}, 42):
            try:
                engine.set_language(invalid)
            except ValueError:
                pass
            else:
                raise AssertionError('Invalid language accepted')
        server = AppServer(('127.0.0.1', 0), engine)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        def request(method, path, body=None, headers=None):
            connection = http.client.HTTPConnection('127.0.0.1', server.server_port)
            try:
                connection.request(method, path, body, headers or {})
                response = connection.getresponse()
                return response.status, response.read()
            finally:
                connection.close()
        try:
            headers = {'X-App-Token': server.token, 'Origin': server.origin, 'Content-Type': 'application/json'}
            assert request('POST', '/api/language', '{"language":"en"}')[0] == 403
            assert request('POST', '/api/language', '{"language":"fr"}', headers)[0] == 400
            assert request('POST', '/api/language', '{"language":"en"}', headers)[0] == 200
            assert engine.state()['language'] == 'en'
            status, content = request('GET', '/i18n.js')
            assert status == 200 and b'AppI18n' in content
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=3)
    print('PASS: English default, Spanish persistence, capture preference preserved, invalid language rejected and private HTTP endpoint')


if __name__ == '__main__':
    main()
