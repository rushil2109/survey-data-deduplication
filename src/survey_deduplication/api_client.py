from __future__ import annotations

import json
import logging
import time
from typing import Any, Dict, Optional
import urllib.error
import urllib.request

from gql import Client, gql
from gql.transport.exceptions import TransportQueryError, TransportServerError
from gql.transport.requests import RequestsHTTPTransport

logger = logging.getLogger(__name__)
# gql logs full variables at INFO; survey answers should not be written to logs.
logging.getLogger("gql.transport.requests").setLevel(logging.WARNING)


class ApiError(Exception):
    pass


class SurveyApiClient:
    """Handles authentication and all GraphQL communication with the survey API.

    Call authenticate() before any GraphQL method. A single token is used for
    the lifetime of the client; there is no automatic token refresh.
    # TODO: add token refresh logic for long-running processes where the token
    # may expire mid-run (token lifetime is returned as expires_in in the auth response).
    """

    def __init__(self, base_url: str, client_id: str, client_secret: str, timeout: float = 10, retries: int = 2):
        self.base_url = base_url.rstrip("/")
        self.client_id = client_id
        self.client_secret = client_secret
        self.timeout = timeout
        self.retries = retries
        self.token: Optional[str] = None
        # Created once in authenticate(); None until then.
        self._gql_client: Optional[Client] = None

    def _request(self, path: str, body: Dict[str, Any]) -> Dict[str, Any]:
        # Authentication is a REST endpoint, so gql cannot be used for this call.
        request = urllib.request.Request(
            f"{self.base_url}{path}",
            data=json.dumps(body).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        for attempt in range(self.retries + 1):
            try:
                with urllib.request.urlopen(request, timeout=self.timeout) as response:
                    payload = json.loads(response.read().decode("utf-8"))
                    if not isinstance(payload, dict):
                        raise ApiError(f"response from {path} was not a JSON object")
                    return payload
            except urllib.error.HTTPError as exc:
                if exc.code not in {429, 500, 502, 503, 504} or attempt == self.retries:
                    raise ApiError(f"HTTP {exc.code} from {path}") from exc
            except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, ApiError) as exc:
                if attempt == self.retries:
                    raise ApiError(f"request to {path} failed: {exc}") from exc
            time.sleep(0.1 * (2**attempt))
        raise ApiError(f"request to {path} failed")

    def authenticate(self) -> None:
        payload = self._request("/auth/token", {"client_id": self.client_id, "client_secret": self.client_secret})
        token = payload.get("access_token")
        if not isinstance(token, str) or not token:
            raise ApiError("authentication response did not contain access_token")
        self.token = token
        # Build the gql client once so the underlying requests.Session is reused
        # across all GraphQL calls (keeps connections alive, avoids per-call overhead).
        transport = RequestsHTTPTransport(
            url=f"{self.base_url}/graphql",
            headers={"Authorization": f"Bearer {self.token}"},
            timeout=self.timeout,
        )
        self._gql_client = Client(transport=transport, fetch_schema_from_transport=False)

    def _graphql(self, query: str, variables: dict[str, Any]) -> dict[str, Any]:
        if self._gql_client is None:
            raise ApiError("client is not authenticated; call authenticate() first")

        # Mirror the retry/backoff policy used by _request so all network calls
        # degrade gracefully under transient server-side failures.
        last_exc: Exception = ApiError("GraphQL request failed")
        for attempt in range(self.retries + 1):
            try:
                # Enter the client as a context manager per call so gql manages
                # the connection lifecycle (keep-alive, session pooling) correctly.
                with self._gql_client as session:
                    result = session.execute(gql(query), variable_values=variables)
                if not isinstance(result, dict):
                    raise ApiError("GraphQL response data was not an object")
                return result
            except TransportServerError as exc:
                # HTTP 5xx / 429 — transient; worth retrying.
                last_exc = exc
                if attempt == self.retries:
                    raise ApiError(f"GraphQL request failed after {self.retries + 1} attempts: {exc}") from exc
            except TransportQueryError as exc:
                # Application-level GraphQL error (e.g. bad query, 400) — not retryable.
                raise ApiError(f"GraphQL request failed: {exc}") from exc
            except ApiError:
                raise
            except Exception as exc:
                # Any other unexpected transport error — not retryable.
                raise ApiError(f"GraphQL request failed: {exc}") from exc
            time.sleep(0.1 * (2**attempt))

        raise ApiError(f"GraphQL request failed after {self.retries + 1} attempts: {last_exc}") from last_exc

    def existing_response_ids(self, response_ids: list[str]) -> set[str]:
        # Operation name enables server-side tracing and APM identification.
        query = """
            query CheckExistingResponses($responseIds: [UUID!]!) {
                surveyResponsesByResponseIds(responseIds: $responseIds) {
                    responseId
                }
            }
        """
        try:
            records = self._graphql(query, {"responseIds": response_ids}).get("surveyResponsesByResponseIds", [])
            # Use .get() so a missing field returns None instead of raising KeyError;
            # then filter Nones so null responseId values are silently excluded.
            ids = {record.get("responseId") for record in records}
            ids.discard(None)
            return ids  # type: ignore[return-value]
        except ApiError:
            raise
        except (KeyError, TypeError) as exc:
            raise ApiError(f"unexpected structure in surveyResponsesByResponseIds response: {exc}") from exc

    def upload(self, responses: list[dict[str, Any]]) -> list[dict[str, Any]]:
        # TODO: on partial batch failure, retry each record individually to isolate
        # the bad record rather than dropping the entire batch. Currently a single
        # bad record causes the whole batch to be skipped and logged.
        # Operation name enables server-side tracing and APM identification.
        mutation = """
            mutation UploadSurveyResponses($input: [CreateSurveyResponseInput!]!) {
                createSurveyResponses(input: $input) {
                    responseId
                }
            }
        """
        try:
            return self._graphql(mutation, {"input": responses}).get("createSurveyResponses", [])
        except ApiError:
            raise
        except (KeyError, TypeError) as exc:
            raise ApiError(f"unexpected structure in createSurveyResponses response: {exc}") from exc
