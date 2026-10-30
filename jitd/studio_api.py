"""Studio HTTP routes; all expensive work runs outside the ASGI event loop."""
import asyncio
import os
import threading
from functools import partial
from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, ConfigDict, Field

from . import llm
from .platform import enterprise
from .studio import CostInputs, DraftInput, Settings, Studio, project_cost

router = APIRouter()
_studios = {}
_lock = threading.Lock()


def get_studio():
    from .server import LAB
    key = str(LAB.dir.resolve())
    with _lock:
        if key not in _studios:
            def factory(meter, role):
                model = os.getenv('JITD_ARCHITECT_MODEL_ID' if role == 'Architect' else 'JITD_REPAIR_MODEL_ID') or os.environ['NEBIUS_MODEL_ID']
                return llm.NebiusClient(meter, model=model)
            _studios[key] = Studio(LAB.dir, factory if llm.available() else None, client_source='nebius_api')
        return _studios[key]


async def call(fn, *args, **kwargs):
    return await asyncio.get_running_loop().run_in_executor(None, partial(fn, *args, **kwargs))


def actor(request):
    return request.state.principal['name']


class Revision(BaseModel):
    model_config = ConfigDict(extra='forbid')
    revision: int = Field(ge=1, strict=True)


class Edit(Revision):
    name: str = Field(min_length=3, max_length=80)
    task: str = Field(min_length=12, max_length=2000)
    settings: Settings


class Publish(Revision):
    report_id: str = Field(pattern=r'^report_[a-f0-9]{16}$')
    human_minutes: float | None = Field(default=None, ge=0, le=1440, allow_inf_nan=False)


class RuntimeSettings(BaseModel):
    model_config = ConfigDict(extra='forbid')
    scenario: str
    evidence: str = 'independent'


class Execution(BaseModel):
    model_config = ConfigDict(extra='forbid')
    auto_assist: bool = False
    invoice_id: str | None = Field(default=None, pattern=r'^[A-Za-z0-9_.-]{1,80}$')


class Propose(BaseModel):
    model_config = ConfigDict(extra='forbid')
    use_model: bool = False


class Decision(BaseModel):
    model_config = ConfigDict(extra='forbid')
    approve: bool
    human_minutes: float | None = Field(default=None, ge=0, le=1440, allow_inf_nan=False)


@router.get('/lab')
def original_lab_page():
    return FileResponse(Path(__file__).resolve().parent.parent / 'web' / 'index.html')


@router.get('/studio')
def studio_page():
    return FileResponse(Path(__file__).resolve().parent.parent / 'web' / 'studio.html')


@router.get('/api/studio')
async def overview():
    return await call(get_studio().overview)


@router.post('/api/studio/drafts')
async def create(body: DraftInput, request: Request):
    return await call(get_studio().create, body, actor(request))


@router.get('/api/studio/drafts/{aid}')
async def draft(aid: str):
    return await call(get_studio()._get, 'drafts', aid)


@router.put('/api/studio/drafts/{aid}')
async def edit(aid: str, body: Edit, request: Request):
    return await call(get_studio().update, aid, body.revision, body.name, body.task, body.settings, actor(request))


@router.post('/api/studio/drafts/{aid}/test')
async def test(aid: str, body: Revision, request: Request):
    return await call(get_studio().test, aid, body.revision, actor(request))


@router.get('/api/studio/reports/{rid}')
async def report(rid: str):
    return await call(get_studio()._get, 'reports', rid)


@router.post('/api/studio/drafts/{aid}/publish')
async def publish(aid: str, body: Publish, request: Request):
    return await call(get_studio().publish, aid, body.revision, body.report_id, actor(request),
                      separate_reviewer=enterprise(), human_minutes=body.human_minutes)


@router.get('/api/studio/versions/{vid}')
async def version(vid: str):
    return await call(get_studio().version_detail, vid)


@router.post('/api/studio/versions/{vid}/configure')
async def configure(vid: str, body: RuntimeSettings, request: Request):
    return await call(get_studio().configure_run, vid, body.scenario, body.evidence, actor(request))


@router.post('/api/studio/versions/{vid}/executions')
async def execute(vid: str, body: Execution, request: Request):
    saved=await call(get_studio().execute, vid, body.invoice_id, actor(request))
    if body.auto_assist:
        from .hybrid_api import assist
        saved['hybrid_assistance']=await call(assist,saved['id'],actor(request))
    return saved


@router.get('/api/studio/runs/{rid}')
async def run(rid: str):
    return await call(get_studio()._get, 'executions', rid)


@router.get('/api/studio/runs/{rid}/passport')
async def passport(rid: str):
    value = await call(get_studio()._get, 'executions', rid)
    return JSONResponse({'passport': value['passport'], 'chain_verification': get_studio().verify_passports()},
                        headers={'Content-Disposition': f'attachment; filename="{rid}-passport.json"'})


@router.post('/api/studio/versions/{vid}/runs/{rid}/propose')
async def propose(vid: str, rid: str, body: Propose, request: Request):
    return await call(get_studio().propose, vid, rid, body.use_model, actor(request))


@router.post('/api/studio/proposals/{pid}/decision')
async def decide(pid: str, body: Decision, request: Request):
    return await call(get_studio().decide, pid, body.approve, actor(request),
                      separate_reviewer=enterprise(), human_minutes=body.human_minutes)


@router.get('/api/studio/receipts/{rid}')
async def receipt(rid: str):
    return await call(get_studio().receipt, rid)


@router.get('/api/studio/runs/{rid}/comparison')
async def comparison(rid: str):
    return await call(get_studio().comparison, rid)


@router.post('/api/studio/cost/project')
def costs(body: CostInputs):
    return project_cost(body)


@router.get('/api/studio/runs/{rid}/assurance')
async def assurance(rid: str, budget: int = 4, changed_source: str = ''):
    from .assurance import report
    from .lab import LabError
    if not 0 <= budget <= 1000000:
        raise LabError('invalid_budget', 'Budget must be between 0 and 1000000 planning units.', 422)
    saved = await call(get_studio()._get, 'executions', rid)
    return report(saved['run'], budget, [changed_source] if changed_source else [])
