# JIT-D submission package

## Short description

JIT-D helps teams reuse a supported AI workflow without silently trusting assumptions that may have changed. A user builds and tests a bounded workflow, publishes an approved version, and runs it with deterministic contracts and evidence checks. If an invoice-unit drift appears, JIT-D blocks acceptance and can request a bounded diagnosis or repair. A repair must pass strict checks and reviewer approval. Missing or untrusted evidence remains a block.

**Tagline:** Reason once. Verify what matters. Recover cheaply.

## What is in this build

- Invoice Recovery Studio: draft, fixed-case test, review/publish, run, drift block, bounded proposal, strict validation, approval and retry.
- Visual Builder: ten bounded JSON workflow families, drag/drop typed blocks, model-assisted family selection, test/publish/run and usage receipts. The templates are local JSON computations with supplied evidence; they do not connect to live ERP/payment/logistics systems.
- Hybrid Assurance: deterministic checks, simple statistical change signals, a verified-predicate history proxy, graph-based cause ranking and optional gated diagnosis. The risk proxy is not calibrated error probability.
- UX changes included in this ZIP: Axion-inspired light/orange visual system, fluid navigation highlight, responsive layouts, first-visit guide with keyboard dismissal/reopen, page footers, subtle pointer motion, reduced-motion handling, and no orange cursor glow.
- Local Vercel FastAPI demo adapter and deployment instructions.

## Model use and observed local evidence

The user previously reported a Nebius connection using NVIDIA Nemotron 3 Super (`nvidia/nemotron-3-super-120b-a12b`). The historical user-session observations described an accepted Architect response (135 input / 77 output tokens; configured-rate estimate $0.0001098) and a matched always-model baseline (105 / 328 tokens; configured-rate estimate $0.0003267). These are user-session observations, not independently collected or embedded benchmark results. The rates were supplied in the UI; the dollar estimates are not provider invoices. The hybrid missing-evidence check dispatched zero model calls. A later recovery proposal was not approved because strict authority evidence was `UNKNOWN`.

Use those exact distinctions in the demo. Do not present synthetic benchmark results as real-world accuracy, claim universal safety, or claim measured cost savings from the projected cost curve. Ordinary dependency replay can match semantic reuse in the included experiments, and correlated provider/authority errors remain a limitation.

## Tester quick path

1. Sign in to the working demo or follow the local Windows guide. Use synthetic examples only.
2. Open Visual Builder. Load the invoice reconciliation template, validate it, and inspect its model receipt if the Architect call is enabled.
3. Publish a validated version, then run the clean example: it should be accepted with no model call.
4. Load the dollars-to-cents drift: it should halt. Remove evidence: it should still halt.
5. In Hybrid Assurance, request diagnosis on a missing-evidence run: `dispatched` should be false and acceptance should remain false.
6. Open Invoice Recovery Studio and follow Build → Test → Versions & review → Runs & recovery. A repair cannot be approved when fresh independent authority evidence is unavailable.
7. Inspect Cost & model usage for reported tokens and configured-rate estimates. Distinguish live provider receipts from synthetic fixtures and projected costs.

## Submission checklist

- Public source repository with the included open-source license and setup instructions.
- Working, judge-accessible demo or test build; private deployments need tester credentials and explicit run steps.
- Public YouTube demo under three minutes, showing the workflow running and clearly naming Nebius Token Factory and Nemotron.
- Submission description, track, feedback on the tools used, and an explanation of significant changes during the hackathon if this project existed beforehand.
- A tested Vercel URL if you choose Vercel. The ZIP itself does not create or verify a cloud deployment.

## Release evidence status

No raw live provider report is bundled. Previous user-session observations are not accepted here as reproducible benchmark evidence. `/demo` reports missing evidence explicitly; it never generates fictional receipts. Collect live reports and paired case usage before claiming measured savings. Public URL, judge credentials and video must be supplied by the deployment owner.
