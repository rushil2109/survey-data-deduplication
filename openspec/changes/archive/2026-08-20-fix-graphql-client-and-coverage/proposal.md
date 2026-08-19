## Why

The current implementation has several correctness and quality issues: the `gql.Client` is recreated on every GraphQL call (leaking connections and bypassing the library's connection management), GraphQL calls have no retry logic unlike the auth call, a `KeyError` can crash the process instead of surfacing a clean `ApiError`, operations are anonymous (making server-side tracing impossible), and the test suite is too thin to validate the deduplication pipeline end-to-end. The example data file is also too small to meaningfully demonstrate batching behaviour.

## What Changes

- Fix `gql.Client` lifecycle: create once after authentication, reuse via context manager per call
- Add retry logic with exponential backoff to `_graphql`, matching `_request`
- Guard `existing_response_ids` against `KeyError` from unexpected API responses
- Name all GraphQL operations (`CheckExistingResponses`, `UploadSurveyResponses`)
- Expand test coverage: `run()` integration path, GraphQL error path, retry behaviour, deduplication logic
- Add larger example JSON files (100+ records) to demonstrate batching

## Capabilities

### New Capabilities

- `graphql-client-lifecycle`: Persistent, properly-managed `gql.Client` reused across all GraphQL calls within one execution
- `graphql-retry`: Retry logic with exponential backoff for transient GraphQL failures, consistent with the existing REST retry behaviour
- `example-data`: Larger, realistic example input files (100+ records including duplicates and malformed entries) for demonstrating batching and deduplication at scale

### Modified Capabilities

- None — no spec-level behavioural requirements are changing; all changes are implementation corrections and test additions

## Impact

- `src/survey_deduplication/api_client.py`: Client lifecycle refactor, retry addition, `KeyError` guard, named operations
- `tests/test_api_client.py`: New tests for retry, error safety, named operations
- `tests/test_deduplication.py`: New end-to-end `run()` tests with mocked client
- `examples/`: New `responses_large.json` (100+ records) and `responses_batch_demo.json` (300+ records spanning multiple default batch sizes)
