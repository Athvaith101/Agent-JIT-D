# HTTP integration verification

Full suite: 152 passed in 46.45 seconds, Linux Python 3.12.
Twenty HTTP tests cover local socket requests, capture, pagination, version consistency, duplicate payments, identity mismatches, authority freshness/source/amount/version failures, malformed/unavailable/redirected evidence, token separation, URL configuration and timeout sanitization.
Nine prior CSV integration tests remain passing. Secret scan clean; new modules compile and CLI help runs.
No real provider account, independent field dataset, Windows runtime, external writes or live Nemotron evaluation was exercised.
UI is unchanged and retains synthetic services. Existing benchmark JSON files retain historical source fingerprints.
See HTTP_INTEGRATION.md for Windows commands and the adapter contract.
