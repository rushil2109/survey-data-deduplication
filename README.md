# Survey Data Deduplication via GraphQL

Small Python CLI that reads survey responses from JSON, authenticates with a local or remote API, removes responses already present in GraphQL, and uploads new responses in batches. The `/auth/token` REST request uses Python's standard library; GraphQL queries and mutations use the `gql` client with its requests transport instead of manually managing GraphQL HTTP payloads.

## Setup

The Makefile provides shortcuts for setup and common commands:

```bash
make setup
make test
```

For API commands, `make setup` also creates the local environment file if it is missing:

```bash
make setup
```

Update `.env` with the API URL and credentials. Make loads this file automatically for `make run` and `make mock-server`, and never overwrites an existing file.

Without Make, the equivalent manual setup is:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

The dependency pins support Python 3.7, which is useful for the legacy interpreter used in this workspace.

## Run the local mock

In one terminal:

```bash
make mock-server
```

The mock uses `demo-client` / `demo-secret`, considers one response ID pre-existing, and rejects the example's `33333333-3333-3333-3333-333333333333` ID to demonstrate batch failure logging.

In another terminal:

```bash
make run INPUT=examples/responses.json
```

Make passes `API_BASE_URL`, `CLIENT_ID`, `CLIENT_SECRET`, and related settings from `.env` to the CLI. The mock server uses `demo-client` / `demo-secret` by default.

Use `--query-batch-size` and `--upload-batch-size` to change batch sizes. The defaults are 100 because the API specification does not define server limits.

Run tests with `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q` if your machine has globally installed pytest plugins with incompatible dependencies.

## Input format

The JSON file may contain either an array or an object with a `responses` array. Each response requires `responseId`, `surveyId`, `answers`, and `submittedAt`, matching `CreateSurveyResponseInput` in the GraphQL schema.

Malformed records are skipped and logged. Upload failures are logged per batch and do not stop later batches. Authentication failure is fatal. A successful process exits with code 0 even when upload batches fail, as requested.

## Commentary

Duplicate detection uses exact `responseId` equality between the input and the API query results. The client uses one bearer token per execution, finite request timeouts, and retries transient transport errors and HTTP 429/5xx responses. GraphQL errors are treated as failed operations. There is no per-record retry or token refresh logic because those were outside this exercise's scope.

This solution was produced with AI assistance in this Copilot session. AI was used to structure the project, draft the client and mock server, and suggest focused tests; the resulting behavior was validated locally with pytest and an end-to-end mock-server run.

Given more time, I would add per-record retry or isolation for partially rejected mutation batches, token refresh, persistent progress, and stronger schema-level validation.