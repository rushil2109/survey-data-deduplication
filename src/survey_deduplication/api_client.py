from __future__ import annotations

import json
import logging
import time
from typing import Any, Dict, Optional
import urllib.error
import urllib.request

from gql import Client, gql
from gql.transport.requests import RequestsHTTPTransport

logger = logging.getLogger(__name__)
# gql logs full variables at INFO; survey answers should not be written to logs.
logging.getLogger("gql.transport.requests").setLevel(logging.WARNING)


class ApiError(Exception):
    pass


class SurveyApiClient:
    def __init__(self, base_url: str, client_id: str, client_secret: str, timeout: float = 10, retries: int = 2):
        self.base_url = base_url.rstrip("/")
        self.client_id = client_id
        self.client_secret = client_secret
        self.timeout = timeout
        self.retries = retries
        self.token: Optional[str] = None

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

    def _graphql(self, query: str, variables: dict[str, Any]) -> dict[str, Any]:
        if not self.token:
            raise ApiError("client is not authenticated")
        transport = RequestsHTTPTransport(
            url=f"{self.base_url}/graphql",
            headers={"Authorization": f"Bearer {self.token}"},
            timeout=self.timeout,
        )
        graphql_client = Client(transport=transport, fetch_schema_from_transport=False)
        try:
            result = graphql_client.execute(gql(query), variable_values=variables)
        except Exception as exc:
            raise ApiError(f"GraphQL request failed: {exc}") from exc
        if not isinstance(result, dict):
            raise ApiError("GraphQL response data was not an object")
        return result

    def existing_response_ids(self, response_ids: list[str]) -> set[str]:
        query = "query($responseIds: [UUID!]!) { surveyResponsesByResponseIds(responseIds: $responseIds) { responseId } }"
        records = self._graphql(query, {"responseIds": response_ids}).get("surveyResponsesByResponseIds", [])
        return {record["responseId"] for record in records}

    def upload(self, responses: list[dict[str, Any]]) -> list[dict[str, Any]]:
        mutation = "mutation($input: [CreateSurveyResponseInput!]!) { createSurveyResponses(input: $input) { responseId } }"
        return self._graphql(mutation, {"input": responses}).get("createSurveyResponses", [])