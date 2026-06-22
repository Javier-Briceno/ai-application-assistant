"""
Deterministic scoring logic.
Ports the n8n Calculate Dimensions + Calculate Threshold Code Nodes.
No LLM calls — pure arithmetic on AnalyzerOutput.
"""
from typing import Literal

from backend.models.analysis import AnalyzerOutput, DimensionScores
from backend.models.requirements import RequirementsAnalysis

# Dimension maximums (hard constraint — must match the Analyzer prompt and frontend)
DIM_MAX = {
    "technical": 40,
    "requirements": 25,
    "role_fit": 20,
    "location": 10,
    "strategic": 5,
}

# Threshold rules (mirrors n8n Calculate Threshold Code Node)
PASS_MIN_TOTAL = 60
CAUTION_MIN_TOTAL = 45
# A dimension score of 0 in technical or requirements is a hard fail signal
CRITICAL_DIMS = {"technical", "requirements"}


def calculate_dimensions(output: AnalyzerOutput) -> DimensionScores:
    """
    Extract and clamp dimension scores from AnalyzerOutput.
    Clamping ensures LLM can't return out-of-range values.
    """
    return DimensionScores(
        technical=max(0, min(output.technical.score, DIM_MAX["technical"])),
        requirements=max(0, min(output.requirements.score, DIM_MAX["requirements"])),
        role_fit=max(0, min(output.role_fit.score, DIM_MAX["role_fit"])),
        location=max(0, min(output.location.score, DIM_MAX["location"])),
        strategic=max(0, min(output.strategic.score, DIM_MAX["strategic"])),
    )


def apply_requirements_override(
    threshold: Literal["pass", "caution", "fail"],
    requirements_analysis: RequirementsAnalysis | None,
) -> Literal["pass", "caution", "fail"]:
    """
    Adjust the score-based threshold for explicit requirement failures.

    Rules (applied in order):
      1. triggered_dealbreakers present, base was already "fail" → keep "fail"
      2. triggered_dealbreakers present, base was "pass"/"caution" → downgrade to
         "caution" (NOT "fail"), so document generation still proceeds.
         The dealbreaker is surfaced via requirements_analysis in the UI.
      3. missing_hard_requirements and threshold == "pass" → downgrade to "caution"
      4. Everything else → leave threshold unchanged

    Rationale for rule 2: a single Haiku check should never silently kill
    generation.  The Analyzer (GPT-4.1) already captured the requirement signal
    in the requirements dimension score.  When the Haiku check fires a dealbreaker
    on a base that was pass/caution, it records the blocker prominently for the
    user while still producing the CV and cover letter.
    """
    if requirements_analysis is None:
        return threshold
    if requirements_analysis.triggered_dealbreakers:
        if threshold == "fail":
            return "fail"
        return "caution"
    if requirements_analysis.missing_hard_requirements and threshold == "pass":
        return "caution"
    return threshold


def calculate_threshold(dims: DimensionScores) -> Literal["pass", "caution", "fail"]:
    """
    Determine pass / caution / fail from dimension scores.
    Mirrors the n8n Calculate Threshold Code Node logic.
    """
    total = dims.total
    has_critical_zero = any(
        getattr(dims, dim) == 0 for dim in CRITICAL_DIMS
    )

    if total >= PASS_MIN_TOTAL and not has_critical_zero:
        return "pass"

    if total >= CAUTION_MIN_TOTAL and not has_critical_zero:
        return "caution"

    # Secondary caution: high total but one critical dim at zero
    if total >= PASS_MIN_TOTAL and has_critical_zero:
        return "caution"

    return "fail"
