# Connect JIT-D to Nebius Token Factory

JIT-D already contains an OpenAI-compatible client for Nebius Token Factory in
`jitd/llm.py`. It sends chat-completion requests to the configured HTTPS base
URL, reads the API key and model ID from environment variables, records provider
usage when returned, and applies the configured attempted-call ceiling. The
deterministic workflow runtime does not receive the model client.

## 1. Create the provider credentials

In Nebius Token Factory, create an API key and choose a model available to your
account. Copy the model's exact ID from the Token Factory model catalog/account;
do not guess the model ID from a model family name. Nebius documents its Python
client using the `https://api.tokenfactory.nebius.com/v1/` OpenAI-compatible
base URL. See the [Token Factory API examples](https://docs.tokenfactory.nebius.com/api-reference/examples/batches)
and [custom model example](https://docs.tokenfactory.nebius.com/fine-tuning/deploy-custom-model).

## 2. Configure JIT-D locally

Copy `.env.example` to `.env` in the `jitd` project folder, then edit:

```dotenv
NEBIUS_API_KEY=your_actual_key
NEBIUS_BASE_URL=https://api.tokenfactory.nebius.com/v1/
NEBIUS_MODEL_ID=exact_model_id_from_your_account
JITD_MAX_MODEL_CALLS=1
JITD_MODEL_MAX_OUTPUT_TOKENS=16
```

Keep `.env` private. It is excluded from the release ZIP and should never be
committed or pasted into chat. The call limit counts attempts, including failed
requests. It is a safety ceiling, not a monetary cap. Check your Token Factory
balance and billing settings before calling a hosted model; the provider says
new accounts may receive initial credits, but usage is not guaranteed to be
free. See [Nebius billing](https://docs.tokenfactory.nebius.com/other-capabilities/billing).

## 3. Send one bounded connection check

From PowerShell, in the folder containing `requirements.lock`:

```powershell
.\.venv\Scripts\python.exe -m jitd.nebius_smoke
```

The command sends one real request with a small output-token limit. It prints
the model ID, response, provider-reported tokens when available, and latency;
it never prints or writes the API key. A failed or interrupted call still uses
one attempt from the configured ceiling.

If you do not want to store the key in `.env`, remove it there and use the hidden
prompt instead. Make sure the call ceiling is nonzero first:

```powershell
$env:JITD_MAX_MODEL_CALLS = "1"
.\.venv\Scripts\python.exe -m jitd.nebius_smoke --ask-api-key
```

## 4. Use the model from JIT-D

After the smoke check, set a small explicit ceiling for the app (for example,
12 attempts), then start JIT-D:

```powershell
$env:JITD_MAX_MODEL_CALLS = "12"
.\.venv\Scripts\python.exe -m jitd.launch
```

In Studio, choose **Nemotron** when creating a draft, or use **Propose with
Nemotron** on a blocked run. In Visual Builder, add a Nebius connection under
**Models & keys** and then choose **Draft with model**. Connection setup alone
does not make a provider request. Inspect **Cost & model usage** for receipts.

The smoke test confirms that credentials, the selected model ID, and the chat
completion route work together. It does not prove the model will produce a
valid JIT-D plan or repair; JIT-D's validators still decide whether a proposal
is acceptable.
