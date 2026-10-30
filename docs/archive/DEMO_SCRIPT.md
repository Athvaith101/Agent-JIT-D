> Historical AAIR release notes. For the integrated release see P0_P2_VERIFICATION.md and RELEASE_P0_P2.md.

# Three-minute AAIR demonstration

**Opening:** “Repeated reasoning is expensive. Blind replay is cheap but can silently become wrong. JIT-D compiles the procedure,
records what must remain true, and checks those assumptions before accepting the result.”

1. Home: show the positioning and synthetic-services badge. Open Execution.
2. Run a clean invoice. Point to the four assumption records, the independent monetary references, source IDs and timestamps.
3. Apply Dollars → cents. Run again. Explain that the schema still accepts numbers, but reconciliation contradicts the old unit assumption.
4. Diagnose. Show that the check fires at reconcile while normalize_amount owns the broken conversion assumption.
5. Try a wrong repair if time allows. Its drift validation fails. Propose the correct bounded repair; inspect the diff and drift/regression validation; approve.
6. Retry the same invoice. Point to four reused safe checkpoints and four re-executed nodes. Every required assumption is verified again before the ledger output.
7. Select Authority unavailable and run another invoice. Explain that UNKNOWN does not become VALID just because the schema and arithmetic agree.
8. Performance: show safety, correct outputs, runtime and modelled cost together. Say explicitly that Nemotron/billing evidence requires live credentials;
   ordinary data-dependency replay can match AAIR's slice on this small graph.

**Close:** “The target is lower total cost per correct workflow. We keep false blocks, missing evidence and cases where AAIR loses visible.”

The legacy correlated-blind-spot button is a deliberately labelled comparison that bypasses the strict gate. It must not be presented as the strict AAIR path.
The prototype's provider and independent authority are both simulated from fixture truth; no production financial integration is claimed.
