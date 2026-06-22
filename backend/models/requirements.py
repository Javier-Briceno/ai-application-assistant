"""
Pydantic models for the requirements compliance check.
Produced by run_requirements_check (Haiku) and used to adjust the final threshold.
"""
from pydantic import BaseModel, Field


class BlockerItem(BaseModel):
    requirement: str  # e.g. "C1 German required"
    reason: str       # why the candidate does not meet it


class RequirementsAnalysis(BaseModel):
    """
    Structured result of comparing explicit job requirements against the candidate.

    Fields:
      hard_requirement_matches   — requirements clearly MET (for transparency)
      missing_hard_requirements  — explicit mandatory requirements NOT met
      triggered_dealbreakers     — hard exclusion criteria triggered (most severe)
      missing_soft_requirements  — preferred/nice-to-have items not met (no threshold impact)
      recommendation_blockers    — flat summary list for UI: one entry per hard miss/dealbreaker
    """
    hard_requirement_matches: list[str] = Field(default_factory=list)
    missing_hard_requirements: list[BlockerItem] = Field(default_factory=list)
    triggered_dealbreakers: list[BlockerItem] = Field(default_factory=list)
    missing_soft_requirements: list[str] = Field(default_factory=list)
    recommendation_blockers: list[str] = Field(default_factory=list)
