"""Pruebas sin red ni cuentas reales."""
import hashlib
import base64
import tempfile
import json
import records.online as online_module
from pathlib import Path
from urllib.parse import parse_qs, urlsplit
from records.online import Online, protect, SUPABASE, publication_payload


def main():
    raw = b'fixture-session-never-uploaded'
    encrypted = protect(raw)
    assert raw not in encrypted
    assert protect(encrypted, decrypt=True) == raw
    with tempfile.TemporaryDirectory() as directory:
        client = Online(Path(directory))
        client.key = 'sb_publishable_fixture'
        url = client.start('http://127.0.0.1:54321')
        query = parse_qs(urlsplit(url).query)
        assert url.startswith(SUPABASE + '/auth/v1/authorize?')
        assert query['provider'] == ['discord']
        nonce, verifier, _ = client.pending
        expected = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b'=').decode()
        assert query['code_challenge'] == [expected]
        assert verifier not in url
        try:
            client.callback('wrong-nonce', 'code')
        except ValueError:
            pass
        else:
            raise AssertionError('Callback ajeno aceptado')
        client.save({'access_token':'fixture-a','refresh_token':'fixture-r','expires_in':3600,
                     'provider_token':'must-not-be-stored','user':{'identities':[{'provider':'discord'}],
                     'user_metadata':{'preferred_username':'Piloto prueba'}}})
        assert 'provider_token' not in client.session
        assert Online(Path(directory)).status()['name'] == 'Piloto prueba'
        assert client.access_token() == 'fixture-a'
        previous_request = online_module.request_json
        calls = []
        def profile_request(url, data=None, headers=None):
            calls.append((url, data))
            return {'name':'Piloto Permanente','name_chosen':True}
        try:
            online_module.request_json = profile_request
            assert client.account('Piloto Permanente')['name_chosen']
            assert client.status()['name'] == 'Piloto Permanente'
            assert client.account()['name'] == 'Piloto Permanente'
            assert calls[0][1] == {'name':'Piloto Permanente'} and calls[1][1] is None
        finally:
            online_module.request_json = previous_request
        client.logout()
        assert not client.path.exists() and not client.status()['signed_in']
        path = Path(directory) / 'attempt.json'
        attempt = {'start_observed': True, 'capture_status':'closed','trace_file':'attempt.jsonl',
                   'stage_game_id':'WrcgGrSS3Full','raw_time_ms':10000,'penalty_ms':33000,
                   'save_evidence':{'result_id':'a'*64,'car_game_id':'TestCar'}}
        path.write_text(json.dumps(attempt))
        samples=[{'elapsed_s':i/5,'clock_ms':i*200,'distance_m':i*2,'xyz_m':[i*2,0,0],
                  'speed_kmh':36,'player':'private-name','graphics_base64':'private-debug'} for i in range(51)]
        (Path(directory)/'attempt.jsonl').write_text('\n'.join(json.dumps(sample) for sample in samples))
        payload = publication_payload(path)
        assert len(payload['points']) == 11 and payload['points'][-1][1] == 10000
        assert 'private' not in json.dumps(payload) and payload['penalty_ms'] == 33000
        attempt['start_observed'] = None
        path.write_text(json.dumps(attempt))
        try:
            publication_payload(path)
        except ValueError:
            pass
        else:
            raise AssertionError('Captura histórica sin inicio habilitada')
    print('PASS: DPAPI, PKCE, callback ajeno, sesión persistente y cierre local')
