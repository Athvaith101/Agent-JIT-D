> Release 2.3 adds a separate visual workspace with ten bounded JSON templates. The invoice Studio retains its deeper recovery integration. See docs/VISUAL_BUILDER.md (or VISUAL_BUILDER.md from this directory) for current scope. Earlier sections below describe the original Studio.

# Review of the expanded JIT-D Platform plan

Decision: **proceed with the bounded Agent Studio; do not claim the entire vision is already implemented.**

The plan improves product coherence: users can create a supported procedure, test it, approve a version, inspect a blocked
run and recover it. That connects the existing recovery engine to a visible user job. The improvement is a stronger product
workflow and demonstration, not proof of research novelty, commercial readiness or hackathon ranking.

## What makes the project better

| Change | Practical benefit | Evidence needed |
|---|---|---|
| Saved drafts and explicit supported scope | Users can configure a procedure rather than only operate a prebuilt lab | Create, inspect and test a supported draft; refuse unsupported tasks |
| Validation tied to content and runtime policy hashes | Old approval cannot silently qualify changed content | Edit after testing; publication must require a current report |
| Immutable published base plus separately approved runtime repairs | History identifies what was published and what changed during recovery | Base remains unchanged; execution passport records actual runtime hash and repair review |
| Recorded-input impact preview | Reviewer can inspect output changes on retained examples | Captured inputs and actual replay results; disclose sample size and synthetic truth |
| Evidence Passport | A result carries its run/version/evidence/review provenance | Check output, run and manifest hashes and the receipt chain |
| Human-inclusive cost sensitivity | Review effort can overturn an attractive token-cost saving | Distinguish assumptions from measured usage and independently measured baseline cost |

## Claims that must change

1. **“Never let it silently post a wrong answer.”** This is not supported as a universal guarantee. The system blocks when
   its required configured evidence is UNKNOWN or INVALID. A correlated wrong provider/authority can still agree and be wrong.
   Say: **“Block outputs whose required evidence does not qualify, and make the acceptance basis inspectable.”**
2. **“The platform cannot overspend by design.”** An attempted-call ceiling is not a monetary ceiling, account credit check
   or account-wide budget. Failures, unknown usage, multiple data directories and restoring older counters matter. Keep the
   default zero and explicitly enable a small ceiling only after confirming available credits and top-up settings.
3. **“At a fraction of the cost.”** This requires a measured comparable baseline, adequate correctness, configured prices,
   verification overhead and human time. The release records model usage and provides a clearly labelled what-if curve;
   it does not claim observed customer savings or a measured break-even point.
4. **“Compile the successful Nemotron run.”** This studio maps a supported task to a fixed typed invoice template and bounded
   parameters. It is not arbitrary trace-to-code compilation. The existing compiler validates and attaches contracts to a
   supported workflow graph. Demonstrate actual trace learning before claiming it.
5. **Five Nemotron roles.** Role count is not evidence of model value. This release exposes Architect and Repairer calls;
   diagnosis, verification and execution are deterministic. Tracer and model Auditor roles remain proposed.
6. **“Class-winning entry.”** A working lifecycle and visible results improve the entry, but neither this document nor a test
   count establishes how it will rank. Actual NVIDIA/Nebius evidence and a complete accessible submission are still necessary.

## Implemented in this release

- Build/Test/Versions/Runs/Cost studio and the original lab at `/lab`.
- Multiple saved agents within **one USD invoice template family**, one workspace and one server process.
- Strict draft schema, conservative English task-to-template routing and explicit unsupported-task refusal.
- Bounded page parameter editing; fixed allowlisted tool graph and mandatory evidence policy.
- Twenty-eight fixed authored synthetic validation cases, draft/report/policy hashes, revision conflict checks and immutable publication.
- Builder, operator, reviewer, viewer and admin permissions. Named-user publication and repair approval require a different reviewer.
- Separate runtime per published version. Approved repairs advance the runtime revision without rewriting its published base.
- Counterfactual output-impact replay on the last twenty captured synthetic inputs. The replay is in memory, with no real write.
  It is not live shadow traffic or an independent truth source. Strict fresh checks remain a separate promotion requirement.
- Fresh strict candidate checks at proposal and approval time, plus the existing exact-candidate regression validation.
- Evidence passports for accepted and blocked runs, including run/output/manifest hashes, authority observations and approvals.
- A schema-only replay comparison against the selected saved strict run. Always-LLM and LLM-self-check results remain “not measured”.
- Architect/Repairer model receipts with raw output, model ID, usage and fallback attribution. No paid model result is bundled.
- Role-specific model ID configuration and a cost sensitivity curve whose inputs are explicitly assumptions.

## Proposed, not shipped

General graph synthesis; arbitrary editable bindings/tools; learning executable code from arbitrary traces; multiple domain
families; scheduling; model-auditor routing; prompt/result caching; live shadow/canary deployment; drift forecasting; independent
field evaluation; a full real-agent benchmark; measured savings and production financial writes. There are no pretend working
buttons for these features in the demo path.

The existing negative recovery findings remain: ordinary dependency replay can match or outperform semantic reuse in this
workflow. Adding a builder does not change that result or demonstrate algorithmic superiority.

## Next evidence priorities

First collect real configured Nemotron draft/repair outcomes, including rejected proposals and failures. Then test a frozen,
independently authored example with independently controlled authority observations. Measure human effort and a comparable
baseline before making savings claims. Finally test the downloaded ZIP on Windows and complete public repository, demo and
narrated video access. Use the recorded release verification for the checks actually performed here.
