"""Local startup with optional .env configuration; values already exported take precedence."""
import os
from pathlib import Path


def load_env(path):
    if not path.exists():
        return
    for line in path.read_text(encoding='utf-8-sig').splitlines():
        line = line.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        key, value = line.split('=', 1)
        if key.strip().isidentifier():
            os.environ.setdefault(key.strip(), value.strip().strip('\"\''))


def main():
    import argparse
    import getpass
    import logging
    parser = argparse.ArgumentParser(description='Start JIT-D; secrets may be supplied through environment variables or a hidden prompt.')
    parser.add_argument('--profile', choices=('local', 'enterprise'))
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int)
    parser.add_argument('--ask-api-key', action='store_true', help='Hidden prompt; key stays in this process and is not written to disk')
    args = parser.parse_args()
    load_env(Path(__file__).resolve().parent.parent / '.env')
    if args.profile:
        os.environ['JITD_PROFILE'] = args.profile
    if args.ask_api_key:
        key = getpass.getpass('Nebius API key (hidden, never saved): ').strip()
        if not key:
            parser.error('API key was empty')
        os.environ['NEBIUS_API_KEY'] = key
    from .platform import data_dir, enterprise, validate_runtime
    if args.host not in ('127.0.0.1', 'localhost', '::1') and not enterprise() and not os.getenv('JITD_ACCESS_TOKEN'):
        parser.error('Network binding requires enterprise profile or an explicit shared access token')
    os.environ.setdefault('JITD_MAX_MODEL_CALLS', '0')
    try:
        if not 0 <= int(os.environ['JITD_MAX_MODEL_CALLS']) <= 10000:
            raise ValueError()
    except ValueError:
        parser.error('JITD_MAX_MODEL_CALLS must be an integer from 0 to 10000')
    os.environ.setdefault('JITD_BUDGET_DB', str(data_dir() / 'platform.sqlite3'))
    try:
        validate_runtime()
    except RuntimeError as exc:
        parser.error(str(exc))
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(name)s %(message)s')
    import uvicorn
    uvicorn.run('jitd.server:app', host=args.host, port=args.port or int(os.getenv('PORT', '8000')), workers=1,
                proxy_headers=False, access_log=False, limit_concurrency=32, timeout_keep_alive=5, timeout_graceful_shutdown=30)


if __name__ == '__main__':
    main()
