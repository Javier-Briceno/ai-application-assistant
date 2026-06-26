"""
Pydantic models for profile extraction LLM outputs.
These mirror the JSON schemas from the n8n Structured Output Parser nodes exactly.
"""
from pydantic import BaseModel, Field


# ── Raw Extraction – Market Research ──────────────────────────────────────────

class RoleListItem(BaseModel):
    label: str
    frequency: str
    bridge_quality: str


class MarketResearchOutput(BaseModel):
    candidates: list[str] = Field(default_factory=list)
    city_list: list[str] = Field(default_factory=list)
    role_list: list[RoleListItem] = Field(default_factory=list)


# ── Binary Classifier ─────────────────────────────────────────────────────────

class ClassifierDecision(BaseModel):
    item: str
    valid: bool


class BinaryClassifierOutput(BaseModel):
    decisions: list[ClassifierDecision] = Field(default_factory=list)


# ── Raw Extraction – Core Skills ──────────────────────────────────────────────

class SkillCount(BaseModel):
    technology: str
    count: int


class CoreSkillsOutput(BaseModel):
    skill_counts: list[SkillCount] = Field(default_factory=list)


# ── Extract Candidate Profile ─────────────────────────────────────────────────

class CandidateProfileData(BaseModel):
    """
    skill_gaps is a stringified JSON array — stored as a string to match
    the n8n behavior and the candidate_context value column (TEXT).
    Parse with json.loads() when you need the array.
    """
    name: str
    core_skills: str
    secondary_tools: str
    skill_gaps: str
    home_location: str
    commute_options: str
    target_format: str


class CandidateProfileOutput(BaseModel):
    candidate_profile: CandidateProfileData
    role_type_scores: dict[str, int]


# ── Profile row (from DB) ─────────────────────────────────────────────────────

class ProfileRow(BaseModel):
    """Full profile including candidate_context fields — for edit modal."""
    id: int
    first_name: str | None = None
    last_name: str | None = None
    email: str | None = None
    phone_country_code: str | None = "+49"
    phone_number: str | None = None
    street_address: str | None = None
    postal_code: str | None = None
    city: str | None = None
    linkedin_url: str | None = None
    github_url: str | None = None
    avatar_url: str | None = None
    cv_text: str | None = None
    market_research: str | None = None
    career_target: str | None = None


class ProfileSummary(BaseModel):
    """Minimal profile data for the selector dropdown."""
    id: int
    first_name: str | None = None
    last_name: str | None = None
    avatar_url: str | None = None
    street_address: str | None = None
    postal_code: str | None = None
    city: str | None = None
    email: str | None = None
    phone_country_code: str | None = None
    phone_number: str | None = None
    linkedin_url: str | None = None
    github_url: str | None = None

    @property
    def display_name(self) -> str:
        parts = [self.first_name or "", self.last_name or ""]
        name = " ".join(p for p in parts if p).strip()
        return name or f"Profil #{self.id}"
