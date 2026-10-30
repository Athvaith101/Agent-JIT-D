from types import SimpleNamespace as NS
from jitd import nebius_smoke
from jitd.platform import PlatformStore


def setup(monkeypatch,tmp_path):
    monkeypatch.setenv('JITD_DATA_DIR',str(tmp_path));monkeypatch.setenv('JITD_BUDGET_DB',str(tmp_path/'platform.sqlite3'))
    monkeypatch.setenv('NEBIUS_API_KEY','fake-test-never-a-real-key');monkeypatch.setenv('NEBIUS_MODEL_ID','test-model')
    monkeypatch.setenv('NEBIUS_BASE_URL','https://api.tokenfactory.nebius.com/v1/')
    monkeypatch.setattr(nebius_smoke,'load_env',lambda _:None)
    monkeypatch.delenv('JITD_MODEL_MAX_OUTPUT_TOKENS',raising=False)


def test_smoke_defaults_zero(monkeypatch,tmp_path,capsys):
    setup(monkeypatch,tmp_path);monkeypatch.delenv('JITD_MAX_MODEL_CALLS',raising=False)
    assert nebius_smoke.main([])==2
    out=capsys.readouterr();assert 'No request sent' in out.err and 'fake-test-never-a-real-key' not in out.err+out.out


def test_smoke_requires_model(monkeypatch,tmp_path):
    setup(monkeypatch,tmp_path);monkeypatch.delenv('NEBIUS_MODEL_ID');assert nebius_smoke.main([])==2


def test_smoke_rejects_unapproved_destination(monkeypatch,tmp_path,capsys):
    setup(monkeypatch,tmp_path);monkeypatch.setenv('JITD_MAX_MODEL_CALLS','1');monkeypatch.setenv('NEBIUS_BASE_URL','https://attacker.invalid/v1')
    assert nebius_smoke.main([])==2 and 'approved' in capsys.readouterr().err


def test_smoke_attempt_budget_persists(monkeypatch,tmp_path,capsys):
    import openai
    setup(monkeypatch,tmp_path);monkeypatch.setenv('JITD_MAX_MODEL_CALLS','1')
    calls=[]
    class Fake:
        def __init__(self,**kwargs):self.chat=NS(completions=NS(create=self.create))
        def create(self,**kwargs):
            calls.append(kwargs)
            return NS(usage=NS(prompt_tokens=10,completion_tokens=3,total_tokens=13),choices=[NS(message=NS(content='JITD_OK'))])
    monkeypatch.setattr(openai,'OpenAI',Fake)
    assert nebius_smoke.main([])==0
    assert nebius_smoke.main([])==2
    assert len(calls)==1 and calls[0]['max_tokens']<=16
    assert PlatformStore(tmp_path).usage()['used']==1
    output=capsys.readouterr();assert 'fake-test-never-a-real-key' not in output.out+output.err
