import secrets
from fastapi import HTTPException, Request

def authenticated(request: Request):
    if not request.session.get('authenticated'):
        raise HTTPException(401, 'Please log in to continue.')
    if request.method not in ('GET', 'HEAD', 'OPTIONS'):
        token = request.headers.get('x-csrf-token', '')
        if not token or not secrets.compare_digest(token.encode(), request.session.get('csrf_token', '').encode()):
            raise HTTPException(403, 'Your session verification failed. Refresh and try again.')

class RequestLimit:
    """Bound the whole multipart body, including requests without Content-Length."""
    def __init__(self, app, limit):
        self.app, self.limit = app, limit
    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http':
            return await self.app(scope, receive, send)
        from starlette.responses import JSONResponse
        from starlette.exceptions import HTTPException as StarletteHTTPException
        total = 0
        async def bounded_receive():
            nonlocal total
            message = await receive()
            total += len(message.get('body', b''))
            if total > self.limit:
                raise StarletteHTTPException(413, 'Upload exceeds the configured request limit.')
            return message
        headers = dict(scope['headers'])
        try:
            length = int(headers.get(b'content-length', b'0'))
        except ValueError:
            length = self.limit + 1
        if length > self.limit:
            return await JSONResponse({'error': {'message': 'Upload exceeds the configured request limit.'}}, status_code=413)(scope, receive, send)
        await self.app(scope, bounded_receive, send)
