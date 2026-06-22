"""
Pydantic models for the CV tailoring pipeline.
Mirrors the JSON schemas from the n8n CV Tailoring Planner workflow.
"""
from typing import Literal

from pydantic import BaseModel, Field


# ── Classifier output ─────────────────────────────────────────────────────────

class ClassifierItem(BaseModel):
    id: str
    classification: Literal["KEEP", "DISTRAKTOR", "TRANSFERABEL"]


class ClassifierOutput(BaseModel):
    items: list[ClassifierItem] = Field(default_factory=list)


# ── Generator output ──────────────────────────────────────────────────────────

class GeneratorItem(BaseModel):
    id: str
    action: Literal["ENTFERNEN", "KÜRZEN", "KEEP"]
    new_content: str


class GeneratorOutput(BaseModel):
    items: list[GeneratorItem] = Field(default_factory=list)


# ── Validator result ──────────────────────────────────────────────────────────

class ValidationError(BaseModel):
    item_id: str
    error_type: Literal["no_op", "transferabel_removed", "cluster_guard"]
    detail: str


class ValidationResult(BaseModel):
    valid: bool
    errors: list[ValidationError] = Field(default_factory=list)


# ── Final tailoring result ────────────────────────────────────────────────────

class TailoringResult(BaseModel):
    tailored_cv: str
    cv_diff: str
    items_removed: int
    items_shortened: int
    retry_used: bool = False
