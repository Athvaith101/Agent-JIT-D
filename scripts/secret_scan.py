"""Fail if anything that looks like a real credential is in the tree. Run: python scripts/secret_scan.py"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKIP_DIRS = {".git", "__pycache__", ".pytest_cache", "node_modules", ".venv"}
PATTERNS = {
    "nebius/openai-style key": re.compile(r"\b(?:sk|v1)[-_][A-Za-z0-9_\-]{24,}\b"),
    "aws access key": re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    "private key block": re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    "key assigned in code/env": re.compile(r"NEBIUS_API_KEY\s*=\s*['\"]?[A-Za-z0-9_\-]{20,}"),
    "bearer token": re.compile(r"Bearer\s+[A-Za-z0-9._\-]{30,}"),
}
# Synthetic demo secrets are deliberately present in scenario data and are labelled as fake.
ALLOW = ("LEAKCHECK", "SENTINEL", "sk-SECRET", "SYNTHETIC", "sk-live-DEMO", "AKIADEMO", "FAKE", "example")


def scan(root: Path = ROOT) -> list[str]:
    hits = []
    for p in root.rglob("*"):
        if not p.is_file() or set(p.relative_to(root).parts) & SKIP_DIRS or p.suffix in {".png", ".zip", ".pyc"}:
            continue
        try:
            text = p.read_text(errors="ignore")
        except OSError:
            continue
        for name, pat in PATTERNS.items():
            for m in pat.finditer(text):
                line = text[max(0, m.start() - 80): m.end() + 40]
                if any(a.lower() in line.lower() for a in ALLOW):
                    continue
                hits.append(f"{p.relative_to(root)}: {name}: {m.group()[:12]}…")
    return hits


if __name__ == "__main__":
    h = scan()
    print("\n".join(h) if h else "secret scan: clean")
    sys.exit(1 if h else 0)
