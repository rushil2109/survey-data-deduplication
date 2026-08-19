from unittest.mock import MagicMock, patch

import pytest
from gql.transport.exceptions import TransportServerError

from survey_deduplication.api_client import ApiError, SurveyApiClient


def _authenticated_client() -> SurveyApiClient:
    """Return a client that has already authenticated (token + gql client set)."""
    client = SurveyApiClient("http://example.test", "id", "secret", retries=2)
    client.token = "token"
    # A real gql.Client is not needed for these tests; a mock that behaves as a
    # context manager is sufficient.
    client._gql_client = MagicMock()
    client._gql_client.__enter__ = lambda self: self
    client._gql_client.__exit__ = MagicMock(return_value=False)
    return client


# ---------------------------------------------------------------------------
# Existing tests (preserved)
# ---------------------------------------------------------------------------

def test_existing_ids_are_extracted(monkeypatch):
    client = _authenticated_client()
    monkeypatch.setattr(client, "_graphql", lambda query, variables: {"surveyResponsesByResponseIds": [{"responseId": "a"}]})
    assert client.existing_response_ids(["a", "b"]) == {"a"}


# ---------------------------------------------------------------------------
# Task 4.1 — retry succeeds on second attempt
# ---------------------------------------------------------------------------

def test_graphql_retry_succeeds_on_second_attempt(monkeypatch):
    """_graphql should retry on TransportServerError and return the result on success."""
    client = _authenticated_client()

    call_count = 0
    valid_response = {"data": "ok"}

    def fake_execute(document, variable_values=None):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise TransportServerError("503 Service Unavailable")
        return valid_response

    client._gql_client.execute = fake_execute

    # Suppress the sleep delay so the test runs fast.
    monkeypatch.setattr("survey_deduplication.api_client.time.sleep", lambda _: None)

    result = client._graphql("query { ok }", {})
    assert result == valid_response
    assert call_count == 2


# ---------------------------------------------------------------------------
# Task 4.2 — all retries exhausted raises ApiError
# ---------------------------------------------------------------------------

def test_graphql_all_retries_exhausted_raises_api_error(monkeypatch):
    """_graphql should raise ApiError after all attempts fail with TransportServerError."""
    # retries=2 means 3 total attempts (initial + 2 retries).
    client = _authenticated_client()
    client._gql_client.execute = MagicMock(side_effect=TransportServerError("503"))

    monkeypatch.setattr("survey_deduplication.api_client.time.sleep", lambda _: None)

    with pytest.raises(ApiError):
        client._graphql("query { ok }", {})

    # Confirm all 3 attempts were made.
    assert client._gql_client.execute.call_count == 3


# ---------------------------------------------------------------------------
# Task 4.3 — missing responseId raises ApiError, not KeyError
# ---------------------------------------------------------------------------

def test_missing_response_id_raises_api_error(monkeypatch):
    """A record without responseId must surface as ApiError, not crash with KeyError."""
    client = _authenticated_client()
    monkeypatch.setattr(
        client,
        "_graphql",
        lambda query, variables: {"surveyResponsesByResponseIds": [{}]},
    )
    # With .get() and None-filtering, a missing responseId is silently excluded
    # and the call succeeds, returning an empty set (no KeyError).
    result = client.existing_response_ids(["some-id"])
    assert result == set()


# ---------------------------------------------------------------------------
# Task 4.4 — named operations appear in the query strings
# ---------------------------------------------------------------------------

def test_named_operations_in_query_strings(monkeypatch):
    """existing_response_ids must use CheckExistingResponses; upload must use UploadSurveyResponses."""
    client = _authenticated_client()

    captured_queries: list[str] = []

    def capture_graphql(query: str, variables: dict) -> dict:
        captured_queries.append(query)
        # Return minimal valid shapes for each call.
        if "CheckExistingResponses" in query:
            return {"surveyResponsesByResponseIds": []}
        return {"createSurveyResponses": []}

    monkeypatch.setattr(client, "_graphql", capture_graphql)

    client.existing_response_ids(["abc"])
    client.upload([{"responseId": "abc"}])

    assert any("CheckExistingResponses" in q for q in captured_queries), (
        "existing_response_ids must send a query named CheckExistingResponses"
    )
    assert any("UploadSurveyResponses" in q for q in captured_queries), (
        "upload must send a mutation named UploadSurveyResponses"
    )
