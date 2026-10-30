"""Bounded HTTP ingress, authenticated roles, request receipts and safe JSON errors."""
import asyncio
import hashlib
import json
import logging
import os
import re
import time
import uuid
from collections import OrderedDict, deque
from urllib.parse import urlsplit

from starlette.requests import Request
from starlette.responses import JSONResponse

from .platform import PlatformStore, allowed, authenticate, data_dir, enterprise

MAX_BODY = 2 * 1024 * 1024
LOG = logging.getLogger('jitd.requests')


class Boundary:
    def __init__(self, app):
        self.app = app
        self.hits = OrderedDict()

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http':
            return await self.app(scope, receive, send)
        request = Request(scope)
        path, method = request.url.path, request.method
        rid = uuid.uuid4().hex
        started = time.monotonic()
        principal = {'name': 'local', 'role': 'admin'}
        scope.setdefault('state', {})['principal'] = principal

        async def reject(status, message, **headers):
            LOG.warning('request_refused request_id=%s actor=%s method=%s path=%s status=%s', rid, (principal or {}).get('name','anonymous'), method, path, status)
            response = JSONResponse({'error': {'code': 'request_refused', 'message': message}, 'request_id': rid}, status_code=status,
                                    headers={'X-Request-ID': rid, 'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff', **headers})
            await response(scope, receive, send)

        if enterprise() and path != '/api/health':
            hosts = {h.strip().lower() for h in os.getenv('JITD_ALLOWED_HOSTS', 'localhost,127.0.0.1').split(',')}
            if request.url.hostname not in hosts:
                return await reject(400, 'Host is not allowed')
            peer = scope.get('client') or ('unknown', 0)
            key = peer[0]
            now = time.monotonic()
            q = self.hits.setdefault(key, deque())
            while q and now - q[0] > 60:
                q.popleft()
            # Bound anonymous work before expensive password verification. No forwarded-IP trust.
            if len(q) >= 180:
                return await reject(429, 'Request rate exceeded', **{'Retry-After': '60'})
            q.append(now)
            self.hits.move_to_end(key)
            while len(self.hits) > 2048:
                self.hits.popitem(last=False)
            principal = await asyncio.to_thread(authenticate, request.headers.get('authorization', ''))
            if principal is None:
                return await reject(401, 'Workspace credentials required', **{'WWW-Authenticate': 'Basic realm="JIT-D", charset="UTF-8"'})
            scope['state']['principal'] = principal
            if not allowed(principal['role'], method, path):
                return await reject(403, 'Role cannot perform this action. Repairs require a proposal and reviewer decision.')

        mutation = method in ('POST', 'PUT', 'PATCH', 'DELETE')
        raw = bytearray()
        if mutation:
            origin = request.headers.get('origin')
            try:
                def host_port(value):
                    u = urlsplit(value)
                    if u.scheme not in ('http', 'https') or u.username or u.password or u.path not in ('', '/') or u.query or u.fragment:
                        return None
                    return u.hostname, None if u.port in (None, 80, 443) else u.port
                if origin and (host_port(origin) is None or host_port(origin) != host_port(str(request.base_url))):
                    return await reject(403, 'Cross-origin mutation refused')
                length = request.headers.get('content-length')
                if length and (int(length) < 0 or int(length) > MAX_BODY):
                    return await reject(413, 'Request exceeds 2 MiB')
            except ValueError:
                return await reject(400, 'Invalid request headers')
            while True:
                try:
                    message = await asyncio.wait_for(receive(), timeout=15)
                except asyncio.TimeoutError:
                    return await reject(408, 'Request body timed out')
                if message['type'] == 'http.disconnect':
                    return
                raw.extend(message.get('body', b''))
                if len(raw) > MAX_BODY:
                    return await reject(413, 'Request exceeds 2 MiB')
                if not message.get('more_body', False):
                    break
        delivered = False

        async def bounded_receive():
            nonlocal delivered
            if mutation and not delivered:
                delivered = True
                return {'type': 'http.request', 'body': bytes(raw), 'more_body': False}
            return await receive()

        store = PlatformStore(data_dir()) if mutation or enterprise() and path.startswith('/api/') else None
        if enterprise() and mutation and not store.verify()['valid']:
            return await reject(503, 'Audit integrity check failed; administrator investigation required')
        execution_path = bool(re.fullmatch(r'/api/hybrid/runs/[a-z0-9_]+/assist',path)) or path in ('/api/canvas/architect','/api/canvas/baseline') or bool(re.fullmatch(r'/api/canvas/versions/version_[a-f0-9]{16}/executions', path)) or path == '/api/executions' or bool(re.fullmatch(r'/api/studio/versions/version_[a-f0-9]{16}/executions', path))
        idem = request.headers.get('idempotency-key') if execution_path and method == 'POST' else None
        if enterprise() and execution_path and method == 'POST' and not idem:
            return await reject(400, 'Idempotency-Key is required for execution')
        if idem:
            if not re.fullmatch(r'[A-Za-z0-9_.:-]{8,128}', idem):
                return await reject(400, 'Idempotency-Key must contain 8–128 safe characters')
            fingerprint = hashlib.sha256(method.encode() + path.encode() + bytes(raw)).hexdigest()
            state, saved = store.claim(principal['name'], idem, fingerprint)
            if state == 'replay':
                return await JSONResponse(saved['body'], status_code=saved['status'], headers={'X-Request-ID': rid, 'Idempotency-Replayed': 'true', 'Cache-Control': 'no-store'})(scope, receive, send)
            if state != 'new':
                return await reject(409, 'Idempotency key is in progress or belongs to different input; inspect execution history before retrying')
        if store and mutation:
            store.event(action='request_started', request_id=rid, actor=principal['name'], role=principal['role'], method=method, path=path)
        status, body = 500, bytearray()
        response_started = False

        async def wrapped_send(message):
            nonlocal status, response_started
            if message['type'] == 'http.response.start':
                response_started = True
                status = message['status']
                headers = [(k,v) for k,v in message.get('headers', []) if k.lower() not in (b'cache-control', b'x-request-id')]
                headers.extend([(b'x-request-id', rid.encode()), (b'cache-control', b'no-store')])
                message = {**message, 'headers': headers}
            if idem and message['type'] == 'http.response.body':
                body.extend(message.get('body', b''))
            await send(message)
        try:
            await self.app(scope, bounded_receive, wrapped_send)
        except Exception as exc:
            LOG.error('request_failed request_id=%s error_type=%s', rid, type(exc).__name__)
            if not response_started:
                await reject(500, 'Internal operation failed; use the request ID to investigate')
            status = 500
        finally:
            if store and mutation:
                store.event(action='request_finished', request_id=rid, actor=principal['name'], role=principal['role'], method=method,
                            path=path, status=status, duration_ms=round((time.monotonic()-started)*1000, 2))
            if idem and response_started:
                try:
                    store.complete_request(principal['name'], idem, status, json.loads(body))
                except (ValueError, UnicodeError):
                    pass  # retain in-progress reservation; never repeat uncertain side effects
            LOG.info('request request_id=%s actor=%s method=%s path=%s status=%s duration_ms=%.2f', rid, principal['name'], method, path, status, (time.monotonic()-started)*1000)
