"""JIT-D API. uvicorn jitd.server:app --port 8000

The Nebius key stays in this process. Every endpoint triggers real backend behaviour; the UI animates nothing by itself.
"""
from __future__ import annotations

import asyncio
import json
import os
import re
import threading
import time
from collections import deque
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import RELEASE_VERSION, SUITE_VERSION, llm as llm_mod
from .bench import DEFINITIONS, summary_csv
from .lab import Lab, LabError
from .scenarios import SCENARIOS
from .schemas import SchemaError

ROOT = Path(__file__).resolve().parent.parent
RESULTS = ROOT / "benchmark" / "results" / "runs"
ID_RE = re.compile(r"^[A-Za-z0-9_.-]{1,80}$")
RATE = (90, 60.0)

from contextlib import asynccontextmanager
from .platform import PlatformStore, data_dir, enterprise, validate_runtime
from .admin import exclusive
from .boundary import Boundary

validate_runtime()

@asynccontextmanager
async def lifespan(app):
    validate_runtime()
    with exclusive(data_dir()):
        global LAB
        if enterprise():
            LAB = _new_lab()
        chain = PlatformStore(LAB.dir).verify()
        if not chain['valid']:
            raise RuntimeError('Security audit chain failed verification; investigate before startup')
        yield

app = FastAPI(title="JIT-D", version=RELEASE_VERSION, lifespan=lifespan)
def _new_lab():
    return Lab(llm_factory=(lambda meter: llm_mod.NebiusClient(meter)) if llm_mod.available() else None)

LAB = None if enterprise() else _new_lab()
_hits: dict[str, deque] = {}
_lock = threading.Lock()


@app.middleware("http")
async def workspace_access(request: Request, call_next):
    import base64
    import hmac
    from urllib.parse import urlsplit
    token = '' if enterprise() else os.getenv('JITD_ACCESS_TOKEN', '')
    public_health = request.url.path == '/api/health'
    if not enterprise() and os.getenv('JITD_REQUIRE_AUTH') == '1' and not token and not public_health:
        return JSONResponse({'error': 'Hosted access token is not configured'}, status_code=503)
    if token and not public_health:
        try:
            scheme, encoded = request.headers.get('authorization', '').split(' ', 1)
            username, password = base64.b64decode(encoded, validate=True).decode().split(':', 1)
            valid = scheme.lower() == 'basic' and hmac.compare_digest(username.encode(), b'jitd') and hmac.compare_digest(password.encode(), token.encode())
        except (ValueError, UnicodeError):
            valid = False
        if not valid:
            if 'text/html' in request.headers.get('accept', '') and not request.url.path.startswith('/api/'):
                return FileResponse(ROOT / 'web' / '401.html', status_code=401,
                                    headers={'WWW-Authenticate': 'Basic realm="JIT-D", charset="UTF-8"', 'Cache-Control': 'no-store'})
            return JSONResponse({'error': 'Workspace authentication required'}, status_code=401,
                                headers={'WWW-Authenticate': 'Basic realm="JIT-D", charset="UTF-8"'})
    if request.method in ('POST', 'PUT', 'DELETE', 'PATCH'):
        origin = request.headers.get('origin')
        def host_port(value):
            parsed = urlsplit(value)
            if parsed.scheme not in ('http', 'https') or parsed.username or parsed.password or parsed.path not in ('', '/') or parsed.query or parsed.fragment:
                return None
            port = parsed.port
            return (parsed.hostname, None if port in (None, 80, 443) else port)
        try:
            same_host = host_port(origin) == host_port(str(request.base_url)) if origin else True
        except ValueError:
            same_host = False
        if origin and not same_host:
            return JSONResponse({'error': 'Cross-origin mutation refused'}, status_code=403)
    response = await call_next(request)
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['Referrer-Policy'] = 'same-origin'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['Content-Security-Policy'] = "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; font-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
    if token and not public_health:
        response.headers['Cache-Control'] = 'no-store'
    return response


@app.exception_handler(LabError)
async def lab_error(_, e: LabError):
    return JSONResponse({"error": {"code": e.code, "message": e.message}}, status_code=e.status)


def limit(request: Request):
    import hashlib
    identity = request.headers.get("authorization")
    ip = "credential:" + hashlib.sha256(identity.encode()).hexdigest() if identity else request.client.host if request.client else "?"
    now = time.monotonic()
    with _lock:
        q = _hits.setdefault(ip, deque())
        while q and now - q[0] > RATE[1]:
            q.popleft()
        if len(q) >= RATE[0]:
            raise HTTPException(429, "rate limit exceeded", headers={"Retry-After": "10"})
        q.append(now)


def _rid(x: str) -> str:
    if not ID_RE.match(x):
        raise HTTPException(400, "bad id")
    return x


@app.get("/api/health")
def health():
    return {"status": "ok", "version": SUITE_VERSION, "release": RELEASE_VERSION}


@app.get("/api/meta")
def meta():
    live = llm_mod.available()
    return {"version": SUITE_VERSION, "mode": "MODEL CONFIGURED" if live else "SIMULATED SERVICES", "model": os.getenv("NEBIUS_MODEL_ID") if live else None,
            "model_configured": live, "host_mode": os.getenv("JITD_HOST_MODE", "single_process"), "model_call_budget": llm_mod.budget(), "scenarios": [{"id": s.id, "title": s.title, "kind": s.kind, "split": s.split, "desc": s.desc, "repairable": s.repairable} for s in SCENARIOS.values()],
            "definitions": DEFINITIONS, "note": "All provider data is synthetic and simulated by this server."}


@app.get("/api/state")
def state():
    return LAB.state()


class Reset(BaseModel):
    pass


@app.post("/api/lab/reset")
def reset(request: Request):
    limit(request)
    LAB.reset()
    return LAB.state()


class Compile(BaseModel):
    use_model: bool = False


@app.post("/api/lab/compile")
async def compile_(body: Compile, request: Request):
    limit(request)
    try:
        return await asyncio.get_running_loop().run_in_executor(None, LAB.compile, body.use_model)
    except LabError:
        raise
    except Exception as e:
        raise HTTPException(502, llm_mod.sanitize(e))


class Inject(BaseModel):
    scenario: str = Field(pattern=r"^[a-z_]{1,40}$")


@app.post("/api/lab/inject")
def inject(body: Inject, request: Request):
    limit(request)
    return LAB.inject(body.scenario)


@app.post("/api/lab/hard-case")
def hard_case(request: Request, n: int = 10):
    limit(request)
    return LAB.hard_case(n)


@app.get("/api/run/stream")
async def run_stream(request: Request, invoice_id: str | None = None):
    limit(request)
    if invoice_id is not None:
        _rid(invoice_id)
    loop = asyncio.get_running_loop()
    q: asyncio.Queue = asyncio.Queue()

    def work():
        try:
            view = LAB.run(lambda ev: loop.call_soon_threadsafe(q.put_nowait, ev), invoice_id)
            loop.call_soon_threadsafe(q.put_nowait, {"type": "run_view", "run": view})
        except LabError as e:
            loop.call_soon_threadsafe(q.put_nowait, {"type": "error", "code": e.code, "message": e.message})
        except Exception as e:
            loop.call_soon_threadsafe(q.put_nowait, {"type": "error", "code": "internal", "message": llm_mod.sanitize(e)})
        finally:
            loop.call_soon_threadsafe(q.put_nowait, None)

    threading.Thread(target=work, daemon=True).start()

    async def gen():
        while True:
            ev = await q.get()
            if ev is None:
                yield "data: " + json.dumps({"type": "stream_end"}) + "\n\n"
                return
            yield "data: " + json.dumps(ev, default=str) + "\n\n"
            if ev.get("type") in ("step_started", "step_finished", "contract_result"):
                await asyncio.sleep(0.09)       # pacing so a person can follow; events are real and already recorded
    return __import__("fastapi").responses.StreamingResponse(gen(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@app.get("/api/runs/{run_id}")
def get_run(run_id: str):
    return LAB.run_view(LAB.get_run(_rid(run_id)))


@app.post("/api/runs/{run_id}/diagnose")
def diagnose_(run_id: str, request: Request):
    limit(request)
    return LAB.diagnose(_rid(run_id))


class Repair(BaseModel):
    mode: str = Field(default="auto", pattern="^(auto|model|wrong)$")


@app.post("/api/runs/{run_id}/repair")
async def repair_(run_id: str, body: Repair, request: Request):
    limit(request)
    _rid(run_id)
    try:
        return await asyncio.get_running_loop().run_in_executor(None, LAB.repair, run_id, body.mode)
    except LabError:
        raise
    except Exception as e:
        raise HTTPException(502, llm_mod.sanitize(e))


@app.get("/api/runs/{run_id}/export")
def export(run_id: str):
    return JSONResponse(LAB.export_run(_rid(run_id)), headers={"Content-Disposition": f'attachment; filename="jitd-{run_id}.json"'})


def _bench_files():
    return sorted(RESULTS.glob("bench_*.json"), reverse=True) if RESULTS.exists() else []


@app.get("/api/benchmarks")
def benchmarks():
    out = []
    for p in _bench_files():
        try:
            m = json.loads(p.read_text())["meta"]
        except (ValueError, KeyError, OSError):
            continue
        out.append({"id": p.stem, "started_utc": m["started_utc"], "seeds": m["seeds"], "runs_per_stream": m["runs_per_stream"], "mode": m["mode"], "suite_version": m["suite_version"]})
    return {"benchmarks": out}


def _load_bench(bid: str):
    p = {f.stem: f for f in _bench_files()}.get(_rid(bid))
    if p is None:
        raise HTTPException(404, "unknown benchmark")
    return json.loads(p.read_text())


@app.get("/api/benchmarks/{bid}")
def benchmark(bid: str):
    d = _load_bench(bid)
    return {"id": bid, "meta": d["meta"], "cells": d["cells"]}


@app.get("/api/benchmarks/{bid}/csv")
def benchmark_csv(bid: str):
    return PlainTextResponse(summary_csv(_load_bench(bid)), media_type="text/csv", headers={"Content-Disposition": f'attachment; filename="{bid}.csv"'})


class Decision(BaseModel):
    approve: bool


class Pause(BaseModel):
    paused: bool


class Rollback(BaseModel):
    version: str = Field(pattern=r"^[0-9]+\.[0-9]+\.[0-9]+$")


@app.get("/api/operations")
def operations():
    from .operations import overview
    return overview(LAB)


async def _propose(run_id, request, mode):
    limit(request)
    result = await asyncio.get_running_loop().run_in_executor(None, lambda: LAB.repair(_rid(run_id), mode, preview=True))
    if result.get('proposal_id'):
        PlatformStore(LAB.dir).proposer(result['proposal_id'], request.state.principal['name'])
    return result


@app.post('/api/runs/{run_id}/propose-model')
async def propose_model(run_id: str, request: Request):
    return await _propose(run_id, request, 'model')


@app.post('/api/runs/{run_id}/propose')
async def propose(run_id: str, request: Request):
    return await _propose(run_id, request, 'auto')


@app.post("/api/proposals/{proposal_id}/decision")
async def decision(proposal_id: str, body: Decision, request: Request):
    limit(request)
    if enterprise():
        proposer = PlatformStore(LAB.dir).proposer(_rid(proposal_id))
        if proposer is None:
            raise HTTPException(409, 'Proposal has no authenticated proposer; create a fresh proposal')
        if body.approve and proposer == request.state.principal['name']:
            raise HTTPException(403, 'A different reviewer must approve this proposal')
    return await asyncio.get_running_loop().run_in_executor(None, LAB.decide, _rid(proposal_id), body.approve)


@app.post("/api/workflow/pause")
def pause_workflow(body: Pause, request: Request):
    limit(request)
    return LAB.pause(body.paused)


@app.post("/api/workflow/rollback")
def rollback_workflow(body: Rollback, request: Request):
    limit(request)
    return LAB.rollback(body.version)


@app.get("/api/audit/export")
def audit_export():
    return JSONResponse({"schema": "jitd.audit/1", "mode": "synthetic_provider", "events": LAB.store.audit()},
                        headers={"Content-Disposition": 'attachment; filename="jitd-audit.json"'})


@app.post("/api/recordings/validate")
async def validate_recorded(request: Request):
    limit(request)
    raw = await request.body()
    from .sdk import validate_recording
    from .schemas import SchemaError
    try:
        case = json.loads(raw)
        with LAB.lock:
            manifest = LAB.manifest.clone()
        return await asyncio.get_running_loop().run_in_executor(None, validate_recording, manifest, case)
    except (ValueError, KeyError, TypeError, SchemaError) as e:
        raise HTTPException(422, llm_mod.sanitize(e))


class EvidenceMode(BaseModel):
    mode: str = Field(pattern="^(independent|missing|correlated)$")


@app.post("/api/evidence-mode")
def evidence_mode(body: EvidenceMode, request: Request):
    limit(request)
    with LAB.lock:
        LAB._mutable()
        LAB.services.evidence_mode = body.mode
        LAB._checkpoint("evidence_mode_changed", {"mode": body.mode})
    return {"mode": body.mode, "note": "Simulated authority availability. Required UNKNOWN evidence blocks posting."}


@app.get("/api/aair/benchmark")
def aair_benchmark():
    final = ROOT / "benchmark" / "final" / "aair.json"
    if final.exists():
        return {"available": True, **json.loads(final.read_text(encoding="utf-8"))}
    files = sorted((ROOT / "benchmark" / "aair").glob("aair_*.json"), reverse=True)
    if not files:
        return {"available": False, "note": "Run python -m jitd.aair_bench"}
    return {"available": True, **json.loads(files[0].read_text(encoding="utf-8"))}


def pilot_store():
    from .pilot import PilotStore
    return PilotStore(LAB.dir)


async def bounded_json(request):
    raw = bytearray()
    async for chunk in request.stream():
        raw.extend(chunk)
        if len(raw) > 2 * 1024 * 1024:
            raise HTTPException(413, 'Case exceeds 2 MiB')
    try:
        return json.loads(raw)
    except ValueError:
        raise HTTPException(422, 'Invalid JSON')


@app.get('/api/pilot')
def pilot_overview():
    store = pilot_store()
    return {'report': store.report(), 'cases': store.rows()}


@app.post('/api/pilot/import')
async def pilot_import(request: Request):
    limit(request)
    bundle = await bounded_json(request)
    with LAB.lock:
        manifest = LAB.manifest.clone()
    try:
        return await asyncio.get_running_loop().run_in_executor(None, pilot_store().create, bundle, manifest)
    except (ValueError, KeyError, TypeError, ArithmeticError, SchemaError):
        raise HTTPException(422, 'Invalid case bundle; check recording, provenance, supported page limit and evidence fields')


class PilotReview(BaseModel):
    revision: int = Field(ge=1)
    reviewer: str = Field(min_length=1, max_length=100)
    note: str = Field(min_length=1, max_length=2000)
    human_minutes: float = Field(ge=0, le=1440, allow_inf_nan=False)
    authority: dict | None = None


@app.post('/api/pilot/{case_id}/review')
async def pilot_review(case_id: str, body: PilotReview, request: Request):
    limit(request)
    with LAB.lock:
        manifest = LAB.manifest.clone()
    try:
        return await asyncio.get_running_loop().run_in_executor(None, pilot_store().resolve, _rid(case_id), body.revision,
                    request.state.principal['name'] if enterprise() else body.reviewer, body.note, body.human_minutes, body.authority, manifest)
    except KeyError:
        raise HTTPException(404, 'Unknown case')
    except RuntimeError:
        raise HTTPException(409, 'Case changed; reload before reviewing')
    except (ValueError, TypeError, ArithmeticError, SchemaError):
        raise HTTPException(422, 'Invalid evidence review')


@app.get('/api/pilot/export')
def pilot_export():
    store = pilot_store()
    return JSONResponse({'schema': 'jitd.pilot/1', 'report': store.report(), 'cases': store.rows(), 'events': store.events()},
                        headers={'Content-Disposition': 'attachment; filename="jitd-pilot.json"'})


@app.get('/api/readiness')
def submission_readiness():
    from .readiness import readiness
    return readiness(ROOT, pilot_store())


@app.get('/api/research/paired')
def paired_results():
    path = ROOT / 'benchmark' / 'paired' / 'latest.json'
    if not path.exists(): return {'available': False}
    data = json.loads(path.read_text())
    return {'available': True, 'meta': data['meta'], 'cells': data['cells']}


app.mount("/static", StaticFiles(directory=ROOT / "web"), name="static")


@app.get("/")
def index():
    return FileResponse(ROOT / "web" / "home.html")


class Execution(BaseModel):
    invoice_id: str | None = Field(default=None, pattern=r'^[A-Za-z0-9_.-]{1,80}$')


@app.post('/api/executions')
async def execute(body: Execution, request: Request):
    limit(request)
    return await asyncio.get_running_loop().run_in_executor(None, lambda: LAB.run(invoice_id=body.invoice_id))


@app.get('/api/platform/me')
def platform_me(request: Request):
    return {**request.state.principal, 'profile': 'enterprise' if enterprise() else 'local',
            'separate_reviewer_required': enterprise()}


@app.get('/api/platform/status')
def platform_status():
    store = PlatformStore(LAB.dir)
    return {'profile': 'enterprise' if enterprise() else 'local', 'scope': 'Single workspace; synthetic ledger; controlled pilot',
            'authentication': 'Named users with role enforcement' if enterprise() else 'Local / optional shared access',
            'model_configured': llm_mod.available(), 'model_id': os.getenv('NEBIUS_MODEL_ID') if llm_mod.available() else None,
            'budget': llm_mod.budget(), 'budget_persistent': bool(os.getenv('JITD_BUDGET_DB')),
            'usage': store.usage(), 'audit': store.verify(), 'paused': LAB.paused,
            'promotion': 'Validated proposal + separate reviewer' if enterprise() else 'Sandbox controls',
            'storage': 'SQLite; one process; backups via offline administrator', 'provider_calls_from_this_check': 0}


@app.get('/api/platform/audit')
def platform_audit():
    store = PlatformStore(LAB.dir)
    return {'schema': 'jitd.security-audit/1', 'verification': store.verify(), 'events': store.events(500)}


@app.get('/api/platform/ready')
def platform_ready():
    import sqlite3
    try:
        with LAB.store.connect() as db:
            good = db.execute('PRAGMA quick_check').fetchone()[0] == 'ok'
        chain = PlatformStore(LAB.dir).verify()['valid']
        from .studio_api import get_studio
        studio = get_studio()
        with studio.connect() as db:
            studio_good = db.execute('PRAGMA quick_check').fetchone()[0] == 'ok'
        passport_good = studio.verify_passports()['valid']
        from .canvas_api import store as canvas_store
        with canvas_store().db() as db:
            canvas_good = db.execute('PRAGMA quick_check').fetchone()[0] == 'ok'
        ready = bool(good and chain and studio_good and passport_good and canvas_good)
        return JSONResponse({'ready': ready, 'studio_passports_valid': passport_good, 'model_required_for_local_execution': False}, status_code=200 if ready else 503)
    except sqlite3.Error:
        return JSONResponse({'ready': False}, status_code=503)


@app.get('/api/platform/metrics', response_class=PlainTextResponse)
def platform_metrics():
    usage = PlatformStore(LAB.dir).usage()
    with LAB.lock:
        rows = list(LAB.runs.values())
        return '\n'.join(['# JIT-D workspace gauges; retained runs only, not lifetime counters',
            f'jitd_retained_runs {len(rows)}', f'jitd_workflow_paused {int(LAB.paused)}',
            f'jitd_model_attempts {usage["used"]}', f'jitd_model_usage_unknown {usage["usage_unknown_calls"]}',
            f'jitd_model_attempts_remaining {llm_mod.budget()["remaining"]}', ''])


@app.get('/operations')
def operations_console():
    return FileResponse(ROOT / 'web' / 'operations.html')


from .studio_api import router as studio_router
app.include_router(studio_router)

app.add_middleware(Boundary)

from .canvas_api import router as canvas_router
app.include_router(canvas_router)

from .hybrid_api import router as hybrid_router
app.include_router(hybrid_router)

from .presentation_api import router as presentation_router
app.include_router(presentation_router)

from starlette.exceptions import HTTPException as StarletteHTTPException

@app.exception_handler(StarletteHTTPException)
async def http_error_page(request, exc):
    if exc.status_code == 404 and 'text/html' in request.headers.get('accept', '') and not request.url.path.startswith('/api/'):
        return FileResponse(ROOT / 'web' / '404.html', status_code=404)
    return JSONResponse({'detail': exc.detail}, status_code=exc.status_code, headers=exc.headers)
