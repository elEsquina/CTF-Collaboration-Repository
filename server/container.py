"""One-process container startup with credentials retained alongside the database."""
import os
import secrets
import tempfile
from pathlib import Path

import uvicorn
from dotenv import dotenv_values

from .config import BASE_DIR, Settings
from .main import create_app


def prepare_settings():
    root = Path(os.environ.get('DATA_DIR', '/data')).resolve()
    root.mkdir(parents=True, exist_ok=True)
    credentials_path = root / '.env'
    persisted = dotenv_values(credentials_path) if credentials_path.exists() else {}
    configured = dotenv_values(BASE_DIR / '.env')
    values = {}
    generated_password = False
    for key in ('CTF_SHARED_PASSWORD', 'SESSION_SECRET'):
        value = os.environ.get(key, configured.get(key) or persisted.get(key))
        if value is None:
            value = secrets.token_urlsafe(18) if key == 'CTF_SHARED_PASSWORD' else secrets.token_hex(32)
            generated_password |= key == 'CTF_SHARED_PASSWORD'
        values[key] = value
    # Validate before writing anything; explicit empty/invalid settings fail clearly.
    settings = Settings(data_dir=root, ctf_shared_password=values['CTF_SHARED_PASSWORD'],
                        session_secret=values['SESSION_SECRET'])
    if any(persisted.get(key) != value for key, value in values.items()):
        import json
        temporary_path = None
        try:
            with tempfile.NamedTemporaryFile(mode='w', dir=root, prefix='.credentials-', delete=False) as output:
                temporary_path = Path(output.name)
                for key, value in values.items():
                    output.write(f'{key}={json.dumps(value)}\n')
            temporary_path.replace(credentials_path)
        finally:
            if temporary_path:
                temporary_path.unlink(missing_ok=True)
    if generated_password:
        print(f'First-start shared password: {values["CTF_SHARED_PASSWORD"]}', flush=True)
        print('Credentials saved in the repository-data volume.', flush=True)
    return settings


def main():
    settings = prepare_settings()
    uvicorn.run(create_app(settings), host='0.0.0.0', port=8000, workers=1)


if __name__ == '__main__':
    main()
