## ADDED Requirements

### Requirement: GraphQL client is created once per execution
After successful authentication, the system SHALL construct a single `gql.Client` instance backed by a single `RequestsHTTPTransport` (and therefore a single `requests.Session`) and reuse it for all subsequent GraphQL calls within that execution.

#### Scenario: Client is not recreated between calls
- **WHEN** `existing_response_ids` and `upload` are both called on the same `SurveyApiClient` instance
- **THEN** both calls use the same underlying `gql.Client` object (no new client is constructed for the second call)

#### Scenario: Client is entered as a context manager per call
- **WHEN** a GraphQL call is made
- **THEN** the client is used via `with self._gql_client as session: session.execute(...)` so that connection lifecycle is managed by the library

#### Scenario: Calling GraphQL without authenticating first raises ApiError
- **WHEN** `existing_response_ids` or `upload` is called before `authenticate()`
- **THEN** an `ApiError` is raised with a message indicating the client is not authenticated

### Requirement: All GraphQL operations are named
The system SHALL include an operation name in every GraphQL query and mutation string sent to the API.

#### Scenario: Duplicate check query carries operation name
- **WHEN** `existing_response_ids` sends a GraphQL request
- **THEN** the query string begins with `query CheckExistingResponses(`

#### Scenario: Upload mutation carries operation name
- **WHEN** `upload` sends a GraphQL request
- **THEN** the query string begins with `mutation UploadSurveyResponses(`
