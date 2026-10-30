# Start here — Windows PowerShell

Extract the ZIP completely and open PowerShell **inside its `jitd` folder**, where `requirements.lock` is visible.
Use Python 3.12. No BAT file or activation script is needed.

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.lock
.\.venv\Scripts\python.exe -m jitd.launch
```

Open **http://127.0.0.1:8000**. The new home links to the visual builder at **/builder** and invoice Agent Studio at **/studio**. The original workflow lab is at **/lab**, and system controls
are at **/operations**. This local sandbox requires no account and disables inference by default.

## First agent: complete offline demonstration

1. Open **/studio → Build:** keep the supported invoice task, choose a name and page bound, then create the typed draft. Inspect the actual steps.
2. **Test:** run validation. Inspect the 28 fixed synthetic cases and the report's draft hash.
3. **Versions & review:** publish the tested draft. Local sandbox permits same-person approval and labels it accordingly.
4. **Open runtime:** run a clean invoice; inspect its required evidence and Evidence Passport.
5. **Drift Lab:** select dollars → cents, apply the environment, then run another invoice. Acceptance must halt.
6. Compare the selected saved strict run with schema-only replay. The comparison uses captured synthetic input; it is not an LLM benchmark.
7. Propose a bounded repair. Inspect the candidate, invalidated region, captured-input impact and strict validation.
8. Approve and revalidate, then retry the selected blocked invoice. The output should match synthetic truth.
9. Change authority evidence to unavailable, apply, and run again. UNKNOWN must still block acceptance.
10. Return to Build, edit and save the draft. Its old test report no longer permits publication; the published base stays unchanged.

## Enter a model key through the terminal

Stop with Ctrl+C. Confirm your Nebius promotional balance and top-up settings before enabling inference.

```powershell
$env:NEBIUS_MODEL_ID = "COPY_THE_EXACT_NVIDIA_MODEL_ID_FROM_NEBIUS"
$env:JITD_MAX_MODEL_CALLS = "12"
$env:JITD_MODEL_MAX_OUTPUT_TOKENS = "4096"
.\.venv\Scripts\python.exe -m jitd.launch --ask-api-key
```

The hidden prompt does not save or display the key. In Build, explicitly select the Nemotron option before creating a new
agent, or choose Propose with Nemotron on a blocked run. Inspect actual receipts in Cost & model usage. Deterministic fallback
is labelled separately. Opening Studio does not call the model. Twelve is a total attempted-call ceiling in this data directory,
not a billing cap or a guarantee of free usage. Failures remain counted.

Optional model IDs for the two implemented model roles:

```powershell
$env:JITD_ARCHITECT_MODEL_ID = "COPY_EXACT_ACCOUNT_VISIBLE_MODEL_ID"
$env:JITD_REPAIR_MODEL_ID = "COPY_EXACT_ACCOUNT_VISIBLE_MODEL_ID"
```

Both default to NEBIUS_MODEL_ID. Different role IDs are configuration, not measured proof that tier routing saves money.

## Named-user profile

Stop the server and create users with unique passwords of at least fourteen characters:

```powershell
.\.venv\Scripts\python.exe -m jitd.admin user-add admin --role admin
.\.venv\Scripts\python.exe -m jitd.admin user-add builder --role builder
.\.venv\Scripts\python.exe -m jitd.admin user-add operator --role operator
.\.venv\Scripts\python.exe -m jitd.admin user-add reviewer --role reviewer
.\.venv\Scripts\python.exe -m jitd.launch --profile enterprise
```

Builder creates/tests drafts; reviewer publishes a draft last edited by someone else; operator executes and proposes repairs;
a different reviewer approves them. Admin can build and operate but still cannot approve their own work.
Use **different browser profiles or different browsers**, for example Chrome and Edge, to keep identities separate. Two
incognito windows from one profile may share authentication state. No default passwords are supplied.

Read `docs/OPERATIONS.md` for backup/restore and deployment. Read `docs/STUDIO.md` for behavior and limits,
`docs/PLAN_REVIEW.md` for the proposal assessment, and `docs/RELEASE_VERIFICATION.md` for actual checks.

### Inspect semantic change assurance

In Studio → Runs, select a saved run and click **Plan revalidation**. Set budget to 0 to see uncovered obligations. This read-only plan cannot authorize acceptance. The normal Run action still enforces fresh evidence.

### Visual builder and pasted API keys (2.3)

Open http://127.0.0.1:8000/builder. Select a family, load a template, drag/reorder blocks, then Test & save draft. Under Test & operate publish the passing report, load a fresh example and run. Enterprise publication requires a different reviewer.

Models & keys accepts Nebius or NVIDIA keys in a password field, held only in server memory. No call is made when connecting. See docs/VISUAL_BUILDER.md before enabling the attempted-call ceiling. Cost evidence distinguishes usage-derived costs from projected N-run savings.

### Hybrid controller (2.4)

Open /builder → Hybrid assurance after running an agent. Inspect signals and recommendations. Model assistance starts disabled; consult docs/HYBRID_ASSURANCE.md before enabling it. Missing evidence always blocks. Existing repair review remains mandatory.

For a one-request connection check before starting the app, see [Nebius Token Factory setup](docs/NEBIUS_SETUP.md). It includes
`python -m jitd.nebius_smoke`, which uses a small output limit and consumes one configured attempt.


### New home and workspace links (2.5)

After launch, open http://127.0.0.1:8000/ for the redesigned home. Choose **Build your agent** for /builder or **Studio** for /studio. The existing model setup, testing, hybrid policy and review instructions still apply. No Node/npm build is needed.
