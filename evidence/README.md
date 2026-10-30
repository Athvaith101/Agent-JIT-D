# Live Nemotron evidence

**Status: no real Nemotron/Nebius run has been recorded in this repository.** The build environment had no API key.
Until you run the command below, every statement about Nemotron here is untested against the real service.

    export NEBIUS_API_KEY=...        # never commit
    export NEBIUS_MODEL_ID=...       # the exact model ID from your Nebius console
    python -m jitd.live --compiles 3

This writes `evidence/live_<UTC stamp>.json` (full manifests, rejections, run IDs, proposals, meter) and a `.md` summary.
Failures are kept: a model plan rejected by the allowlist/oracle, or a repair proposal that fell back to the deterministic
synthesizer, is the honest result. Each plan and proposal is labelled by source (`nemotron` vs deterministic fallback), and the
JSON has `nemotron_proposal_accepted` and `deterministic_fallback_accepted` per scenario so the two cannot be confused.
The key is never written; errors are sanitized. Commit the evidence files, quote them in the submission, and do not edit them.
