## 1. GraphQL Client Lifecycle Fix

- [x] 1.1 Add `_gql_client` instance variable (initially `None`) to `SurveyApiClient.__init__`
- [x] 1.2 In `authenticate()`, after storing `self.token`, construct `RequestsHTTPTransport` and `Client` and assign to `self._gql_client`
- [x] 1.3 Rewrite `_graphql` to guard on `self._gql_client is None` (raise `ApiError`) and use `with self._gql_client as session: session.execute(...)` instead of creating a new client per call
- [x] 1.4 Name the query in `existing_response_ids`: change to `query CheckExistingResponses($responseIds: [UUID!]!) { ... }`
- [x] 1.5 Name the mutation in `upload`: change to `mutation UploadSurveyResponses($input: [CreateSurveyResponseInput!]!) { ... }`

## 2. Retry Logic for GraphQL

- [x] 2.1 Wrap `session.execute()` in `_graphql` in the same `for attempt in range(self.retries + 1)` retry loop used in `_request`
- [x] 2.2 Catch `gql.transport.exceptions.TransportServerError` (and `TransportQueryError` where applicable) for retryable errors; re-raise immediately on non-retryable errors
- [x] 2.3 Apply `time.sleep(0.1 * (2 ** attempt))` backoff between retries, consistent with `_request`

## 3. Error Safety

- [x] 3.1 In `existing_response_ids`, replace `record["responseId"]` with `record.get("responseId")` and filter out `None` values so a missing field raises `ApiError` instead of `KeyError`
- [x] 3.2 Wrap the response-parsing logic in `existing_response_ids` in a `try/except (KeyError, TypeError)` that re-raises as `ApiError` with a descriptive message

## 4. Tests — API Client

- [x] 4.1 Add test: retry succeeds on second attempt — monkeypatch `session.execute` to raise `TransportServerError` once then return valid data; assert result is correct and call count is 2
- [x] 4.2 Add test: all retries exhausted raises `ApiError` — monkeypatch to always raise `TransportServerError`; assert `ApiError` is raised
- [x] 4.3 Add test: missing `responseId` in response record raises `ApiError` (not `KeyError`) — monkeypatch `_graphql` to return `{"surveyResponsesByResponseIds": [{}]}`
- [x] 4.4 Add test: named operations — assert `"CheckExistingResponses"` appears in the query string passed to `_graphql`, and `"UploadSurveyResponses"` in the mutation

## 5. Tests — Deduplication Pipeline (run())

- [x] 5.1 Add test: happy path — mock client returns one existing ID; assert `run()` returns 0, upload called with only the new record
- [x] 5.2 Add test: query failure — mock `existing_response_ids` raises `ApiError`; assert affected records are excluded from upload (not uploaded blindly)
- [x] 5.3 Add test: upload failure — mock `upload` raises `ApiError`; assert `run()` still returns 0 and later batches are attempted

## 6. Example Data Files

- [x] 6.1 Generate `examples/responses_large.json` with 100 valid records (unique UUIDs, varied `surveyId` values, valid ISO-8601 `submittedAt` timestamps)
- [x] 6.2 Generate `examples/responses_batch_demo.json` with 300 records including: the mock server's pre-seeded ID `11111111-1111-1111-1111-111111111111` as a duplicate, the mock server's rejection ID `33333333-3333-3333-3333-333333333333` to demonstrate upload error logging, and at least 2 malformed records (missing fields or bad UUID)
- [x] 6.3 Verify both files parse cleanly with `read_responses` and log expected skip/duplicate counts
