"""Make one explicitly budgeted Nebius Token Factory chat-completion request.

This is an operator smoke check, not part of normal workflow execution. The API
key is read from the process environment/.env or from a hidden terminal prompt;
it is never printed or written by this command.
"""
from __future__ import annotations

import argparse
import getpass
import os
import sys
from pathlib import Path
from urllib.parse import urlsplit

from .launch import load_env


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Send one small, metered Nebius Token Factory test request.")
    parser.add_argument("--ask-api-key", action="store_true", help="Read the API key using a hidden prompt")
    parser.add_argument("--max-tokens", type=int, default=16, help="Maximum response tokens (1..64; default: 16)")
    args = parser.parse_args(argv)
    if not 1 <= args.max_tokens <= 64:
        parser.error("--max-tokens must be from 1 to 64 for this smoke check")

    project_root = Path(__file__).resolve().parent.parent
    load_env(project_root / ".env")
    current_key = os.getenv("NEBIUS_API_KEY", "").strip()
    if args.ask_api_key and (not current_key or current_key.startswith("replace_")):
        key = getpass.getpass("Nebius API key (hidden, never saved): ").strip()
        if not key:
            parser.error("API key was empty")
        os.environ["NEBIUS_API_KEY"] = key

    # Keep this explicit check useful even when the package is run outside the
    # normal launcher, which otherwise supplies the zero-call safe default.
    os.environ.setdefault("JITD_MAX_MODEL_CALLS", "0")
    if not os.getenv("NEBIUS_MODEL_ID", "").strip():
        print("Missing NEBIUS_MODEL_ID. Copy the exact model ID shown in your Nebius account.", file=sys.stderr)
        return 2
    if not os.getenv("NEBIUS_API_KEY", "").strip() or os.getenv("NEBIUS_API_KEY", "").startswith("replace_"):
        print("Missing NEBIUS_API_KEY. Set it in .env or rerun with --ask-api-key.", file=sys.stderr)
        return 2
    try:
        max_calls = int(os.environ["JITD_MAX_MODEL_CALLS"])
    except ValueError:
        print("JITD_MAX_MODEL_CALLS must be an integer. Set it to 1 for one smoke request.", file=sys.stderr)
        return 2
    if max_calls < 1:
        print("No request sent: set JITD_MAX_MODEL_CALLS=1 (or higher) to authorize a test call.", file=sys.stderr)
        return 2

    # Bound the smoke request regardless of a larger app output-token setting.
    configured_limit = os.getenv("JITD_MODEL_MAX_OUTPUT_TOKENS")
    if configured_limit:
        try:
            args.max_tokens = min(args.max_tokens, int(configured_limit))
        except ValueError:
            print("JITD_MODEL_MAX_OUTPUT_TOKENS must be an integer from 1 to 8192.", file=sys.stderr)
            return 2
    if args.max_tokens < 1:
        print("No request sent: configured output-token limit is below 1.", file=sys.stderr)
        return 2
    os.environ["JITD_MODEL_MAX_OUTPUT_TOKENS"] = str(args.max_tokens)

    from .platform import data_dir
    os.environ.setdefault("JITD_BUDGET_DB", str(data_dir() / "platform.sqlite3"))
    endpoint = urlsplit(os.getenv("NEBIUS_BASE_URL", "https://api.tokenfactory.nebius.com/v1/"))
    try:
        safe = (endpoint.scheme == "https" and endpoint.hostname in {"api.tokenfactory.nebius.com", "api.tokenfactory.us-central1.nebius.com"}
                and endpoint.port in (None,443) and not endpoint.username and not endpoint.password
                and endpoint.path.rstrip('/') == '/v1' and not endpoint.query and not endpoint.fragment)
    except ValueError:
        safe = False
    if not safe:
        print("No request sent: use an approved Nebius HTTPS /v1 endpoint.", file=sys.stderr)
        return 2

    from . import llm
    from .meter import ModelMeter

    if not llm.available():
        print("Nebius configuration is incomplete or still contains a placeholder.", file=sys.stderr)
        return 2

    meter = ModelMeter()
    try:
        client = llm.NebiusClient(meter=meter, timeout=30)
        answer = client.complete(
            "explain",
            "You are checking an API connection. Follow the user's instruction exactly.",
            "Reply with exactly: JITD_OK",
            max_tokens=args.max_tokens,
        ).strip()
    except llm.BudgetExceeded as exc:
        print(f"No request sent: {exc}", file=sys.stderr)
        return 2
    except Exception as exc:
        print("Nebius request failed: " + llm.sanitize(exc), file=sys.stderr)
        print("Check the model ID, API key, account balance, and Token Factory availability.", file=sys.stderr)
        return 1

    usage = meter.usage[-1] if meter.usage else {}
    print("Nebius API request succeeded.")
    print(f"Model: {client.model}")
    print(f"Response: {answer[:300]}")
    print(f"Usage reported: input={usage.get('input_tokens')} output={usage.get('output_tokens')} tokens")
    print(f"Latency: {usage.get('latency_ms')} ms")
    print("This was a real provider request; check your Nebius account for the resulting usage or credit charge.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
