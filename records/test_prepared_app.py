"""Interpreted checks for the private, cached leaderboard bridge; no desktop build."""
import http.client
import json
from pathlib import Path
import tempfile
import threading
from records import app as app_module
from records.app import Engine, AppServer


def main():
    with tempfile.TemporaryDirectory() as directory:
        engine = Engine(Path(directory), monitor=False)
        server = AppServer(('127.0.0.1', 0), engine)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        def get(path, authorized=True):
            connection = http.client.HTTPConnection('127.0.0.1', server.server_port)
            try:
                connection.request('GET', path, headers={'X-App-Token': server.token} if authorized else {})
                response = connection.getresponse()
                return response.status, response.read()
            finally:
                connection.close()
        original_request = app_module.request_json
        calls = []
        def fake_request(url):
            calls.append(url)
            return {'records': []}
        app_module.request_json = fake_request
        try:
            assert get('/api/leaderboard?stage=WrcgEsSS4Full', False)[0] == 403
            assert get('/api/leaderboard?stage=https://invalid.test')[0] == 400
            assert get('/api/leaderboard?stage=WrcgEsSS4Full')[0] == 200
            assert json.loads(get('/api/leaderboard?stage=WrcgEsSS4Full')[1]) == {'records': []}
            assert len(calls) == 1
            assert calls[0] == 'https://acrsplits.online/api/leaderboard?stage=WrcgEsSS4Full'
            get('/api/leaderboard?stage=WrcgKeSS2Full')
            assert len(calls) == 2
            def offline(url):
                raise ValueError('Offline')
            app_module.request_json = offline
            assert get('/api/leaderboard?stage=WrcgGrSS3Full')[0] == 502
            assert get('/flags/es.svg')[0] == 200
            assert get('/flags/../../session.bin')[0] == 404
            source = (Path(__file__).parent / 'ui/app.js').read_text(encoding='utf-8')
            assert 'const EXPORT_ENABLED=false;' in source
            assert 'if(!EXPORT_ENABLED)return;' in source
        finally:
            app_module.request_json = original_request
            server.shutdown()
            server.server_close()
            thread.join(timeout=3)
    print('PASS: private leaderboard, fixed host, 60s cache, safe flags and disabled export')


if __name__ == '__main__':
    main()
