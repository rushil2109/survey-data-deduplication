"""
End-to-end tests for the run() pipeline using a fully mocked SurveyApiClient.

These tests verify the deduplication logic — which records are uploaded, which are
excluded, and how the pipeline behaves when individual batches fail — without
requiring a live server.
"""

import argparse
from datetime import datetime, timezone
from typing import Optional, Set
from unittest.mock import MagicMock
from uuid import UUID

import pytest

from survey_deduplication.api_client import ApiError
from survey_deduplication.cli import chunks, run
from survey_deduplication.models import CreateSurveyResponseInput


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _response(response_id: str, survey_id: str = "test-survey") -> CreateSurveyResponseInput:
    """Build a minimal valid CreateSurveyResponseInput for test use."""
    return CreateSurveyResponseInput(
        responseId=UUID(response_id),
        surveyId=survey_id,
        answers={"score": 1},
        submittedAt=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )


def _mock_client(existing_ids: Optional[Set[str]] = None, upload_side_effect=None) -> MagicMock:
    """Return a mock SurveyApiClient with configurable behaviour."""
    client = MagicMock()
    client.existing_response_ids.return_value = existing_ids or set()
    if upload_side_effect is not None:
        client.upload.side_effect = upload_side_effect
    else:
        # Default: report each submitted record as successfully created.
        client.upload.side_effect = lambda batch: [{"responseId": r["responseId"]} for r in batch]
    return client


def _args(input_path: str, query_batch_size: int = 100, upload_batch_size: int = 100) -> argparse.Namespace:
    """Build an argparse.Namespace that satisfies run()'s expectations."""
    return argparse.Namespace(
        input=input_path,
        base_url="http://example.test",
        client_id="id",
        client_secret="secret",
        timeout=10.0,
        query_batch_size=query_batch_size,
        upload_batch_size=upload_batch_size,
    )


# ---------------------------------------------------------------------------
# Task 5.1 — happy path: existing record excluded, new record uploaded
# ---------------------------------------------------------------------------

def test_run_happy_path_excludes_existing_and_uploads_new(tmp_path, monkeypatch):
    """run() must skip records already on the server and upload only the new ones."""
    import json

    existing_id = "11111111-1111-1111-1111-111111111111"
    new_id = "22222222-2222-2222-2222-222222222222"

    input_file = tmp_path / "responses.json"
    input_file.write_text(json.dumps([
        {"responseId": existing_id, "surveyId": "s", "answers": {}, "submittedAt": "2026-01-01T00:00:00Z"},
        {"responseId": new_id,      "surveyId": "s", "answers": {}, "submittedAt": "2026-01-01T00:00:00Z"},
    ]))

    mock_client = _mock_client(existing_ids={existing_id})

    # Inject the mock by patching SurveyApiClient wherever cli.py imports it.
    monkeypatch.setattr(
        "survey_deduplication.cli.SurveyApiClient",
        lambda *args, **kwargs: mock_client,
    )

    result = run(_args(str(input_file)))
    assert result == 0

    # Only the new record must have been passed to upload.
    uploaded_batches = mock_client.upload.call_args_list
    uploaded_ids = {r["responseId"] for batch_call in uploaded_batches for r in batch_call.args[0]}
    assert new_id in uploaded_ids
    assert existing_id not in uploaded_ids


# ---------------------------------------------------------------------------
# Task 5.2 — query failure: affected records excluded from upload
# ---------------------------------------------------------------------------

def test_run_query_failure_excludes_affected_records(tmp_path, monkeypatch):
    """When existing_response_ids raises ApiError, those records must NOT be uploaded."""
    import json

    safe_id = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
    risky_id = "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"

    input_file = tmp_path / "responses.json"
    input_file.write_text(json.dumps([
        {"responseId": safe_id,  "surveyId": "s", "answers": {}, "submittedAt": "2026-01-01T00:00:00Z"},
        {"responseId": risky_id, "surveyId": "s", "answers": {}, "submittedAt": "2026-01-01T00:00:00Z"},
    ]))

    # Both records land in separate batches of 1 so we can make one fail.
    mock_client = MagicMock()

    # First batch (safe_id) succeeds; second batch (risky_id) fails.
    def query_side_effect(ids):
        if risky_id in ids:
            raise ApiError("query failed for risky batch")
        return set()

    mock_client.existing_response_ids.side_effect = query_side_effect
    mock_client.upload.side_effect = lambda batch: [{"responseId": r["responseId"]} for r in batch]

    monkeypatch.setattr(
        "survey_deduplication.cli.SurveyApiClient",
        lambda *args, **kwargs: mock_client,
    )

    # Use batch size 1 so each record gets its own query batch.
    result = run(_args(str(input_file), query_batch_size=1))
    assert result == 0

    uploaded_batches = mock_client.upload.call_args_list
    uploaded_ids = {r["responseId"] for batch_call in uploaded_batches for r in batch_call.args[0]}

    # The safe record must be uploaded; the risky record (unknown dup status) must not.
    assert safe_id in uploaded_ids
    assert risky_id not in uploaded_ids


# ---------------------------------------------------------------------------
# Task 5.3 — upload failure: run() returns 0 and later batches still attempted
# ---------------------------------------------------------------------------

def test_run_upload_failure_continues_later_batches(tmp_path, monkeypatch):
    """A failing upload batch must not abort subsequent batches; run() still returns 0."""
    import json

    id_a = "cccccccc-cccc-cccc-cccc-cccccccccccc"
    id_b = "dddddddd-dddd-dddd-dddd-dddddddddddd"
    id_c = "eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee"

    input_file = tmp_path / "responses.json"
    input_file.write_text(json.dumps([
        {"responseId": id_a, "surveyId": "s", "answers": {}, "submittedAt": "2026-01-01T00:00:00Z"},
        {"responseId": id_b, "surveyId": "s", "answers": {}, "submittedAt": "2026-01-01T00:00:00Z"},
        {"responseId": id_c, "surveyId": "s", "answers": {}, "submittedAt": "2026-01-01T00:00:00Z"},
    ]))

    call_count = 0

    def upload_side_effect(batch):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            # First batch fails.
            raise ApiError("upload failed for first batch")
        return [{"responseId": r["responseId"]} for r in batch]

    mock_client = _mock_client(upload_side_effect=upload_side_effect)

    monkeypatch.setattr(
        "survey_deduplication.cli.SurveyApiClient",
        lambda *args, **kwargs: mock_client,
    )

    # Use upload batch size 1 so we get 3 separate upload calls.
    result = run(_args(str(input_file), upload_batch_size=1))

    # run() must return 0 regardless of failed batches.
    assert result == 0
    # All 3 batches must have been attempted (pipeline continues after failure).
    assert call_count == 3


# ---------------------------------------------------------------------------
# Preserved existing test
# ---------------------------------------------------------------------------

def test_chunks_preserves_order():
    assert list(chunks([1, 2, 3, 4, 5], 2)) == [[1, 2], [3, 4], [5]]
