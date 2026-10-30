import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _scan():
    spec = importlib.util.spec_from_file_location("secret_scan", ROOT / "scripts/secret_scan.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def test_no_real_looking_secrets_in_tree():
    hits = [h for h in _scan().scan() if "tests/" not in h]
    assert hits == []


def test_scanner_catches_a_planted_key(tmp_path):
    (tmp_path / "x.py").write_text('KEY = "sk-' + "a1b2c3d4" * 4 + '"\n')
    assert _scan().scan(tmp_path)


def test_gitignore_and_env_example():
    g = (ROOT / ".gitignore").read_text()
    assert ".env" in g and "data/" in g
    assert "replace_me" in (ROOT / ".env.example").read_text()


def test_frontend_never_references_secrets():
    for p in (ROOT / "web").rglob("*"):
        if p.is_file():
            t = p.read_text(errors="ignore")
            assert "NEBIUS_API_KEY" not in t and "Authorization" not in t
