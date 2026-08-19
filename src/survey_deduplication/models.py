from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from uuid import UUID


def _datetime_value(value: datetime) -> str:
    """Serialize datetimes in the UTC ISO-8601 format expected by GraphQL."""
    normalized = value.astimezone(timezone.utc)
    return normalized.isoformat().replace("+00:00", "Z")


@dataclass(frozen=True)
class SurveyResponse:
    id: UUID
    responseId: UUID
    surveyId: str
    answers: Any
    submittedAt: datetime

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": str(self.id),
            "responseId": str(self.responseId),
            "surveyId": self.surveyId,
            "answers": self.answers,
            "submittedAt": _datetime_value(self.submittedAt),
        }


@dataclass(frozen=True)
class CreateSurveyResponseInput:
    responseId: UUID
    surveyId: str
    answers: Any
    submittedAt: datetime

    def as_dict(self) -> dict[str, Any]:
        return {
            "responseId": str(self.responseId),
            "surveyId": self.surveyId,
            "answers": self.answers,
            "submittedAt": _datetime_value(self.submittedAt),
        }