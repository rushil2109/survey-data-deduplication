# Survey Data Deduplication via GraphQL

A Python CLI that reads survey responses from a JSON file, authenticates with the API, removes responses already present in the database, and uploads the remaining new responses in batches.

## Approach and Logic

The program follows the five steps from the task specification in sequence:

**1. Read input data**
The CLI accepts a JSON file path. The file may be a bare array of response objects or an object with a `responses` key. Each record is validated for the required fields (`responseId`, `surveyId`, `answers`, `submittedAt`); malformed records are logged and skipped rather than aborting the run.

**2. Authenticate**
A single `POST /auth/token` request is made using Python's standard `urllib` (no extra dependency) with the `CLIENT_ID` and `CLIENT_SECRET` from the environment. The returned bearer token is attached to every subsequent GraphQL request. If authentication fails the process exits immediately — there is no point continuing without a valid token.

**3. Check for duplicates**
The `surveyResponsesByResponseIds` query is used to ask the API which of the input `responseId` values already exist. The input IDs are sent in batches (default 100) so that a large file does not produce a single oversized request.

**4. Deduplicate**
A **duplicate** is defined as any input record whose `responseId` exactly matches a `responseId` returned by the query above. The comparison is case-sensitive UUID string equality, matching the schema type. Records identified as duplicates are discarded; the remainder are the new responses to upload.

**5. Upload deduplicated data**
The new responses are sent via the `createSurveyResponses` mutation, again in batches (default 100). A failed batch is logged and skipped; later batches still run. The process exits with code 0 even if some upload batches fail, because partial success is still progress and the spec requested this behaviour.

## Batching rationale

The API specification does not define request size limits, so sending everything in a single request risks a timeout or silent rejection. Batching bounds each request to a known size and isolates failures: if one batch is rejected, only those records are affected. Both the query and upload batch sizes are configurable via `--query-batch-size` and `--upload-batch-size`.

## Error handling summary

| Scenario | Behaviour |
|---|---|
| Authentication failure | Fatal — exits with non-zero code |
| Malformed input record | Logged, record skipped |
| GraphQL query batch failure | Logged, those IDs treated as not-yet-checked (safe: may re-upload) |
| GraphQL mutation batch failure | Logged, batch skipped, later batches continue |
| GraphQL `errors` field present | Treated as a failed operation |
| Network transient error / HTTP 429 / 5xx | Retried with exponential back-off |

## AI tool usage

This solution was produced with AI assistance throughout the session using Claude Code (Anthropic). The workflow followed a structured planning and implementation cycle:

**1. Planning with OpenSpec (`/openspec-explore` and `/openspec-propose`)**
Before writing any code I used OpenSpec to explore the task specification and generate a structured change proposal. This surfaced ambiguities early — for example, whether batching was necessary, what "duplicate" should mean precisely, and how to handle partial upload failures — so those decisions were made explicitly rather than discovered mid-implementation.

**2. Stress-testing the plan with `/grill-with-docs` (Matt Pocock)**
Once the plan was drafted I ran `/grill-with-docs` against it. This skill interviews you relentlessly about your own design, forcing you to justify every assumption. It surfaced questions like: what happens if a query batch fails — do you treat those IDs as seen or unseen? What is the exit code contract when uploads partially fail? Working through those answers before touching code prevented several logic gaps.

**3. Plan review and sign-off**
After `/grill-with-docs` completed its edits to the plan I went through the updated plan myself, read through each proposed change, and finalized it before any code was written. This kept me in control of the scope and ensured I understood every decision before handing it to the implementation step.

**4. Implementation in phases with `/opsx:apply`**
With the plan stress-tested, implementation was done in phases using `/opsx:apply`. Each phase targeted a discrete slice of the work (auth, GraphQL client, deduplication logic, mock server, tests), keeping the context focused and making it easy to review each piece in isolation.

**4. Client and mock server**
AI drafted the `gql`-based GraphQL client, the `urllib` auth call, and the retry decorator. I reviewed each piece and adjusted timeouts, error classification, and the batch-splitting logic. AI also drafted the Flask mock server; I extended it to demonstrate duplicate detection (one pre-existing ID) and batch failure (one rejected ID).

**5. Testing**
Tests were verified two ways:
- `make test` — runs the pytest suite against the mocked client
- **Postman** — I manually exercised the auth endpoint and GraphQL query/mutation against the running mock server to confirm the HTTP contract matched the spec before wiring up the CLI end-to-end

**6. Makefile**
The Makefile was my own addition to simplify the setup and run experience. Manually typing `source .venv/bin/activate && python -m survey_deduplication.cli ...` with the right environment variables gets tedious quickly; `make setup`, `make test`, `make run`, and `make mock-server` reduce that to one command each and load `.env` automatically.

## Setup

```bash
make setup   # creates .venv, installs dependencies, creates .env if missing
make test
```

Update `.env` with the API URL and credentials. Make loads this file for `make run` and `make mock-server`.

Without Make:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

The dependency pins support Python 3.7.

## Run the local mock

In one terminal:

```bash
make mock-server
```

The mock uses `demo-client` / `demo-secret`, considers one response ID pre-existing, and rejects `33333333-3333-3333-3333-333333333333` to demonstrate batch failure logging.

In another terminal:

```bash
make run INPUT=examples/responses.json
```

Use `--query-batch-size` and `--upload-batch-size` to override the default of 100.

Run tests with `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q` if your machine has globally installed pytest plugins with incompatible dependencies.

## Input format

The JSON file may be an array or an object with a `responses` array. Each record requires `responseId`, `surveyId`, `answers`, and `submittedAt`, matching `CreateSurveyResponseInput` in the GraphQL schema.

## Future improvements

- **Per-record retry / batch isolation**: if a mutation batch is rejected, re-attempt each record individually to identify the specific failing record rather than dropping the whole batch.
- **Token refresh**: the current implementation uses one token per run. A long-running process with a large file could hit token expiry mid-upload; a refresh mechanism would handle this transparently.
- **Persistent progress**: for very large files, checkpointing which batches have already been uploaded would allow a failed run to resume rather than restart.
- **Server-side `UNIQUE` constraint**: the client-side duplicate filter is the primary guard, but a concurrent run or a bug could let a duplicate reach the mutation. Without a database-level `UNIQUE` constraint on `responseId`, that would result in a silent duplicate insert rather than a hard error.
- **Stronger input validation**: the current check is field-presence only. UUID format, ISO 8601 datetime format, and JSON shape of `answers` could be validated before making any network calls.
- **CSV support**: the spec mentions CSV as an alternative input format; the current implementation only handles JSON.
