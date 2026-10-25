import json
import logging
import secrets
import tempfile
from contextlib import asynccontextmanager
from pathlib import Path
from threading import RLock
from typing import Annotated
from fastapi import FastAPI, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from sqlalchemy import select
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.sessions import SessionMiddleware
from . import crud
from .archive import validate_extract
from .auth import authenticated, RequestLimit
from .config import Settings
from .database import Base, connect
from .models import Challenge
from .schemas import Category, Detail, Login, Metadata, MetadataPatch, Summary, Envelope, SessionInfo, ChallengeList

logger = logging.getLogger(__name__)

def create_app(settings=None):
    settings = settings or Settings()
    storage = settings.root / 'challenges'
    storage.mkdir(parents=True, exist_ok=True)
    engine, session_factory = connect(settings.root)
    Base.metadata.create_all(engine)
    mutation_lock = RLock()
    @asynccontextmanager
    async def lifespan(app):
        yield
        engine.dispose()
    app = FastAPI(title='ACM CTF Track Challenge Tool', lifespan=lifespan)
    app.state.session_factory = session_factory
    app.state.engine = engine
    app.add_middleware(RequestLimit, limit=settings.max_upload_bytes + 1024 * 1024)
    app.add_middleware(SessionMiddleware, secret_key=settings.session_secret, session_cookie='ctf_session',
                       same_site='lax', https_only=settings.cookie_secure, max_age=settings.session_max_age)

    @app.middleware('http')
    async def security(request, call_next):
        if request.method not in ('GET', 'HEAD', 'OPTIONS'):
            origin = request.headers.get('origin')
            if origin and origin not in settings.allowed_origins.split(','):
                return JSONResponse({'error': {'message': 'Request origin is not allowed.'}}, status_code=403)
        response = await call_next(request)
        response.headers['Cache-Control'] = 'no-store'
        response.headers['X-Content-Type-Options'] = 'nosniff'
        return response

    @app.exception_handler(StarletteHTTPException)
    async def http_error(request, exc):
        return JSONResponse({'error': {'message': str(exc.detail)}}, status_code=exc.status_code)

    @app.exception_handler(RequestValidationError)
    async def validation_error(request, exc):
        messages = ['.'.join(str(v) for v in e['loc'][1:]) + ': ' + e['msg'] for e in exc.errors()]
        return JSONResponse({'error': {'message': '; '.join(messages)}}, status_code=422)

    @app.exception_handler(Exception)
    async def unexpected_error(request, exc):
        logger.exception('Request failed')
        return JSONResponse({'error': {'message': 'The server could not complete this operation.'}}, status_code=500)

    def db_session():
        with session_factory() as db:
            yield db
    DB = Annotated[object, Depends(db_session)]
    private = [Depends(authenticated)]

    def parse_metadata(values):
        try:
            return Metadata.model_validate(values)
        except ValidationError as exc:
            raise HTTPException(422, '; '.join(f'{".".join(str(v) for v in e["loc"]) or "metadata"}: {e["msg"]}' for e in exc.errors())) from exc

    def stage(upload, directory, docker):
        filename = Path((upload.filename or '').replace('\\', '/')).name
        if not filename.lower().endswith('.zip') or len(filename) > 255 or any(ord(c) < 32 for c in filename):
            raise HTTPException(422, 'Choose a .zip file with a valid filename.')
        archive = directory / 'original.zip'
        size = 0
        with archive.open('wb') as out:
            while chunk := upload.file.read(64 * 1024):
                size += len(chunk)
                if size > settings.max_upload_bytes:
                    raise HTTPException(413, 'ZIP exceeds the configured upload size limit.')
                out.write(chunk)
        (directory / 'extracted').mkdir()
        validate_extract(archive, directory / 'extracted', docker, settings)
        return filename

    @app.get('/api/health')
    def health(db: DB):
        from sqlalchemy import text
        db.execute(text('SELECT 1'))
        return {'data': {'status': 'ok'}}

    @app.post('/api/login', response_model=Envelope[SessionInfo], response_model_exclude_none=True)
    def login(body: Login, request: Request):
        if not secrets.compare_digest(body.password.encode(), settings.ctf_shared_password.encode()):
            raise HTTPException(401, 'Incorrect password. Please try again.')
        request.session.clear()
        request.session.update(authenticated=True, csrf_token=secrets.token_urlsafe(32))
        return {'data': {'authenticated': True, 'csrf_token': request.session['csrf_token']}}

    @app.get('/api/me', dependencies=private, response_model=Envelope[SessionInfo])
    def me(request: Request):
        return {'data': {'authenticated': True, 'csrf_token': request.session['csrf_token']}}

    @app.post('/api/logout', dependencies=private, response_model=Envelope[SessionInfo], response_model_exclude_none=True)
    def logout(request: Request):
        request.session.clear()
        return {'data': {'authenticated': False}}

    @app.get('/api/challenges', dependencies=private, response_model=ChallengeList)
    def listing(db: DB, category: Category | None = None, search: str = ''):
        records = crud.list_challenges(db, category, search)
        all_records = db.scalars(select(Challenge)).all()
        return {'data': [Summary.model_validate(row).model_dump(mode='json') for row in records], 'stats': {
            'total': len(all_records), 'categories': len({c.category for c in all_records}),
            'docker': sum(c.requires_docker for c in all_records), 'static': sum(not c.requires_docker for c in all_records)}}

    @app.get('/api/challenges/{challenge_id}', dependencies=private, response_model=Envelope[Detail])
    def detail(challenge_id: int, db: DB):
        return {'data': Detail.model_validate(crud.get(db, challenge_id))}

    @app.post('/api/challenges', status_code=201, dependencies=private, response_model=Envelope[Detail])
    def submit(db: DB, name: Annotated[str, Form()], description: Annotated[str, Form()],
               flag: Annotated[str, Form()], category: Annotated[str, Form()],
               requires_docker: Annotated[bool, Form()], archive: Annotated[UploadFile, File()]):
        metadata = parse_metadata(dict(name=name, description=description, flag=flag, category=category, requires_docker=requires_docker))
        with tempfile.TemporaryDirectory(prefix='.upload-', dir=storage) as temp:
            staged = Path(temp) / 'payload'
            staged.mkdir()
            filename = stage(archive, staged, requires_docker)
            with mutation_lock:
                challenge = crud.create(db, metadata, filename, staged, storage)
        return {'data': Detail.model_validate(challenge)}

    @app.patch('/api/challenges/{challenge_id}', dependencies=private, response_model=Envelope[Detail])
    def edit(challenge_id: int, body: MetadataPatch, db: DB):
        with mutation_lock:
            challenge = crud.get(db, challenge_id)
            values = {key: getattr(challenge, key) for key in Metadata.model_fields}
            values.update(body.model_dump(exclude_unset=True))
            metadata = parse_metadata(values)
            if metadata.requires_docker != challenge.requires_docker:
                validate_extract(storage / challenge.folder_path / 'original.zip', None, metadata.requires_docker, settings)
            return {'data': Detail.model_validate(crud.update(db, challenge, metadata))}

    @app.put('/api/challenges/{challenge_id}/archive', dependencies=private, response_model=Envelope[Detail])
    def replace(challenge_id: int, db: DB, archive: Annotated[UploadFile, File()], metadata: Annotated[str | None, Form()] = None):
        with mutation_lock:
            challenge = crud.get(db, challenge_id)
            values = {key: getattr(challenge, key) for key in Metadata.model_fields}
            if metadata is not None:
                try:
                    values = json.loads(metadata)
                except ValueError as exc:
                    raise HTTPException(422, 'Metadata must be valid JSON.') from exc
            parsed = parse_metadata(values)
            with tempfile.TemporaryDirectory(prefix='.upload-', dir=storage) as temp:
                staged = Path(temp) / 'payload'
                staged.mkdir()
                filename = stage(archive, staged, parsed.requires_docker)
                challenge = crud.replace(db, challenge, parsed, filename, staged, storage)
            return {'data': Detail.model_validate(challenge)}

    @app.get('/api/challenges/{challenge_id}/download', dependencies=private)
    def download(challenge_id: int, db: DB):
        with mutation_lock:
            challenge = crud.get(db, challenge_id)
            path = storage / challenge.folder_path / 'original.zip'
            if not path.is_file():
                raise HTTPException(404, 'The stored archive is missing.')
            # Open before releasing the lock so a concurrent replacement cannot remove it.
            from starlette.responses import StreamingResponse
            stream = path.open('rb')
            from urllib.parse import quote
            def chunks():
                try:
                    while chunk := stream.read(64 * 1024):
                        yield chunk
                finally:
                    stream.close()
            return StreamingResponse(chunks(), media_type='application/zip', headers={
                'Content-Disposition': f"attachment; filename*=UTF-8''{quote(challenge.original_filename)}",
                'Content-Length': str(path.stat().st_size)})
    return app
