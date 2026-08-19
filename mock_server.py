import re

from flask import Flask, jsonify, request

app = Flask(__name__)
TOKEN = "local-demo-token"
RECORDS = {
    "11111111-1111-1111-1111-111111111111": {
        "id": "11111111-1111-1111-1111-111111111111",
        "responseId": "11111111-1111-1111-1111-111111111111",
        "surveyId": "customer-satisfaction",
        "answers": {"score": 5},
        "submittedAt": "2026-08-19T10:00:00Z",
    }
}


def requested_response_fields(query):
    match = re.search(r"surveyResponsesByResponseIds\s*\([^)]*\)\s*\{([^{}]*)\}", query or "")
    if not match:
        return {"responseId"}
    fields = {"id", "responseId", "surveyId", "answers", "submittedAt"}
    return set(re.findall(r"\b(?:" + "|".join(fields) + r")\b", match.group(1)))


def select_fields(record, fields):
    return {field: record[field] for field in fields if field in record}


@app.post("/auth/token")
def auth_token():
    body = request.get_json(silent=True) or {}
    if body.get("client_id") != "demo-client" or body.get("client_secret") != "demo-secret":
        return jsonify({"error": "invalid_client"}), 401
    return jsonify({"access_token": TOKEN, "expires_in": 3600, "token_type": "Bearer"})


@app.post("/graphql")
def graphql():
    if request.headers.get("Authorization") != f"Bearer {TOKEN}":
        return jsonify({"errors": [{"message": "unauthorized"}]}), 401
    body = request.get_json(silent=True) or {}
    variables = body.get("variables", {})
    if "responseIds" in variables:
        fields = requested_response_fields(body.get("query", ""))
        records = [select_fields(RECORDS[value], fields) for value in variables["responseIds"] if value in RECORDS]
        return jsonify({"data": {"surveyResponsesByResponseIds": records}})
    input_records = variables.get("input", [])
    failed = [record["responseId"] for record in input_records if record["responseId"] == "33333333-3333-3333-3333-333333333333"]
    if failed:
        return jsonify({"errors": [{"message": f"mock rejected response_ids: {failed}"}]})
    created = []
    for record in input_records:
        stored = {
            "id": record["responseId"],
            "responseId": record["responseId"],
            "surveyId": record["surveyId"],
            "answers": record["answers"],
            "submittedAt": record["submittedAt"],
        }
        RECORDS[record["responseId"]] = stored
        created.append({"responseId": record["responseId"]})
    return jsonify({"data": {"createSurveyResponses": created}})


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000)