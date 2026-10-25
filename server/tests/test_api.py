import io
import json
import stat
import struct
import zipfile

import pytest
from fastapi.testclient import TestClient

from server.config import Settings
from server.main import create_app

PASSWORD = 'team-password'


def zip_bytes(files=None):
    out = io.BytesIO()
    with zipfile.ZipFile(out, 'w', compression=zipfile.ZIP_DEFLATED) as z:
        for name, value in (files if files is not None else {'README.md': 'A static challenge'}).items():
            z.writestr(name, value)
    return out.getvalue()


def docker_zip(root=''):
    return zip_bytes({f'{root}Dockerfile': 'FROM alpine\n', f'{root}dist/readme.txt': 'Player files', f'{root}src/main.py': 'print(42)'})


@pytest.fixture
def settings(tmp_path):
    return Settings(ctf_shared_password=PASSWORD, session_secret='x' * 48, data_dir=tmp_path)


@pytest.fixture
def app(settings):
    return create_app(settings)


@pytest.fixture
def client(app):
    with TestClient(app) as client:
        yield client


def login(client):
    response = client.post('/api/login', json={'password': PASSWORD})
    assert response.status_code == 200
    client.headers['X-CSRF-Token'] = response.json()['data']['csrf_token']
    return response


@pytest.fixture
def authed(client):
    login(client)
    return client


def upload(client, content=None, docker=False, name='Hidden evidence', category='forensics'):
    return client.post('/api/challenges', data={'name': name, 'description': '# Investigation\nFind the evidence.', 'flag': 'anything goes', 'category': category, 'requires_docker': str(docker).lower()}, files={'archive': ('challenge.zip', content if content is not None else zip_bytes(), 'application/zip')})


def metadata(**kwargs):
    return {'name': 'Updated challenge', 'description': 'New description', 'flag': 'new flag', 'category': 'web', 'requires_docker': False, **kwargs}


def test_successful_login_cookie_and_logout(client):
    response = login(client)
    cookie = response.headers['set-cookie'].lower()
    assert 'httponly' in cookie and 'samesite=lax' in cookie
    assert client.get('/api/me').json()['data']['authenticated']
    assert client.post('/api/logout').status_code == 200
    assert client.get('/api/me').status_code == 401


def test_wrong_password(client):
    assert client.post('/api/login', json={'password': 'wrong'}).status_code == 401


@pytest.mark.parametrize('method,path', [('get','/api/challenges'),('get','/api/challenges/1'),('post','/api/challenges'),('patch','/api/challenges/1'),('put','/api/challenges/1/archive'),('get','/api/challenges/1/download')])
def test_unauthorized(client, method, path):
    assert getattr(client, method)(path).status_code == 401


def test_csrf_and_origin_checks(authed):
    authed.headers.pop('X-CSRF-Token')
    assert authed.post('/api/logout').status_code == 403
    assert authed.post('/api/login', json={'password': PASSWORD}, headers={'Origin': 'https://evil.example'}).status_code == 403


@pytest.mark.parametrize('root', ['', 'enclosing-folder/'])
def test_valid_docker_upload(authed, settings, root):
    content = docker_zip(root)
    response = upload(authed, content, docker=True, category='osint')
    assert response.status_code == 201, response.text
    folder = next((settings.root / 'challenges').iterdir())
    assert (folder / 'original.zip').read_bytes() == content
    assert (folder / 'extracted' / root / 'Dockerfile').is_file()
    assert response.json()['data']['created_at'].endswith('Z')


def test_static_without_dist(authed):
    assert upload(authed).status_code == 201


@pytest.mark.parametrize('files', [{'dist/x': 'x'}, {'Dockerfile': 'FROM alpine'}])
def test_missing_docker_layout(authed, files):
    response = upload(authed, zip_bytes(files), docker=True)
    assert response.status_code == 422


def test_corrupted_zip(authed, settings):
    assert upload(authed, b'not a zip').status_code == 422
    assert list((settings.root / 'challenges').iterdir()) == []


@pytest.mark.parametrize('path', ['../escape', '/absolute', 'C:/windows', 'folder\\escape', 'x/../../escape', 'a/./b', 'x//file'])
def test_unsafe_paths(authed, path):
    assert upload(authed, zip_bytes({path: 'bad'})).status_code == 422


def test_symlink_and_special_file(authed):
    for mode in (stat.S_IFLNK, stat.S_IFIFO):
        output = io.BytesIO()
        with zipfile.ZipFile(output, 'w') as z:
            info = zipfile.ZipInfo('unsafe')
            info.create_system = 3
            info.external_attr = (mode | 0o777) << 16
            z.writestr(info, '/etc/passwd')
        assert upload(authed, output.getvalue()).status_code == 422


def test_encrypted_zip(authed):
    data = bytearray(zip_bytes())
    for signature, offset in ((b'PK\x03\x04', 6), (b'PK\x01\x02', 8)):
        index = data.index(signature) + offset
        struct.pack_into('<H', data, index, struct.unpack_from('<H', data, index)[0] | 1)
    assert upload(authed, bytes(data)).status_code == 422


def test_duplicate_and_conflicting_paths(authed):
    assert upload(authed, zip_bytes({'a': 'file', 'a/b': 'bad'})).status_code == 422
    assert upload(authed, zip_bytes({'A': 'file', 'a': 'duplicate'})).status_code == 422


def test_size_member_and_bomb_limits(settings):
    configurations = [({'max_upload_bytes': 30}, zip_bytes()), ({'max_file_bytes': 5}, zip_bytes()), ({'max_extracted_bytes': 5}, zip_bytes()), ({'max_zip_members': 1}, docker_zip()), ({'max_compression_ratio': 2}, zip_bytes({'bomb': '0' * 50000}))]
    for overrides, content in configurations:
        limited = create_app(settings.model_copy(update=overrides))
        with TestClient(limited) as c:
            login(c)
            assert upload(c, content).status_code in (413, 422)


def test_list_search_filter_stats_and_no_flag(authed):
    upload(authed, name='SQL injection', category='web')
    upload(authed, name='Hidden evidence', category='forensics')
    result = authed.get('/api/challenges').json()
    assert len(result['data']) == 2 and 'flag' not in result['data'][0]
    assert result['stats'] == {'total': 2, 'categories': 2, 'docker': 0, 'static': 2}
    assert len(authed.get('/api/challenges?category=web').json()['data']) == 1
    assert authed.get('/api/challenges?search=sQl').json()['data'][0]['name'] == 'SQL injection'
    assert authed.get('/api/challenges?search=%25').json()['data'] == []


def test_edit_metadata_preserves_archive(authed):
    original = zip_bytes()
    identifier = upload(authed, original).json()['data']['id']
    response = authed.patch(f'/api/challenges/{identifier}', json={'name': 'A new name', 'flag': 'new secret'})
    assert response.status_code == 200
    assert response.json()['data']['name'] == 'A new name'
    assert authed.get(f'/api/challenges/{identifier}').json()['data']['flag'] == 'new secret'
    assert authed.get(f'/api/challenges/{identifier}/download').content == original
    assert authed.patch(f'/api/challenges/{identifier}', json={'name': '  '}).status_code == 422
    assert authed.patch(f'/api/challenges/{identifier}', json={'requires_docker': None}).status_code == 422


def test_successful_replacement_and_atomic_metadata(authed, settings):
    identifier = upload(authed).json()['data']['id']
    replacement = docker_zip('root/')
    response = authed.put(f'/api/challenges/{identifier}/archive', data={'metadata': json.dumps(metadata(requires_docker=True))}, files={'archive': ('new.zip', replacement)})
    assert response.status_code == 200, response.text
    assert response.json()['data']['requires_docker'] is True
    assert authed.get(f'/api/challenges/{identifier}/download').content == replacement
    assert len(list((settings.root / 'challenges').iterdir())) == 1


def test_failed_replacement_preserves_original(authed, settings):
    original = docker_zip()
    identifier = upload(authed, original, docker=True).json()['data']['id']
    assert authed.put(f'/api/challenges/{identifier}/archive', files={'archive': ('bad.zip', zip_bytes())}).status_code == 422
    assert authed.get(f'/api/challenges/{identifier}/download').content == original
    assert len(list((settings.root / 'challenges').iterdir())) == 1


def test_download_original(authed):
    content = zip_bytes()
    identifier = upload(authed, content).json()['data']['id']
    response = authed.get(f'/api/challenges/{identifier}/download')
    assert response.status_code == 200 and response.content == content
    assert response.headers['content-type'] == 'application/zip'
    assert 'attachment' in response.headers['content-disposition']


def test_persistence_after_reconnect(authed, settings, app):
    identifier = upload(authed).json()['data']['id']
    app.state.engine.dispose()
    with TestClient(create_app(settings)) as restarted:
        login(restarted)
        assert restarted.get(f'/api/challenges/{identifier}').status_code == 200
        assert restarted.get(f'/api/challenges/{identifier}/download').content == zip_bytes()


def test_docker_requirement_changes(authed):
    identifier = upload(authed).json()['data']['id']
    assert authed.patch(f'/api/challenges/{identifier}', json={'requires_docker': True}).status_code == 422
    assert not authed.get(f'/api/challenges/{identifier}').json()['data']['requires_docker']
    compatible = upload(authed, docker_zip()).json()['data']['id']
    assert authed.patch(f'/api/challenges/{compatible}', json={'requires_docker': True}).status_code == 200


def test_missing_challenge_and_private_files(authed):
    assert authed.get('/api/challenges/9999').status_code == 404
    assert authed.get('/challenges/001_test/original.zip').status_code == 404


def test_failed_database_commit_cleans_upload(authed, app, settings, monkeypatch):
    from sqlalchemy.orm import Session
    def fail(self):
        raise RuntimeError('Simulated database failure')
    with monkeypatch.context() as m:
        m.setattr(Session, 'commit', fail)
        # TestClient re-raises server exceptions after the 500 handler by default.
        with pytest.raises(RuntimeError, match='Simulated'):
            upload(authed)
    assert list((settings.root / 'challenges').iterdir()) == []
    assert authed.get('/api/challenges').json()['data'] == []


def test_failed_replacement_commit_preserves_original(authed, settings, monkeypatch):
    from sqlalchemy.orm import Session
    original = zip_bytes()
    identifier = upload(authed, original).json()['data']['id']
    def fail(self):
        raise RuntimeError('Simulated database failure')
    with monkeypatch.context() as m:
        m.setattr(Session, 'commit', fail)
        with pytest.raises(RuntimeError, match='Simulated'):
            authed.put(f'/api/challenges/{identifier}/archive', files={'archive': ('new.zip', docker_zip())})
    assert authed.get(f'/api/challenges/{identifier}/download').content == original
    assert len(list((settings.root / 'challenges').iterdir())) == 1


def test_tampered_session_and_secure_cookie(settings):
    secure = create_app(settings.model_copy(update={'cookie_secure': True}))
    with TestClient(secure, base_url='https://testserver') as c:
        response = login(c)
        assert 'secure' in response.headers['set-cookie'].lower()
        c.cookies.clear()
        c.cookies.set('ctf_session', 'forged-session')
        assert c.get('/api/challenges').status_code == 401


def test_bad_replacement_metadata_and_filename(authed):
    identifier = upload(authed).json()['data']['id']
    for value in ('not-json', '[]', 'null', '{}'):
        response = authed.put(f'/api/challenges/{identifier}/archive', data={'metadata': value}, files={'archive': ('new.zip', zip_bytes())})
        assert response.status_code == 422, response.text
    assert authed.put(f'/api/challenges/{identifier}/archive', files={'archive': ('new.txt', zip_bytes())}).status_code == 422


def test_request_limit_with_and_without_content_length(settings):
    limited = create_app(settings.model_copy(update={'max_upload_bytes': 10}))
    with TestClient(limited) as c:
        payload = b'x' * (1024 * 1024 + 100)
        assert c.post('/api/login', content=payload, headers={'Content-Type':'application/json'}).status_code == 413
        def chunks():
            for start in range(0,len(payload),65536):
                yield payload[start:start+65536]
        response = c.post('/api/login', content=chunks(), headers={'Content-Type':'application/json'})
        assert response.status_code == 413, response.text


@pytest.mark.parametrize('filename', ['x' * 256, 'é' * 128])
def test_overlong_zip_path_component_is_validation_error(authed, settings, filename):
    response = upload(authed, zip_bytes({filename: 'data'}))
    assert response.status_code == 422
    assert list((settings.root / 'challenges').iterdir()) == []


def test_failed_folder_move_does_not_delete_existing_folder(authed, settings):
    folder = settings.root / 'challenges' / '001_hidden-evidence'
    folder.mkdir()
    sentinel = folder / 'existing.txt'
    sentinel.write_text('Keep existing files')
    with pytest.raises(OSError):
        upload(authed)
    assert sentinel.read_text() == 'Keep existing files'
    assert authed.get('/api/challenges').json()['data'] == []


@pytest.mark.parametrize('category', ['web','pwn','reverse-engineering','cryptography','forensics','osint','miscellaneous'])
def test_every_category_accepts_both_deployment_types(authed, category):
    assert upload(authed, category=category).status_code == 201
    assert upload(authed, docker_zip(), category=category, docker=True).status_code == 201
    assert len(authed.get(f'/api/challenges?category={category}').json()['data']) == 2


@pytest.mark.parametrize('config_name', ['Dockerfile','compose.yaml','compose.yml','docker-compose.yml','docker-compose.yaml'])
def test_all_docker_configuration_names_with_empty_dist(authed, config_name):
    assert upload(authed, zip_bytes({config_name:'configuration', 'dist/':''}), docker=True).status_code == 201


@pytest.mark.parametrize('field,value', [('name',' '),('description','\t\n'),('flag',''),('category','invalid'),('name','x'*201),('flag','x'*4097)])
def test_invalid_creation_metadata(authed, field, value):
    values = metadata()
    values[field] = value
    response = authed.post('/api/challenges', data=values, files={'archive':('valid.zip',zip_bytes())})
    assert response.status_code == 422
    assert 'error' in response.json()


def test_archive_crc_error_is_rejected(authed, settings):
    out = io.BytesIO()
    with zipfile.ZipFile(out, 'w', compression=zipfile.ZIP_STORED) as z:
        z.writestr('README', b'unique-content')
    damaged = out.getvalue().replace(b'unique-content', b'broken-content')
    assert upload(authed, damaged).status_code == 422
    assert list((settings.root / 'challenges').iterdir()) == []


def test_unknown_fields_and_null_metadata_rejected(authed):
    identifier = upload(authed).json()['data']['id']
    for patch in ({'folder_path':'../../bad'}, {'name':None}, {'category':None}):
        assert authed.patch(f'/api/challenges/{identifier}', json=patch).status_code == 422


def test_concurrent_uploads_use_unique_ids(app, settings):
    from concurrent.futures import ThreadPoolExecutor
    def create(index):
        with TestClient(app) as c:
            login(c)
            response = upload(c, name=f'Concurrent {index}')
            assert response.status_code == 201, response.text
            return response.json()['data']['id']
    with ThreadPoolExecutor(max_workers=4) as pool:
        ids = list(pool.map(create, range(12)))
    assert len(set(ids)) == 12
    assert len(list((settings.root / 'challenges').iterdir())) == 12


def test_error_response_hides_internal_traceback(app, monkeypatch):
    from sqlalchemy.orm import Session
    def fail(self):
        raise RuntimeError('private internal detail')
    with TestClient(app, raise_server_exceptions=False) as c:
        login(c)
        with monkeypatch.context() as m:
            m.setattr(Session, 'commit', fail)
            response = upload(c)
        assert response.status_code == 500
        assert response.json() == {'error':{'message':'The server could not complete this operation.'}}
        assert 'private internal detail' not in response.text
