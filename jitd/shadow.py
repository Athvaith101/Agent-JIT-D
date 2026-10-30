"""Read-only HTTP shadow verification: provider capture -> authority -> strict execution."""
import argparse
import json
import os
import time
from .compiler import compile_workflow
from .executor import Executor
from .http_connector import HTTPProvider, HTTPAuthority, ShadowServices, ConnectorError
from .schemas import SchemaError


def shadow_run(provider, authority, invoice_id, as_of, source, *, export_case=None, author='local-operator', real_data=False):
    if provider.origin == authority.origin:
        raise ConnectorError('Provider and authority require separately configured origins')
    if os.getenv('JITD_AUTHORITY_CSV'):
        raise ConnectorError('Unset JITD_AUTHORITY_CSV before HTTP authority verification')
    started=time.perf_counter()
    case=provider.capture(invoice_id,as_of)
    services=ShadowServices(case,authority,source)
    manifest,_=compile_workflow()
    # Capture already acquired and checked the complete declared page chain.
    manifest.step_for_op('payment.list').params['max_pages']=len(case['pages'])
    result=Executor(services,strict=True).run(manifest,{'invoice_id':invoice_id,'as_of':as_of})
    if export_case:
        from pathlib import Path
        from .integrate import recording_snapshot
        bundle={'recording':case,'authority':getattr(authority,'last_record',None),'source':source,
                'provenance':{'author':author,'collection_method':'GET-only version-bound HTTP capture',
                              'real_data':real_data,'independent_authority':True,'snapshot_kind':'provider_version',
                              'recording_sha256':recording_snapshot(case)}}
        target=Path(export_case);target.parent.mkdir(parents=True,exist_ok=True)
        target.write_text(json.dumps(bundle,indent=2,default=str),encoding='utf-8')
    return {'mode':'HTTP read-only shadow; ledger is in memory', 'outcome':result.outcome,
            'halt':result.halt,'assumptions':result.assumptions,'external_writes':0,
            'snapshot':case['provider_snapshot'], 'captured_pages':len(case['pages']),
            'provider_gets':provider.calls,'authority_gets':authority.calls,
            'network_ms':round(provider.latency_ms+authority.latency_ms,3),
            'total_ms':round((time.perf_counter()-started)*1000,3)}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('provider-url','authority-url','invoice-id','as-of','source'):
        parser.add_argument('--'+name,required=True)
    parser.add_argument('--allow-local-http',action='store_true')
    parser.add_argument('--case-out',help='Export captured case and authority observation for Pilot import')
    parser.add_argument('--author',default='local-operator')
    parser.add_argument('--real-data',action='store_true',help='Declare actual authorized source data; not independently certified')
    args=parser.parse_args()
    provider=authority=None
    try:
        provider=HTTPProvider(args.provider_url,os.getenv('JITD_PROVIDER_TOKEN'),allow_local_http=args.allow_local_http)
        authority=HTTPAuthority(args.authority_url,os.getenv('JITD_AUTHORITY_TOKEN'),allow_local_http=args.allow_local_http)
        report=shadow_run(provider,authority,args.invoice_id,args.as_of,args.source,export_case=args.case_out,author=args.author,real_data=args.real_data)
        code=0 if report['outcome']=='posted' else 2
    except (ConnectorError,SchemaError,ValueError):
        report={'outcome':'input_or_capture_error','external_writes':0,
                'reason':'Capture/configuration invalid; check endpoint contract, identities, snapshot and source.'}
        code=2
    finally:
        if provider: provider.close()
        if authority: authority.close()
    print(json.dumps(report,indent=2,default=str))
    raise SystemExit(code)


if __name__=='__main__':
    main()
