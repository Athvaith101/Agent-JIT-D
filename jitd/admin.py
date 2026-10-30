"""Offline administration. Passwords/API keys are entered using hidden terminal prompts."""
from __future__ import annotations

import argparse
import getpass
import hashlib
import json
import os
import re
import sqlite3
import sys
import tempfile
import zipfile
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath

from .platform import PlatformStore, ROLES, data_dir, password_hash


@contextmanager
def exclusive(directory):
    """One application process or offline administrator per data directory, on Windows/POSIX."""
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    stream = (directory / '.instance.lock').open('a+b')
    stream.seek(0)
    if not stream.read(1):
        stream.write(b'0'); stream.flush()
    stream.seek(0)
    try:
        if os.name == 'nt':
            import msvcrt
            msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        stream.close()
        raise RuntimeError('Data directory is in use. Stop the server before offline administration; use one worker.') from None
    try:
        yield
    finally:
        if os.name == 'nt':
            import msvcrt
            stream.seek(0); msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl
            fcntl.flock(stream, fcntl.LOCK_UN)
        stream.close()


def atomic_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp = tempfile.mkstemp(dir=path.parent, suffix='.tmp')
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            json.dump(value, f, indent=2)
        os.replace(temp, path)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


def add_user(directory, name, role, password):
    if not re.fullmatch(r'[A-Za-z0-9_.-]{1,64}', name) or role not in ROLES:
        raise ValueError('Invalid username or role')
    path = Path(directory) / 'users.json'
    with exclusive(directory):
        users = json.loads(path.read_text()) if path.exists() else {}
        if name in users:
            raise ValueError('User already exists; use user-password to rotate credentials')
        users[name] = {'role': role, 'disabled': False, 'password': password_hash(password)}
        atomic_json(path, users)
        PlatformStore(directory).event(action='user_created', actor='offline_admin', target=name, role=role)


def backup(directory, target):
    directory, target = Path(directory).resolve(), Path(target).resolve()
    if target == directory or directory in target.parents:
        raise ValueError('Backup must be outside the data directory')
    if target.exists():
        raise ValueError('Backup target exists; choose a new filename')
    target.parent.mkdir(parents=True, exist_ok=True)
    with exclusive(directory), tempfile.TemporaryDirectory() as temp:
        staged = Path(temp)
        manifest = {'schema': 'jitd.backup/1', 'created': datetime.now(timezone.utc).isoformat(), 'files': {}}
        paths = [p for p in directory.rglob('*') if p.is_file() and not any(x.startswith('.') for x in p.relative_to(directory).parts)]
        if any(p.is_symlink() for p in directory.rglob('*')):
            raise ValueError('Symlinks are not supported in the data directory')
        for path in paths:
            if path.name.endswith(('-journal', '-wal', '-shm', '.tmp')):
                continue
            name = path.relative_to(directory).as_posix()
            if path.suffix == '.sqlite3':
                dest = staged / name
                dest.parent.mkdir(parents=True, exist_ok=True)
                with sqlite3.connect(path) as src, sqlite3.connect(dest) as dst:
                    src.backup(dst)
                content = dest.read_bytes()
            else:
                content = path.read_bytes()
            manifest['files'][name] = hashlib.sha256(content).hexdigest()
            dest = staged / name
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(content)
        # Exclusive creation avoids overwriting an existing archive.
        with target.open('xb') as f:
            if os.name != 'nt':
                os.chmod(target, 0o600)
            with zipfile.ZipFile(f, 'w', zipfile.ZIP_DEFLATED) as z:
                for name in manifest['files']:
                    z.write(staged / name, 'data/' + name)
                z.writestr('manifest.json', json.dumps(manifest, indent=2))
    return {'file': str(target), 'files': len(manifest['files']), 'sha256': hashlib.sha256(target.read_bytes()).hexdigest()}


def restore(archive, target):
    target = Path(target).resolve()
    if target.exists():
        raise ValueError('Restore requires a new directory; existing data is never overwritten')
    with zipfile.ZipFile(archive) as z:
        infos = z.infolist()
        if len(infos) > 10000 or sum(x.file_size for x in infos) > 100 * 1024 * 1024:
            raise ValueError('Archive exceeds restore limits')
        names = z.namelist()
        if len(set(names)) != len(names):
            raise ValueError('Duplicate archive paths')
        manifest = json.loads(z.read('manifest.json'))
        if manifest.get('schema') != 'jitd.backup/1':
            raise ValueError('Unsupported backup schema')
        expected = {'manifest.json'} | {'data/' + n for n in manifest['files']}
        if set(names) != expected:
            raise ValueError('Archive inventory mismatch')
        contents = {}
        for name, digest in manifest['files'].items():
            p = PurePosixPath(name)
            if p.is_absolute() or '..' in p.parts or '\\' in name or ':' in name or name != p.as_posix() or any(x.startswith('.') for x in p.parts):
                raise ValueError('Unsafe backup path')
            content = z.read('data/' + name)
            if hashlib.sha256(content).hexdigest() != digest:
                raise ValueError('Backup content checksum mismatch')
            contents[name] = content
    # Validate every byte before creating a destination.
    target.mkdir(parents=True, mode=0o700)
    try:
        for name, content in contents.items():
            dest = target / name
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(content)
            if os.name != 'nt':
                os.chmod(dest, 0o600)
        for p in target.rglob('*.sqlite3'):
            with sqlite3.connect(p) as db:
                if db.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
                    raise ValueError('Restored SQLite integrity check failed')
        if (target / 'platform.sqlite3').exists() and not PlatformStore(target).verify()['valid']:
            raise ValueError('Restored audit chain is invalid')
        if (target / 'studio.sqlite3').exists():
            from .studio import Studio
            if not Studio(target).verify_passports()['valid']:
                raise ValueError('Restored evidence passport chain is invalid')
    except Exception:
        import shutil
        shutil.rmtree(target)
        raise
    return {'restored': str(target), 'files': len(contents)}


def doctor(directory):
    directory = Path(directory)
    from .llm import available
    checks = {'python_supported': sys.version_info >= (3, 11), 'data_directory': str(directory.resolve()),
              'model_configured': available(), 'provider_calls': 0}
    checks['databases'] = {}
    for path in directory.glob('*.sqlite3'):
        try:
            with sqlite3.connect(path) as db:
                checks['databases'][path.name] = db.execute('PRAGMA integrity_check').fetchone()[0]
        except sqlite3.Error:
            checks['databases'][path.name] = 'unreadable'
    checks['audit'] = PlatformStore(directory).verify()
    checks['model_usage'] = PlatformStore(directory).usage()
    checks['studio_passports'] = None
    if (directory / 'studio.sqlite3').exists():
        from .studio import Studio
        checks['studio_passports'] = Studio(directory).verify_passports()
    checks['ok'] = all(v == 'ok' for v in checks['databases'].values()) and checks['audit']['valid'] and checks['python_supported'] and (checks['studio_passports'] is None or checks['studio_passports']['valid'])
    return checks


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data-dir', type=Path, default=data_dir())
    sub = parser.add_subparsers(dest='command', required=True)
    user = sub.add_parser('user-add'); user.add_argument('name'); user.add_argument('--role', choices=sorted(ROLES), required=True)
    for command in ('user-disable', 'user-password'):
        sub.add_parser(command).add_argument('name')
    sub.add_parser('doctor')
    sub.add_parser('audit-verify')
    sub.add_parser('backup').add_argument('--output', type=Path, required=True)
    res = sub.add_parser('restore'); res.add_argument('archive', type=Path); res.add_argument('--target', type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.command == 'user-add':
            first = getpass.getpass('New password (at least 14 characters): ')
            if first != getpass.getpass('Confirm password: '):
                raise ValueError('Passwords do not match')
            add_user(args.data_dir, args.name, args.role, first)
            print('User created. Password was not printed or stored in plaintext.')
        elif args.command in ('user-disable', 'user-password'):
            with exclusive(args.data_dir):
                path = args.data_dir / 'users.json'
                users = json.loads(path.read_text())
                if args.name not in users:
                    raise ValueError('Unknown user')
                if args.command == 'user-disable':
                    if users[args.name]['role'] == 'admin' and sum(u['role'] == 'admin' and not u.get('disabled') for u in users.values()) <= 1:
                        raise ValueError('Cannot disable the last enabled admin')
                    users[args.name]['disabled'] = True
                else:
                    password = getpass.getpass('New password: ')
                    if password != getpass.getpass('Confirm password: '):
                        raise ValueError('Passwords do not match')
                    users[args.name]['password'] = password_hash(password)
                atomic_json(path, users)
                PlatformStore(args.data_dir).event(action=args.command, actor='offline_admin', target=args.name)
                print('User updated.')
        elif args.command == 'backup':
            print(json.dumps(backup(args.data_dir, args.output), indent=2))
        elif args.command == 'restore':
            print(json.dumps(restore(args.archive, args.target), indent=2))
        elif args.command == 'audit-verify':
            report = PlatformStore(args.data_dir).verify(); print(json.dumps(report, indent=2))
            if not report['valid']:
                raise SystemExit(1)
        else:
            report = doctor(args.data_dir); print(json.dumps(report, indent=2))
            if not report['ok']:
                raise SystemExit(1)
    except (OSError, ValueError, RuntimeError, sqlite3.Error, zipfile.BadZipFile) as exc:
        parser.exit(1, f'Administration failed: {exc}\n')


if __name__ == '__main__':
    main()
