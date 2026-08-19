import json

from survey_deduplication.input_reader import read_responses


def test_reader_skips_malformed_and_duplicate_records(tmp_path):
    path = tmp_path / "responses.json"
    record = {"responseId": "11111111-1111-1111-1111-111111111111", "surveyId": "survey", "answers": {}, "submittedAt": "2026-08-19T10:00:00Z"}
    path.write_text(json.dumps([record, record, {"responseId": "bad"}, "text"]))

    responses, skipped = read_responses(path)

    assert [str(response.responseId) for response in responses] == ["11111111-1111-1111-1111-111111111111"]
    assert skipped == 3