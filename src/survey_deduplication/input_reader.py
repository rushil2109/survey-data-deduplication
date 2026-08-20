from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, List, Tuple, Union

from .models import CreateSurveyResponseInput
from uuid import UUID

logger = logging.getLogger(__name__)
REQUIRED_FIELDS = ("responseId", "surveyId", "answers", "submittedAt")


def read_responses(path: Union[str, Path]) -> Tuple[List[CreateSurveyResponseInput], int]:
    """Read supported JSON shapes and skip malformed records with a reason."""
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"could not read valid JSON from {path}: {exc}") from exc

    records: Any = payload.get("responses") if isinstance(payload, dict) else payload
    if not isinstance(records, list):
        raise ValueError("input JSON must be an array or an object containing a responses array")

    # Invalid records are isolated so one bad row does not stop a complete run.
    valid: list[CreateSurveyResponseInput] = []
    skipped = 0
    # Track responseIds already seen in this file to catch within-file duplicates
    # before reaching the API. The API is the authoritative source for cross-run
    # duplicates; this catches same-file duplicates that the API would otherwise
    # accept on a first-seen basis.
    seen: set[str] = set()
    for index, record in enumerate(records):
        if not isinstance(record, dict):
            logger.warning("Skipping record %d: expected an object", index)
            skipped += 1
            continue
        missing = [field for field in REQUIRED_FIELDS if field not in record]
        response_id = record.get("responseId")
        try:
            parsed_response_id = UUID(response_id)
            parsed_submitted_at = datetime.fromisoformat(record["submittedAt"].replace("Z", "+00:00"))
        except (AttributeError, TypeError, ValueError):
            parsed_response_id = None
            parsed_submitted_at = None
        if (
            missing
            or not isinstance(record.get("surveyId"), str)
            or not record.get("surveyId")
            or parsed_response_id is None
            or parsed_submitted_at is None
            or parsed_submitted_at.tzinfo is None
        ):
            logger.warning("Skipping record %d: missing or invalid required fields (%s)", index, ", ".join(missing) or "type/value")
            skipped += 1
            continue
        if str(parsed_response_id) in seen:
            logger.warning("Skipping record %d: duplicate response_id within input (%s)", index, response_id)
            skipped += 1
            continue
        seen.add(str(parsed_response_id))
        valid.append(CreateSurveyResponseInput(parsed_response_id, record["surveyId"], record["answers"], parsed_submitted_at))
    return valid, skipped