"""
Pydantic models for document truthfulness validation.
Used by backend/pipeline/truthfulness.py to validate generated CV and cover letter.
"""
from typing import Literal

from pydantic import BaseModel, Field


class TruthfulnessIssue(BaseModel):
    claim: str
    issue_type: Literal[
        "invented_skill",
        "invented_entity",
        "exaggerated_experience",
        "unsupported_claim",
    ]
    detail: str


class TruthfulnessResult(BaseModel):
    valid: bool
    issues: list[TruthfulnessIssue] = Field(default_factory=list)
    severity: Literal["low", "medium", "high"]
