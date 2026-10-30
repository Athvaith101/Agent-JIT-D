# Release verification — 29 October 2026

Release **2.1.0-studio**. Scope: a bounded invoice Agent Studio around the existing evidence-gated workflow engine.

| Check | Actual local observation |
|---|---|
| Automated tests | **243 passed**, zero failures, about 69 seconds, Linux Python 3.12 |
| Added Studio regressions | 33 tests including parameterized cases; the prior 210-test suite remains passing |
| Studio browser | Draft creation → 28-case validation → self-publication refusal → different reviewer publication → clean run → unit drift halt → schema-only counterexample → recorded-input impact → reviewer repair approval → correct retry → passport → UNKNOWN halt → edited draft loses validation eligibility → human-inclusive cost projection |
| Studio mobile | Viewer build/run controls disabled; no horizontal overflow in tested 390px Build and Runs views; no JavaScript page errors |
| Original lab browser | Existing clean/drift/proposal/separate-review/retry flow, operations view and mobile check still pass at /lab |
| Validation and integrity | Stale/foreign reports refused; immutable publication; policy upgrades require retest; unauthorized runtime change refused; altered run/output and passport chain detected |
| Repair promotion | Exact candidate retained; fresh strict evidence at proposal and approval; authority removal after proposal prevents promotion |
| Restore | Agent drafts, published versions, nested runtime state and passports preserved by offline backup/restore |
| Source hygiene | Secret scan clean; Ruff F821 passed; changed JavaScript syntax checks passed |
| Dependencies | Existing pinned closure unchanged; pip check passed; the prior 29 October dependency audit reported no known vulnerabilities |
| Model access | Preflight ran with zero provider calls and default-zero attempted-call ceiling. No paid inference was performed |

Machine-readable checks and Python/frontend SHA256 fingerprints are in `release-checks.json`. Dependency audit details remain
in `security/dependency-audit.json`. Screenshots were used for visual inspection but are not bundled. Browser roles were tested
in separate browser instances; no browser credentials/state are included in the ZIP.

## What these checks do not establish

Actual NVIDIA model contribution or usage on Nebius, Windows execution, Docker build/runtime, remote CI, public demo availability,
independent field generalization, a measured always-LLM baseline, net savings or customer ROI remain unverified. Model tests use
explicitly injected clients; their outputs are not labelled live provider evidence. The cost curve is an assumption-based calculator.
The schema-only comparison uses captured synthetic input and is not a real-agent benchmark.

The existing recovery studies remain historical synthetic evidence. A new builder does not establish semantic reuse superiority,
independent authority trustworthiness or research novelty. Source-policy hashes identify this build; older studies retain their
original scope. Read PLAN_REVIEW.md before using the expanded platform plan's absolute marketing claims.

This is one workspace/process and one fixed invoice family. It is not unrestricted agent synthesis, SSO/MFA, tenant isolation,
HA, immutable external auditing, production financial safety or enterprise certification. Inference caps count reserved attempts
in a data directory, not dollars or an account-wide balance. Retain original external billing/credit controls.

## 2.2 assurance update

Full Linux suite: 253 passed in 62.17 seconds. Added 10 planner/API tests covering all-obligation coverage, shared-check choice, budget bounds, unknown checks, no stale-evidence reuse and HTTP access. New planner is shadow only; no paid calls. See SEMANTIC_CHANGE_ASSURANCE.md.

## 2.3 visual builder update

276 Linux tests passed in 75.63 seconds; 23 new Canvas tests exercise all ten family lifecycles, graph gate bypasses, stale/snapshot evidence, immutable versions, separate review, credential non-persistence, exact cost calculation, actual-token/unknown-usage recording with an injected client, and baseline correctness. New desktop/mobile browser checks passed with no JS errors or horizontal mobile overflow. Original invoice Studio browser path also passed. No paid provider calls or Windows/Docker execution occurred. New templates are bounded JSON computations, not live external connectors. See VISUAL_BUILDER.md.

## 2.3.1 Nebius connection helper

This update adds an operator smoke command for the existing OpenAI-compatible Nebius client. The 2.3.0 automated/browser
verification above predates this helper. No live Nebius call or test run is claimed for 2.3.1; run the bounded command described
in `NEBIUS_SETUP.md` with your own account configuration before relying on the connection.


## 2.4 hybrid assurance update

289 Linux tests passed, including four tests for the preserved Nebius smoke helper's zero-call default, required configuration, endpoint restrictions and persistent attempted-call ceiling. Nine new controller tests cover baseline/CUSUM persistence, unknown-label exclusion, duplicate prevention, expected-risk eligibility, graph ranking, regime reset, one-time dispatch, automatic opt-in assistance with an injected client, no model-label learning and invoice integration. Both desktop/mobile browser workflows passed with no JS errors or horizontal overflow, including the missing-evidence/no-model check. No paid API call, Windows or Docker execution occurred. The authored simulation has development/held-out seeds; its request counts are not measured model usage or savings. See HYBRID_ASSURANCE.md.

## 2.5 selected design refresh

289 Linux tests passed in 72.99 seconds. The home page, mobile navigation/Escape dismissal, reduced-motion view, live system readiness and all workspace links passed browser checks without JS errors, failed HTTP responses or horizontal overflow. Native WebGL rendered successfully; CSS fallback is bundled. The visual builder drag/test/publish/run/block and original invoice repair/retry browser flows both passed. Design changes require no frontend build or remote assets. No paid model calls, Windows execution or Docker execution were performed. See DESIGN_SYSTEM.md.

## 2.5.1 pointer motion and responsive refinement

69 targeted regression tests passed. Browser checks verified actual shader pointer-uniform response, card tilt, magnetic CTA movement, reduced-motion/coarse-pointer behavior, 16px mobile input text and 44px navigation targets. All 36 combinations of nine widths and four routes had no horizontal page overflow. Visual builder and invoice Studio lifecycle browser flows passed. The previous 2.5 full suite result of 289 tests is retained as historical evidence, not reported as a new full-suite run. No paid API calls, Windows or Docker execution occurred.
