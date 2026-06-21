"""
Pydantic models for the analysis & scoring pipeline.
Mirrors the JSON schema from the n8n Analysis Scoring Structured Output Parser.
"""
from typing import Literal

from pydantic import BaseModel, Field


# ── LLM output from Analyzer ──────────────────────────────────────────────────

class TechnicalScore(BaseModel):
    score: int = Field(ge=0, le=40)
    reasoning: str
    matching_skills: list[str] = Field(default_factory=list)
    missing_skills: list[str] = Field(default_factory=list)


class RequirementsScore(BaseModel):
    score: int = Field(ge=0, le=25)
    reasoning: str


class RoleFitScore(BaseModel):
    score: int = Field(ge=0, le=20)
    reasoning: str
    matched_role_key: str = ""


class LocationScore(BaseModel):
    score: int = Field(ge=0, le=10)
    reasoning: str


class StrategicScore(BaseModel):
    score: int = Field(ge=0, le=5)
    reasoning: str


class AnalyzerOutput(BaseModel):
    """Raw structured output from the GPT-4.1 Analyzer."""
    technical: TechnicalScore
    requirements: RequirementsScore
    role_fit: RoleFitScore
    location: LocationScore
    strategic: StrategicScore


# ── Deterministic post-processing ─────────────────────────────────────────────

class DimensionScores(BaseModel):
    technical: int
    requirements: int
    role_fit: int
    location: int
    strategic: int

    @property
    def total(self) -> int:
        return self.technical + self.requirements + self.role_fit + self.location + self.strategic


class ScoringResult(BaseModel):
    """Final result after Calculate Dimensions + Calculate Threshold."""
    dims: DimensionScores
    total_score: int
    threshold: Literal["pass", "caution", "fail"]
    analyzer_output: AnalyzerOutput
