# Latest redesign implementation

The active request is the AAIR and Obsidian/NVIDIA Green brief, preserved in `REDESIGN_SPEC.md`.
It supersedes the earlier commercial-product roadmap preserved in root `IMPROVEMENTS.md`.

See `AAIR_IMPLEMENTATION.md` for the full acceptance matrix. The core additions are explicit assumptions/provenance,
required-UNKNOWN safe halt, snapshot-checked incremental replay, independent output re-verification, attributed runtime
accounting, and matched safety/cost baselines. The frontend remains the supplied functional vanilla JavaScript app,
restyled with the complete requested token system and driven by actual backend traces.

Existing approvals, durable session history, audit export, rollback, idempotent synthetic retries and the read-only invoice
adapter remain available. No new workflow domain, GNN, world model or decorative feature system was introduced.

Real Nemotron experiments need user credentials. The release contains no fabricated model calls, field evidence,
measured customer savings, research-novelty claim or production-readiness claim.
