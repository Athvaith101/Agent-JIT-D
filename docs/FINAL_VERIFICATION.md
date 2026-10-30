# Final verification — Agent JIT-D 2.6.0-deployment

Checked locally on 30 October 2026. This report supersedes older verification notes for the changes in this release.

- Installed the exact pinned Python dependency closure successfully in an isolated environment; pip check passed.
- Full suite with JITD_MAX_MODEL_CALLS=0 in the parent environment: **292 passed in 66.46 seconds**. Tests set their own model budget and isolate persistent budget state.
- Secret scanner: clean.
- JavaScript syntax checked for updated assets; Python modules compiled successfully.
- Chromium against the actual local FastAPI backend: all seven guided lifecycle steps passed, including reviewed repair, accepted retry and missing-evidence block. No paid inference dispatched. No browser JavaScript errors observed.
- Studio and Builder: local Geist font active; guide is an inline nonblocking section; SVG cross bounding boxes fully inside circular buttons, horizontal center error **0 px** at 1440 px viewport. No horizontal document overflow at 390 px.
- Recorded provider replay: correctly reports no bundled provider reports. Does not substitute fake-client receipts or fabricated token savings.
- Local Vercel entry smoke: public health, protected page/API behavior, styled 401 response, authenticated Home/Demo/Studio/Builder/System pages, bundled font and social image, explicit font CSP and ephemeral host metadata all passed. This is not a hosted Vercel test.
- Existing evidence gates and backend validation/reviewer policies remain active during the guided flow. Enterprise reviewer restrictions are not bypassed by the demo.

Not executed: paid Nebius inference, N-case live baseline, Docker image build/runtime, Windows run, remote CI, Render/Vercel hosted cold starts and SSE/network smoke. No cloud deployment was created. Use DEPLOYMENT.md and docs/JUDGE_TESTING.md to complete those owner-account steps.

Render configuration uses a single persistent paid service, a disk, one worker and a persistent attempted-call budget. Vercel is restricted to zero-call ephemeral preview. UI model keys remain process-memory only even on Render. The runtime is a bounded prototype, not a multi-tenant production financial service.
