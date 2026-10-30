"""Safe reference/path resolution. No eval, no attribute access, no dunder keys."""
from __future__ import annotations

import re

_TOKEN = re.compile(r"\.([A-Za-z_][A-Za-z0-9_]*)|\[(\*|\d+)\]")
REF_RE = re.compile(r"^\$(input|[a-z_][a-z0-9_]*)((?:\.[A-Za-z_][A-Za-z0-9_]*|\[\*\]|\[\d+\])*)$")
REL_RE = re.compile(r"^(?:[A-Za-z_][A-Za-z0-9_]*)?(?:\.[A-Za-z_][A-Za-z0-9_]*|\[\*\]|\[\d+\])*$")


def parse_ref(ref: str) -> tuple[str, str]:
    m = REF_RE.match(ref or "")
    if not m:
        raise ValueError(f"bad reference {ref!r}")
    return m.group(1), m.group(2)


def get_path(value, path: str):
    """Resolve '.a[0].b' / 'a.b[*].c' against nested dicts/lists. '[*]' maps (and flattens one level)."""
    if path and not path.startswith((".", "[")):
        path = "." + path
    if not REL_RE.match(path.lstrip(".") if path.startswith(".") else path) and path:
        raise ValueError(f"bad path {path!r}")
    cur = [value]
    star = False
    for m in _TOKEN.finditer(path):
        key, idx = m.group(1), m.group(2)
        nxt = []
        for v in cur:
            if key is not None:
                if key.startswith("__") or not isinstance(v, dict) or key not in v:
                    raise KeyError(key)
                nxt.append(v[key])
            elif idx == "*":
                if not isinstance(v, list):
                    raise KeyError("[*] on non-list")
                nxt.extend(v)
                star = True
            else:
                if not isinstance(v, list) or int(idx) >= len(v):
                    raise KeyError(f"[{idx}]")
                nxt.append(v[int(idx)])
        cur = nxt
    return cur if star else cur[0]
