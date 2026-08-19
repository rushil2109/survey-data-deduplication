from survey_deduplication.api_client import SurveyApiClient


def test_existing_ids_are_extracted(monkeypatch):
    client = SurveyApiClient("http://example.test", "id", "secret")
    client.token = "token"
    monkeypatch.setattr(client, "_graphql", lambda query, variables: {"surveyResponsesByResponseIds": [{"responseId": "a"}]})
    assert client.existing_response_ids(["a", "b"]) == {"a"}