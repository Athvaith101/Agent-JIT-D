"""Verify external invoice recordings without external writes."""
import argparse
import hashlib
import json
from pathlib import Path
from .compiler import compile_workflow
from .evidence_csv import load_evidence
from .executor import Executor
from .sdk import check_recording
from .services import RecordedServices


def recording_snapshot(case):
    payload = {k: case[k] for k in ('invoice_id', 'as_of', 'invoice', 'pages')}
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--recording', required=True)
    parser.add_argument('--authority')
    parser.add_argument('--source')
    parser.add_argument('--snapshot-only', action='store_true')
    args = parser.parse_args()
    case = json.loads(Path(args.recording).read_text(encoding='utf-8-sig'))
    check_recording(case)
    token = recording_snapshot(case)
    if args.snapshot_only:
        print(token)
        return
    class ExternalRecording(RecordedServices):
        def snapshot_token(self, invoice_id):
            return token if invoice_id == case['invoice_id'] else None

        def verification_evidence(self, invoice_id):
            return load_evidence(args.authority, invoice_id, token, args.source)
    manifest, _ = compile_workflow()
    svc = ExternalRecording(case)
    result = Executor(svc, strict=True).run(manifest, {k: case[k] for k in ('invoice_id', 'as_of')})
    print(json.dumps({'mode': 'read-only recording; ledger is in memory', 'outcome': result.outcome,
                      'halt': result.halt, 'assumptions': result.assumptions,
                      'external_writes': 0}, indent=2, default=str))
    raise SystemExit(0 if result.outcome == 'posted' else 2)


if __name__ == '__main__':
    main()
