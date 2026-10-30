# Agent JIT-D --- Redesign Plan & Obsidian × NVIDIA Green Design System

**Date:** 26 October 2026\
**Status:** Agreed design direction; implementation and experimental
claims require validation.\
**Tagline:** **Reason once. Verify what matters. Recover cheaply.**

## 1. Executive decisions

-   **Project:** Continue Agent JIT-D; do not restart from scratch.
-   **Problem:** Repeated LLM planning is expensive; blindly replaying
    compiled workflows can silently fail when an API's meaning changes
    but its schema does not.
-   **Core solution:** **Assumption-Aware Incremental Recompilation
    (AAIR)** --- record semantic assumptions, independently verify them,
    trace invalidation through dependent operations, selectively repair
    and re-execute, and independently verify the result.
-   **Main metric:** **Total cost per correct workflow**, not just speed
    or number of LLM calls.
-   **Interface:** **Obsidian × NVIDIA Green**, premium, minimal,
    precise and focused on real execution evidence.
-   **Scope:** No new GNN, world model, extra AI architecture,
    workflow-domain expansion, or decorative features. Keep the existing
    experimental GNN isolated from the critical path.
-   **Novelty:** AAIR is a *proposed* contribution. Related compiler,
    contract, verification, and incremental-computation research exists.
    Novelty must be established through prior-art review and benchmarks,
    not asserted.

## 2. What we are solving

A Nemotron agent may repeatedly plan the same business workflow.
Compiling a successful trace into a typed, deterministic DAG avoids
repeated planning. But replay can be incorrect if external semantics
drift while JSON schemas remain unchanged.

**Target drift examples:** dollars → cents; inclusive → exclusive date
filters; enum remapping; timestamp meaning/order changes; truncated
pagination; correlated failures; missing independent evidence.

**Correctness rule:** Never trade undetected incorrect outputs for
cheaper execution. An unverified assumption is **UNKNOWN**, not
automatically valid. A safe halt is preferable to a falsely verified
answer.

## 3. Updated architecture

``` text
NVIDIA Nemotron → Workflow discovery → Typed DAG compiler
                                     ↓
                   Compiled DAG + Assumption Registry
                   + provenance and dependency links
                                     ↓
                            Deterministic replay
                                     ↓
                   Independent semantic verification
                                     ↓
                ┌───────────────┴────────────────┐
             VERIFIED                       INVALID / UNKNOWN
                ↓                                ↓
           Accept output               Identify assumption
                                                 ↓
                                       Dependency slicing
                                                 ↓
                                      Selective repair and
                                        downstream replay
                                                 ↓
                                        Re-verification
                                                 ↓
                                      Accept / Escalate /
                                           Safe halt
```

### Keep

-   Nemotron workflow discovery and bounded repair reasoning.
-   Typed DAG compiler, deterministic replay, checkpoints and persisted
    traces.
-   FastAPI backend and existing React frontend.
-   Independent guards, reconciliation checks, regression tests and
    safe-halt policy.

### Strengthen

1.  **Assumption Dependency Graph (ADG):** Attach contracts to relevant
    operations. Store assumption ID, semantic contract, evidence source,
    affected consumers, verification timestamp, and status (`VALID`,
    `INVALID`, `UNKNOWN`).
2.  **Independent verification:** Use trusted unit contracts,
    independent reconciliations, cross-service consistency and business
    invariants. Do not count two checks against the same faulty source
    as independent evidence.
3.  **Selective recovery:** Invalidate affected operations and derived
    values, retain only safe checkpoints, propose a bounded patch,
    re-execute the necessary dependency closure, and verify the output
    again.
4.  **Cost-aware escalation:** Deterministic retry → localized repair →
    full regeneration → safe halt/human review. Minimize **expected
    total safe recovery cost**, not merely number of changed nodes.
5.  **Audit policy:** Keep simple fixed-rate auditing as a strong
    baseline; only retain adaptive auditing if it beats that baseline at
    comparable correctness.

### Example: silent unit change

Initial `order.amount = 2500` means **USD 2,500**. Later
`order.amount = 250000` means **250,000 cents**, but the JSON type stays
numeric. A recorded contract alone cannot detect this. A genuinely
independent unit source or reconciliation must contradict the old
assumption. Then AAIR invalidates the affected calculations, repairs the
conversion, replays dependent operations and re-verifies the result. If
evidence is unavailable, it escalates or halts safely.

## 4. Research foundation and positioning

  -----------------------------------------------------------------------
  Existing research approach          Use in Agent JIT-D
  ----------------------------------- -----------------------------------
  Trace compilation / partial         Convert successful agent reasoning
  evaluation                          into reusable execution

  Design by Contract                  Express semantic expectations

  Data provenance / dependency graphs Link assumptions to consumers and
                                      derived outputs

  Runtime verification / independent  Detect silent semantic violations
  reconciliation                      

  Program slicing / incremental       Restrict recomputation to affected
  computation                         dependencies

  Cost-sensitive decision-making      Select verification and recovery
                                      tiers
  -----------------------------------------------------------------------

**Research hypothesis:** Explicit semantic-assumption dependencies can
enable equally safe, more targeted recovery than conventional
data-dependency invalidation, lowering cost per correct workflow under
semantic drift.

**Do not claim** that workflow compilation, semantic contracts, or
selective repair are new in isolation. Review close prior art before
submission.

## 5. Final development phases

  -----------------------------------------------------------------------
  Phase                   Work                    Exit evidence
  ----------------------- ----------------------- -----------------------
  **R1 --- Audit**        Inspect latest working  Reproducible baseline
                          checkpoint, compiler,   and precise gap list
                          guards, repair paths,   
                          tests, telemetry        

  **R2 --- ADG**          Add assumption          Registry and graph
                          contracts, evidence     tests; unsupported
                          provenance, dependency  contracts marked
                          links, invalidation     UNKNOWN
                          rules                   

  **R3 --- Verification** Improve independent     Detection, false-alarm,
                          semantic checks         correlated-failure,
                                                  missing-evidence tests

  **R4 --- Repair**       Assumption-aware        Verified selective
                          slicing, safe           recovery; no stale
                          checkpoint reuse,       downstream results
                          bounded patching        

  **R5 --- Benchmark**    Real Nemotron calls and Actual tokens, latency,
                          fair baseline           correctness and cost
                          comparisons             estimates

  **R6 --- Demo**         Integrate actual traces Reproducible end-to-end
                          into the existing UI;   demo
                          package deployment      
  -----------------------------------------------------------------------

**Indicative schedule:** 12--20 focused days, dependent on code quality,
API access and failures found. This supersedes the earlier open-ended
O/P feature roadmap.

### Required benchmark baselines

1.  Repeated Nemotron reasoning.
2.  Cached/reusable agent execution.
3.  Deterministic workflow with ordinary validation.
4.  Compiled workflow with full regeneration after failure.
5.  **Agent JIT-D with AAIR**.

Use identical workloads, drift injections, ground truth and accounting.
Test stable runs, known and held-out semantic drift, simultaneous
failures, correlated failures and absent verification evidence. Report
where AAIR **loses**, not just where it wins.

**Primary metric:**
`Total cost per correct workflow = attributable planning + compilation + execution + verification + repair cost / correctly completed workflows`.
Also report silent-error rate, token count, latency, detection delay,
false alarms, recovery cost, and safe-halt rate. Distinguish estimated
API pricing from measured provider billing.

### Go/no-go rules

-   No correctness regression is acceptable merely for lower cost.
-   UNKNOWN evidence never silently becomes VERIFIED.
-   If AAIR fails against conventional validation/recovery, diagnose and
    fix the mechanism before adding features.
-   Keep the GNN as optional research only unless it shows a
    reproducible held-out advantage.

------------------------------------------------------------------------

# 6. Complete interface palette --- Obsidian × NVIDIA Green

**Art direction:** premium AI infrastructure console, calm and
technically credible. Aim for **90% neutral surfaces / 10% accent
color**. Green highlights execution and primary actions; distinct status
colors convey verification state.

## 6.1 Foundation, surfaces and typography

  Design token         Hex         Usage
  -------------------- ----------- -----------------------------
  `--bg-canvas`        `#0B0F0C`   Primary obsidian background
  `--bg-sidebar`       `#0E1410`   Sidebar / navigation
  `--bg-surface`       `#141B16`   Cards and panels
  `--bg-raised`        `#1B241E`   Popovers and raised panels
  `--bg-hover`         `#233026`   Hover surfaces
  `--bg-inset`         `#0A100C`   Code / logs / graph wells
  `--border-subtle`    `#263329`   Hairline dividers
  `--border-strong`    `#394A3D`   Emphasized borders
  `--text-primary`     `#F2F5EF`   Headings and main values
  `--text-secondary`   `#B8C5BA`   Body text
  `--text-muted`       `#91A294`   Labels and timestamps
  `--text-disabled`    `#647466`   Disabled UI only

## 6.2 Accent, semantic status and graph colors

  Design token            Hex           Usage
  ----------------------- ------------- -------------------------------
  `--accent-primary`      `#76B900`     NVIDIA green / primary action
  `--accent-hover`        `#8BCD19`     Hovered CTA
  `--accent-pressed`      `#5D9400`     Pressed CTA
  `--accent-soft`         `#213515`     Accent tint
  `--accent-border`       `#456F1C`     Accent border
  `--on-accent`           `#091006`     Text on bright green
  `--success`             `#5ED39A`     Independently verified
  `--success-soft`        `#153427`     Verified badge background
  `--warning`             `#F1BC67`     Unknown / degraded evidence
  `--warning-soft`        `#3A2B17`     Warning badge background
  `--danger`              `#FF7D78`     Invalid / failed
  `--danger-soft`         `#3D1F1E`     Error badge background
  `--info`                `#67D9C3`     Repaired / informational
  `--info-soft`           `#15352F`     Info badge background
  `--graph-edge`          `#526455`     Inactive dependency line
  `--graph-node`          `#202C23`     Standard graph node
  `--graph-node-border`   `#405445`     Node outline
  `--graph-active`        `#76B900`     Currently executing node
  `--graph-verified`      `#5ED39A`     Verified node
  `--graph-unknown`       `#F1BC67`     Uncertain node
  `--graph-invalid`       `#FF7D78`     Invalidated node
  `--graph-repaired`      `#67D9C3`     Selectively repaired region
  `--focus-ring`          `#A5E54B`     Keyboard focus
  `--overlay`             `#050A06CC`   Modal scrim
  `--chart-grid`          `#2C3A30`     Subtle chart grid
  `--chart-baseline`      `#B8C5BA`     Baseline series
  `--chart-jitd`          `#76B900`     JIT-D series
  `--chart-repair`        `#67D9C3`     Recovery series

## 6.3 CSS design tokens (copy directly)

``` css
:root {
  color-scheme: dark;
  --bg-canvas: #0B0F0C;
  --bg-sidebar: #0E1410;
  --bg-surface: #141B16;
  --bg-raised: #1B241E;
  --bg-hover: #233026;
  --bg-inset: #0A100C;
  --border-subtle: #263329;
  --border-strong: #394A3D;
  --text-primary: #F2F5EF;
  --text-secondary: #B8C5BA;
  --text-muted: #91A294;
  --text-disabled: #647466;
  --accent-primary: #76B900;
  --accent-hover: #8BCD19;
  --accent-pressed: #5D9400;
  --accent-soft: #213515;
  --accent-border: #456F1C;
  --on-accent: #091006;
  --success: #5ED39A;
  --success-soft: #153427;
  --warning: #F1BC67;
  --warning-soft: #3A2B17;
  --danger: #FF7D78;
  --danger-soft: #3D1F1E;
  --info: #67D9C3;
  --info-soft: #15352F;
  --graph-edge: #526455;
  --graph-node: #202C23;
  --graph-node-border: #405445;
  --graph-active: #76B900;
  --graph-verified: #5ED39A;
  --graph-unknown: #F1BC67;
  --graph-invalid: #FF7D78;
  --graph-repaired: #67D9C3;
  --focus-ring: #A5E54B;
  --overlay: #050A06CC;
  --chart-grid: #2C3A30;
  --chart-baseline: #B8C5BA;
  --chart-jitd: #76B900;
  --chart-repair: #67D9C3;
}
```

## 6.4 Usage rules

-   **Green:** primary CTA and active execution; **mint:** independently
    verified; **amber:** UNKNOWN / insufficient evidence; **coral:**
    INVALID / error; **cyan-teal:** repaired and re-executed.
-   Never indicate correctness through green color alone: show **status
    text, icon, evidence and timestamp**.
-   Use bright green sparingly; avoid neon glow and glowing borders
    around every card.
-   Use Inter or Geist for UI, JetBrains Mono or IBM Plex Mono for
    traces/metrics, with system fallbacks.
-   Spacing: 4 / 8 / 12 / 16 / 24 / 32 / 48 px. Cards: 10--14 px radius;
    controls: 8--10 px.
-   Prefer thin borders, calm whitespace and 150--250 ms transitions.
    Honor reduced-motion preferences.
-   Check contrast, keyboard focus, status labels and readability on
    smaller screens.
-   NVIDIA-associated color is a theme choice, **not a claim of NVIDIA
    endorsement**. Follow event brand rules for any logos.

## 6.5 Page design

**Home:** large hero --- **REASON ONCE. VERIFY WHAT MATTERS. RECOVER
CHEAPLY.** One-sentence explanation, **Run Demo** and **Explore
Architecture** actions. Minimal background graph, no fabricated live
metrics.

**Execution workspace:**

1.  **Workflow Graph:** typed DAG, assumptions, invalidation slice,
    reused checkpoints, selective repair.
2.  **Verification Console:** contract, independent evidence,
    VALID/INVALID/UNKNOWN state, reason and time.
3.  **Performance Comparison:** real tokens, latency, correct outputs,
    repair cost and baseline comparison.

**Demo narrative:** initial Nemotron reasoning → compile → deterministic
fast path → silent dollars-to-cents drift → independent detection →
affected-region highlight → selective repair → verified output →
measured cost comparison.

**UI boundary:** All status and metrics must come from actual backend
traces, not hardcoded demo results. Keep the existing functional
frontend; migrate styling incrementally.

------------------------------------------------------------------------

## 7. Implementation acceptance checklist

-   [ ] Latest working ZIP audited before changes; existing tests still
    pass.
-   [ ] Assumptions are explicit and linked to operation dependencies.
-   [ ] Independent evidence supports VALID; missing evidence yields
    UNKNOWN.
-   [ ] Targeted semantic drifts are detected or clearly documented as
    limitations.
-   [ ] Selective repair preserves only safe checkpoints and invalidates
    affected derived values.
-   [ ] Corrected output is independently re-verified.
-   [ ] Real Nemotron usage and cost assumptions are transparently
    logged.
-   [ ] JIT-D is evaluated against strong baselines on matched tasks.
-   [ ] Frontend consistently uses the complete Obsidian × NVIDIA Green
    token system.
-   [ ] Graph, console and metrics reflect real backend events.
-   [ ] Final demo is reproducible, technically defensible and free of
    unnecessary features.

**Final project positioning:** **Agent JIT-D --- Assumption-Aware
Incremental Recompilation for Reliable, Cost-Efficient AI-Agent
Workflows.**
