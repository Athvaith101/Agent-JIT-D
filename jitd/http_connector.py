"""GET-only snapshot capture and separately configured authority integration."""
import hashlib
import ipaddress
import json
import time
from urllib.parse import urlsplit
import httpx
from .evidence_csv import evidence_record
from .sdk import check_recording
from .services import RecordedServices


class ConnectorError(ValueError):
    pass


def origin(url, allow_local_http=False):
    u = urlsplit(url)
    if u.username or u.password or u.query or u.fragment or not u.hostname:
        raise ConnectorError('Base URL must have a host and no credentials, query or fragment')
    local = u.hostname == 'localhost'
    try:
        local = local or ipaddress.ip_address(u.hostname).is_loopback
    except ValueError:
        pass
    if u.scheme != 'https' and not (u.scheme == 'http' and local and allow_local_http):
        raise ConnectorError('HTTPS required; loopback HTTP needs explicit local-test opt-in')
    return u.scheme, u.hostname.lower(), u.port or (443 if u.scheme == 'https' else 80)


class ReadClient:
    def __init__(self, base_url, token=None, *, allow_local_http=False, timeout=5, transport=None):
        self.origin = origin(base_url, allow_local_http)
        self.base_url = base_url.rstrip('/')
        self.client = httpx.Client(timeout=timeout, follow_redirects=False, trust_env=False,
                                   headers={'Authorization': 'Bearer '+token} if token else {}, transport=transport)
        self.calls = 0
        self.latency_ms = 0.0

    def close(self):
        self.client.close()

    def get(self, path, params=None):
        started = time.perf_counter()
        self.calls += 1
        try:
            with self.client.stream('GET', self.base_url+path, params=params) as response:
                if response.status_code != 200:
                    raise ConnectorError('Read endpoint returned HTTP '+str(response.status_code))
                if response.headers.get('content-type','').split(';')[0].strip() != 'application/json':
                    raise ConnectorError('Read endpoint must return application/json')
                raw = bytearray()
                for chunk in response.iter_bytes():
                    raw.extend(chunk)
                    if len(raw) > 2 * 1024 * 1024:
                        raise ConnectorError('Read response exceeds 2 MiB')
                value = json.loads(raw)
                if not isinstance(value, dict):
                    raise ConnectorError('Read response must be a JSON object')
                return value, response.headers.get('x-jitd-snapshot')
        except (httpx.HTTPError, UnicodeError, json.JSONDecodeError):
            # Never return URLs, headers, response bodies or client exception text.
            raise ConnectorError('Read request failed or returned invalid JSON') from None
        finally:
            self.latency_ms += (time.perf_counter()-started)*1000


class HTTPProvider(ReadClient):
    def capture(self, invoice_id, as_of, max_pages=20):
        invoice, snapshot = self.get('/invoice', {'invoice_id': invoice_id, 'as_of': as_of})
        if not snapshot or len(snapshot)>256:
            raise ConnectorError('Provider must supply a bounded immutable X-JITD-Snapshot token')
        pages, cursor = {}, None
        for _ in range(max_pages):
            key = cursor or ''
            if key in pages:
                raise ConnectorError('Cyclic payment cursor')
            params = {'invoice_id': invoice_id, 'as_of': as_of, 'snapshot': snapshot}
            if cursor is not None:
                params['cursor'] = cursor
            page, version = self.get('/payments', params)
            if version != snapshot:
                raise ConnectorError('Provider snapshot changed during capture')
            if 'next_cursor' not in page:
                raise ConnectorError('Explicit pagination completion required')
            pages[key] = page
            cursor = page['next_cursor']
            if cursor is None:
                break
            if not isinstance(cursor,str) or not cursor:
                raise ConnectorError('Invalid payment cursor')
        else:
            raise ConnectorError('Payment page limit reached')
        case = {'invoice_id': invoice_id, 'as_of': as_of, 'invoice': invoice, 'pages': pages,
                'expected': 'unknown', 'provider_snapshot': snapshot}
        check_recording(case)
        ids=[p['payment_id'] for page in pages.values() for p in page['payments']]
        if len(ids)!=len(set(ids)):
            raise ConnectorError('Duplicate payment identity across pages')
        return case


class HTTPAuthority(ReadClient):
    def evidence(self, invoice_id, snapshot, source):
        self.last_record = None
        row, _ = self.get('/evidence', {'invoice_id': invoice_id, 'snapshot': snapshot})
        self.last_record = row
        raw=json.dumps(row,sort_keys=True,separators=(',',':')).encode()
        return evidence_record(row,invoice_id,snapshot,source,hashlib.sha256(raw).hexdigest())


class ShadowServices(RecordedServices):
    def __init__(self, case, authority, source):
        super().__init__(case)
        self.authority, self.source = authority, source

    def snapshot_token(self, invoice_id):
        return self.case['provider_snapshot'] if invoice_id == self.case['invoice_id'] else None

    def verification_evidence(self, invoice_id):
        return self.authority.evidence(invoice_id, self.snapshot_token(invoice_id), self.source)
