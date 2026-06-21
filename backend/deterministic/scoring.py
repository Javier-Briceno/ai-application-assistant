"""
Deterministic scoring logic.
Ports the n8n Calculate Dimensions + Calculate Threshold Code Nodes.
No LLM calls — pure arithmetic on AnalyzerOutput.
"""
from typing import Literal

from backend.models.analysis import AnalyzerOutput, DimensionScores

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
