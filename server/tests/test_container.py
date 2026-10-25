import stat

import pytest
from dotenv import dotenv_values

from server.container import prepare_settings


@pytest.fixture
def container_environment(tmp_path, monkeypatch):
    monkeypatch.setenv('DATA_DIR', str(tmp_path))
    monkeypatch.delenv('CTF_SHARED_PASSWORD', raising=False)
    monkeypatch.delenv('SESSION_SECRET', raising=False)
    # Local developer configuration should not influence isolated bootstrap tests.
    import server.container
    monkeypatch.setattr(server.container, 'BASE_DIR', tmp_path / 'source')
    return tmp_path


def test_first_start_generates_private_persistent_credentials(container_environment, capsys):
    first = prepare_settings()
    path = container_environment / '.env'
    stored = dotenv_values(path)
    assert stored['CTF_SHARED_PASSWORD'] == first.ctf_shared_password
    assert stored['SESSION_SECRET'] == first.session_secret
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    assert first.ctf_shared_password in capsys.readouterr().out
    second = prepare_settings()
    assert second.ctf_shared_password == first.ctf_shared_password
    assert second.session_secret == first.session_secret
    assert capsys.readouterr().out == ''


def test_explicit_container_credentials_take_precedence(container_environment, monkeypatch, capsys):
    monkeypatch.setenv('CTF_SHARED_PASSWORD', 'configured-password')
    monkeypatch.setenv('SESSION_SECRET', 's' * 48)
    settings = prepare_settings()
    assert settings.ctf_shared_password == 'configured-password'
    assert settings.session_secret == 's' * 48
    assert 'configured-password' not in capsys.readouterr().out


def test_invalid_configuration_is_not_saved(container_environment, monkeypatch):
    from pydantic import ValidationError
    monkeypatch.setenv('CTF_SHARED_PASSWORD', '')
    with pytest.raises(ValidationError):
        prepare_settings()
    assert not (container_environment / '.env').exists()


def test_health_checks_database_without_private_data(container_environment):
    from fastapi.testclient import TestClient
    from server.main import create_app
    with TestClient(create_app(prepare_settings())) as client:
        response = client.get('/api/health')
    assert response.status_code == 200
    assert response.json() == {'data': {'status': 'ok'}}


def test_explicit_credentials_are_retained_after_override_is_removed(container_environment, monkeypatch):
    prepare_settings()
    monkeypatch.setenv('CTF_SHARED_PASSWORD', 'replacement-password')
    monkeypatch.setenv('SESSION_SECRET', 's' * 48)
    prepare_settings()
    monkeypatch.delenv('CTF_SHARED_PASSWORD')
    monkeypatch.delenv('SESSION_SECRET')
    settings = prepare_settings()
    assert settings.ctf_shared_password == 'replacement-password'
    assert settings.session_secret == 's' * 48
    assert not list(container_environment.glob('.credentials-*'))
