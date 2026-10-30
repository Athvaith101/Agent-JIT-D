import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("JITD_DATA_DIR", tempfile.mkdtemp(prefix="jitd-test-"))
for k in ("NEBIUS_API_KEY", "NEBIUS_MODEL_ID"):
    os.environ.pop(k, None)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


import pytest


@pytest.fixture(autouse=True)
def _fresh_model_budget(monkeypatch):
    monkeypatch.setenv("JITD_MAX_MODEL_CALLS", "300")
    monkeypatch.delenv("JITD_BUDGET_DB", raising=False)
    from jitd import llm
    llm.reset_budget()
    yield
    llm.reset_budget()
