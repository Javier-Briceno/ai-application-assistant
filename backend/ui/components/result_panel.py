"""
NiceGUI result panel: score header + CV diff + Anschreiben + CV full text.
Mirrors the JS components: ScoreHeader.js, MarkdownContent.js.
"""
from nicegui import ui

from backend.models.analysis import ScoringResult
from backend.models.company import CompanyResearchResult
from backend.models.tailoring import TailoringResult
from backend.pipeline.main_pipeline import PipelineResult
from backend.ui.docx_export import generate_anschreiben_docx, generate_cv_docx

_THRESHOLD_COLOR = {
    "pass": "positive",
    "caution": "warning",
    "fail": "negative",
}

_THRESHOLD_LABEL = {
    "pass": "✅ Empfohlen",
    "caution": "⚠️ Grenzfall",
    "fail": "❌ Nicht empfohlen",
}

_DIM_LABEL = {
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


def render_result(container: ui.element, result: PipelineResult, candidate_name: str = "") -> None:
    """Clear the result container and render the full pipeline result."""
    container.clear()

    with container:
        scoring = result.scoring
        company = result.company
        dims = scoring.dims

        # ── Score header ──────────────────────────────────────────────────────
        with ui.card().classes("w-full mb-4"):
            with ui.row().classes("items-start gap-4"):
                # Score circle
                color = _THRESHOLD_COLOR[scoring.threshold]
                with ui.element("div").classes("text-center"):
                    ui.label(str(scoring.total_score)).classes(
                        f"text-5xl font-bold text-{color}"
                    )
                    ui.label("/100").classes("text-xs text-gray-400")

                # Company + role + threshold
                with ui.column().classes("flex-1"):
                    ui.label(company.company_name).classes("text-lg font-semibold")
                    ui.label(_extract_role(result)).classes("text-sm text-gray-300")
                    ui.badge(
                        _THRESHOLD_LABEL[scoring.threshold], color=color
                    ).classes("mt-1")

                    # Score bar
                    with ui.element("div").classes("w-full mt-2 bg-gray-700 rounded h-2"):
                        ui.element("div").classes(
                            f"bg-{color} h-2 rounded"
                        ).style(f"width: {scoring.total_score}%")

            # Dimension grid
            with ui.row().classes("w-full mt-3 gap-2 flex-wrap"):
                for dim_key in ["technical", "requirements", "role_fit", "location", "strategic"]:
                    score_val = getattr(dims, dim_key)
                    max_val = _DIM_MAX[dim_key]
                    with ui.card().classes("flex-1 min-w-20 text-center p-2"):
                        ui.label(_DIM_LABEL[dim_key]).classes("text-xs text-gray-400")
                        ui.label(f"{score_val}/{max_val}").classes("text-sm font-bold")

        # ── Gap analysis (fail path) ──────────────────────────────────────────
        if result.gap_analysis:
            with ui.card().classes("w-full mb-4"):
                ui.label("Lückenanalyse").classes("text-base font-semibold mb-2")
                ui.markdown(result.gap_analysis).classes("text-sm")
            return  # no tailoring / anschreiben on fail

        # ── CV Diff ───────────────────────────────────────────────────────────
        if result.tailoring:
            with ui.card().classes("w-full mb-4"):
                with ui.row().classes("w-full items-center justify-between mb-2"):
                    ui.label("CV-Anpassungen").classes("text-base font-semibold")
                    ui.button(
                        "Lebenslauf (.docx)",
                        icon="download",
                        on_click=lambda: _download_cv(result, candidate_name),
                    ).props("flat size=sm")

                _render_diff(result.tailoring.cv_diff)

        # ── Anschreiben ───────────────────────────────────────────────────────
        if result.anschreiben_text:
            with ui.card().classes("w-full mb-4"):
                with ui.row().classes("w-full items-center justify-between mb-2"):
                    ui.label("Anschreiben").classes("text-base font-semibold")
                    ui.button(
                        "Anschreiben (.docx)",
                        icon="download",
                        on_click=lambda: _download_anschreiben(result, candidate_name),
                    ).props("flat size=sm")

                with ui.element("div").classes("anschreiben-text text-sm whitespace-pre-wrap"):
                    ui.label(result.anschreiben_text)


def _render_diff(diff_text: str) -> None:
    """Render colored diff lines: + green, - red, neutral gray."""
    if not diff_text.strip():
        ui.label("Keine Änderungen.").classes("text-sm text-gray-400")
        return

    with ui.element("div").classes("font-mono text-xs leading-5"):
        for line in diff_text.splitlines():
            if line.startswith("+ "):
                ui.label(line).classes("text-green-400")
            elif line.startswith("- "):
                ui.label(line).classes("text-red-400")
            else:
                ui.label(line).classes("text-gray-400")


def _extract_role(result: PipelineResult) -> str:
    """Best-effort role title from the scored posting."""
    return result.scoring.analyzer_output.role_fit.matched_role_key or "Stelle"


def _download_cv(result: PipelineResult, candidate_name: str) -> None:
    if not result.tailoring:
        return
    content = generate_cv_docx(result.tailoring.tailored_cv, candidate_name)
    ui.download(content, "Lebenslauf.docx")


def _download_anschreiben(result: PipelineResult, candidate_name: str) -> None:
    if not result.anschreiben_text:
        return
    content = generate_anschreiben_docx(
        result.anschreiben_text,
        candidate_name=candidate_name,
        company_name=result.company.company_name,
    )
    ui.download(content, "Anschreiben.docx")
