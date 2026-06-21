"""
Format pipeline results into the markdown structure expected by the result UI.
Mirrors the n8n Format+Respond Code Node from the main workflow.
"""
from backend.models.analysis import ScoringResult
from backend.models.company import CompanyResearchResult
from backend.models.tailoring import TailoringResult

_THRESHOLD_EMOJI = {
    "pass": "✅",
    "caution": "⚠️",
    "fail": "❌",
}

_THRESHOLD_LABEL = {
    "pass": "Empfohlen",
    "caution": "Grenzfall",
    "fail": "Nicht empfohlen",
}

_DIM_LABEL_DE = {
    "technical": "Technisch",
    "requirements": "Anforderungen",
    "role_fit": "Rollenfit",
    "location": "Standort",
    "strategic": "Strategisch",
}

_DIM_MAX = {
    "technical": 40,
    "requirements": 25,
    "role_fit": 20,
    "location": 10,
    "strategic": 5,
}


def format_score_header(
    company: CompanyResearchResult,
    role_title: str,
    scoring: ScoringResult,
) -> str:
    """
    Build the ## score header block that the frontend parses with parseScoreHeader.js.
    Format must match exactly.
    """
    emoji = _THRESHOLD_EMOJI[scoring.threshold]
    label = _THRESHOLD_LABEL[scoring.threshold]
    dims = scoring.dims

    dim_rows = "\n".join(
        f"| {_DIM_LABEL_DE[k]} | {getattr(dims, k)}/{_DIM_MAX[k]} |"
        for k in ["technical", "requirements", "role_fit", "location", "strategic"]
    )

    return (
        f"## {role_title}\n\n"
        f"**{company.company_name}** · Score: {scoring.total_score}/100 {emoji} {label}\n\n"
        f"| Dimension | Score |\n"
        f"|---|---|\n"
        f"{dim_rows}\n"
    )


def format_pass_response(
    company: CompanyResearchResult,
    role_title: str,
    scoring: ScoringResult,
    tailoring: TailoringResult,
    anschreiben_text: str,
    cv_language: str = "de",
) -> str:
    """Build the full markdown response for pass/caution threshold."""
    header = format_score_header(company, role_title, scoring)

    cv_section_label = "Lebenslauf" if cv_language == "de" else "Curriculum Vitae"
    anschreiben_label = "Anschreiben" if cv_language == "de" else "Cover Letter"
    cv_diff_label = "CV-Anpassungen"

    return (
        f"{header}\n"
        f"---\n\n"
        f"## {cv_diff_label}\n\n"
        f"{tailoring.cv_diff}\n\n"
        f"---\n\n"
        f"## {anschreiben_label}\n\n"
        f"{anschreiben_text}\n\n"
        f"---\n\n"
        f"## {cv_section_label}\n\n"
        f"{tailoring.tailored_cv}\n"
    )


def format_fail_response(
    company: CompanyResearchResult,
    role_title: str,
    scoring: ScoringResult,
    gap_analysis: str,
) -> str:
    """Build the full markdown response for fail threshold."""
    header = format_score_header(company, role_title, scoring)
    return (
        f"{header}\n"
        f"---\n\n"
        f"## Lückenanalyse\n\n"
        f"{gap_analysis}\n"
    )
