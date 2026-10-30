"""Isolated validation worker: reads one JSON payload on stdin, writes one JSON report on stdout.
Launched with a scrubbed environment (no API keys, no proxies) by repair.validate_isolated."""
import json
import os
import sys

from .validation import run_validation

def main():
    payload = json.loads(sys.stdin.read())
    rep = run_validation(payload)
    rep["worker"] = {"pid": os.getpid(), "env_keys": sorted(os.environ)}
    sys.stdout.write(json.dumps(rep))


if __name__ == "__main__":
    main()
