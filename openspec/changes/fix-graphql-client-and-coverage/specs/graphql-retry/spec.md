## ADDED Requirements

### Requirement: GraphQL calls retry on transient failures
The system SHALL retry failed GraphQL requests using the same exponential backoff policy applied to REST calls: up to `self.retries` additional attempts with `0.1 * (2 ** attempt)` seconds between attempts.

#### Scenario: Transient server error triggers retry and eventually succeeds
- **WHEN** the first GraphQL attempt raises a transport-level server error (e.g. HTTP 503)
- **AND** the second attempt succeeds
- **THEN** the call returns the successful result without raising an exception

#### Scenario: All retries exhausted raises ApiError
- **WHEN** every attempt (initial + retries) fails with a transient error
- **THEN** an `ApiError` is raised after the final attempt

#### Scenario: Non-retryable errors are not retried
- **WHEN** a GraphQL call raises a non-transient error (e.g. HTTP 400, invalid query)
- **THEN** the error is raised immediately without retrying

### Requirement: Unexpected API response fields do not crash the process
The system SHALL handle missing or unexpected fields in GraphQL response records by raising `ApiError` rather than propagating an unhandled `KeyError` or `TypeError`.

#### Scenario: Response record missing responseId raises ApiError
- **WHEN** the API returns a record in `surveyResponsesByResponseIds` that does not contain a `responseId` field
- **THEN** an `ApiError` is raised (not a `KeyError`)

#### Scenario: Null responseId is handled safely
- **WHEN** the API returns a record with `responseId: null`
- **THEN** the null value is not included in the returned set of existing IDs
