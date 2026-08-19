## Context

The `SurveyApiClient` in `api_client.py` wraps two transport layers: a plain-stdlib REST call for `/auth/token` and a `gql` library client for GraphQL. The current GraphQL path creates a new `gql.Client` (and a new underlying `requests.Session`) on every call, bypasses the library's context-manager connection lifecycle, has no retry logic, and can surface `KeyError` instead of `ApiError` on unexpected API responses. Operation names are absent, making server-side tracing opaque. Tests validate only trivial helpers rather than the deduplication pipeline.

## Goals / Non-Goals

**Goals:**
- Reuse a single `gql.Client` (and its underlying HTTP session) across all GraphQL calls in one execution
- Apply the same retry/backoff policy to GraphQL calls as already exists for REST calls
- Convert all unhandled exceptions in `existing_response_ids` and `upload` to `ApiError`
- Name all GraphQL operations
- Achieve meaningful test coverage of `run()`, the error path, and retry behaviour
- Provide large example JSON files (100+ and 300+ records) to demonstrate batching

**Non-Goals:**
- Token refresh / multi-token support
- Per-record retry within a partially-rejected mutation batch (logged as TODO in README)
- CSV input support
- Changes to the mock server beyond what is needed to support new tests

## Decisions

### 1. Store `gql.Client` on the instance after `authenticate()`

**Decision:** After a successful `authenticate()`, construct `RequestsHTTPTransport` and `Client` once and store them as `self._gql_client`. `_graphql` opens the client as a context manager (`with self._gql_client as session`) for each call.

**Rationale:** `gql` 3.x manages one `requests.Session` per `RequestsHTTPTransport`. Re-creating it per call leaks connections and bypasses keep-alive. Storing it on the instance is the simplest fix without introducing a connection pool abstraction.

**Alternative considered:** Re-entering `__aenter__`/`__aexit__` every call with `asyncio` — rejected; async would require changing every call site and adds unnecessary complexity for a CLI tool.

### 2. Retry in `_graphql` using the same pattern as `_request`

**Decision:** Wrap the `session.execute()` call in the same `for attempt in range(self.retries + 1)` loop with `time.sleep(0.1 * (2 ** attempt))` backoff. Retry on `TransportQueryError` when the HTTP status is 429/5xx (detectable via the exception message or by catching `TransportServerError`).

**Rationale:** `_request` already has this; symmetric retry policies are easier to reason about. The `gql` library raises `TransportServerError` for HTTP-level errors, which is inspectable.

**Alternative considered:** A shared `_with_retry(fn)` decorator — worth it if more call sites appear, but premature for two callers.

### 3. `KeyError` guard in `existing_response_ids`

**Decision:** Replace `record["responseId"]` with `record.get("responseId")` and filter `None` values, or wrap the comprehension in a `try/except KeyError` that raises `ApiError`.

**Rationale:** The API is mocked and well-behaved in testing, but any field-selection bug or schema mismatch in production would cause an unhandled crash rather than a logged, recoverable error.

### 4. Named GraphQL operations

**Decision:**
- Query: `query CheckExistingResponses($responseIds: [UUID!]!) { ... }`
- Mutation: `mutation UploadSurveyResponses($input: [CreateSurveyResponseInput!]!) { ... }`

**Rationale:** Named operations appear in server logs, APM traces, and GraphQL error responses. This is idiomatic GraphQL and what any real API team expects.

### 5. Test structure

**Decision:** Add tests in three categories:
- `test_api_client.py`: retry behaviour (mock `_graphql` to fail N-1 times then succeed), `KeyError` guard (mock returns record without `responseId`), named operations (assert operation name appears in the query string)
- `test_deduplication.py`: `run()` with a fully mocked `SurveyApiClient` — covering the happy path, query failure (records excluded), upload failure (batch logged, others continue)
- `test_input_reader.py`: already adequate; no changes needed

**Rationale:** Monkeypatching `_graphql` in `test_api_client.py` is already the pattern; extending it is consistent. Testing `run()` via dependency injection of a mock client is the most direct way to verify the pipeline logic without a live server.

### 6. Example data generation

**Decision:** Generate `examples/responses_large.json` (100 records, ~10 spanning multiple field shapes) and `examples/responses_batch_demo.json` (300 records, includes 5 duplicates matching mock-server pre-seeded IDs and 3 malformed entries) as static JSON files committed to the repo.

**Rationale:** Static files are reproducible and require no runtime dependencies. 300 records with default batch size of 100 forces 3 query batches and 3 upload batches, demonstrating the batching logic concretely.

## Risks / Trade-offs

- **`gql.Client` is not thread-safe** → The CLI is single-threaded; not a concern now. If parallelism is added later, the client must be per-thread or replaced with an async transport.
- **Retry in `_graphql` catches `TransportServerError`** → If `gql` changes its exception hierarchy between minor versions, retries silently stop working. Pinning `gql[requests]>=3.5,<4.0` (already in `requirements.txt`) mitigates this.
- **Large example files add repo size** → 300 JSON records is ~50 KB; acceptable for a CLI tool repo.

## Open Questions

- None blocking implementation. The README's noted future work (per-record retry, token refresh, persistent progress) remains out of scope.
