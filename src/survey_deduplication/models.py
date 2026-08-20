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
    # Represents a response already stored in the database (includes server-assigned id).
    id: UUID
    responseId: UUID
    surveyId: str
    # TODO: validate answers structure against a known schema rather than accepting Any.
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
    # Input-only model for the createSurveyResponses mutation; no server-assigned id.
    responseId: UUID
    surveyId: str
    # TODO: validate answers structure against a known schema rather than accepting Any.
    answers: Any
    submittedAt: datetime

    def as_dict(self) -> dict[str, Any]:
        return {
            "responseId": str(self.responseId),
            "surveyId": self.surveyId,
            "answers": self.answers,
            "submittedAt": _datetime_value(self.submittedAt),
        }