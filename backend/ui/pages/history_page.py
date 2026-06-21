"""
Application history page (/verlauf).
Lists all job_applications for the active profile, newest first.
Each row expands to show score breakdown, CV diff, Anschreiben, and gap analysis.
"""
import logging
from datetime import datetime

from nicegui import app, ui

from backend.db import get_conn
from backend.ui.components.nav import add_nav

log = logging.getLogger(__name__)

_THRESHOLD_COLOR = {"pass": "positive", "caution": "warning", "fail": "negative"}
_THRESHOLD_LABEL = {"pass": "✅ Empfohlen", "caution": "⚠️ Grenzfall", "fail": "❌ Nicht empfohlen"}


async def _fetch_applications(profile_id: int) -> list[dict]:
    async with get_conn() as conn:
        rows = await conn.fetch(
            """
            SELECT id, company, role_title, score, threshold,
                   date_applied, cv_diff, anschreiben, gaps, notes
            FROM job_application_assistant.job_applications
            WHERE profile_id = $1
            ORDER BY date_applied DESC
            """,
            profile_id,
        )
    return [dict(r) for r in rows]


async def _fetch_profiles() -> dict[int, str]:
    async with get_conn() as conn:
        rows = await conn.fetch(
            "SELECT id, first_name, last_name FROM job_application_assistant.profiles ORDER BY last_name, first_name"
        )
    return {
        r["id"]: f"{r['first_name'] or ''} {r['last_name'] or ''}".strip() or f"Profil #{r['id']}"
        for r in rows
    }


def _render_diff(diff_text: str, container) -> None:
    with container:
        if not diff_text or not diff_text.strip():
            ui.label("Keine Lebenslauf-Änderungen aufgezeichnet.").classes("text-xs text-gray-500")
            return
        with ui.element("div").classes("font-mono text-xs leading-5 p-2 bg-gray-900 rounded"):
            for line in diff_text.splitlines():
                if line.startswith("+ "):
                    ui.label(line).classes("text-green-400")
                elif line.startswith("- "):
                    ui.label(line).classes("text-red-400")
                else:
                    ui.label(line).classes("text-gray-500")


@ui.page("/verlauf")
async def history_page() -> None:
    add_nav(current="history")

    ui.add_head_html("""
    <style>
      body { background: #0f0f11; color: #e8e8ea; }
    </style>
    """)

    stored_id = app.storage.user.get("active_profile_id")
    profiles = await _fetch_profiles()

    # ── Profile selector ──────────────────────────────────────────────────────
    selected_id: list[int | None] = [int(stored_id) if stored_id else None]

    # Applications container (refreshable)
    apps_container = ui.element("div").classes("w-full max-w-5xl mx-auto mt-4")

    async def load_apps() -> None:
        pid = selected_id[0]
        apps_container.clear()

        if not pid:
            with apps_container:
                ui.label("Bitte oben ein Profil auswählen.").classes("text-gray-500 text-sm mt-8 text-center")
            return

        applications = await _fetch_applications(pid)

        with apps_container:
            if not applications:
                with ui.element("div").classes("text-center mt-16 text-gray-500"):
                    ui.label("Noch keine Bewerbungen für dieses Profil.").classes("text-sm")
                return

            ui.label(f"{len(applications)} Bewerbung{'en' if len(applications) != 1 else ''}").classes(
                "text-sm text-gray-400 mb-3"
            )

            for a in applications:
                threshold = a["threshold"] or "fail"
                score = a["score"] or 0
                color = _THRESHOLD_COLOR.get(threshold, "negative")
                label = _THRESHOLD_LABEL.get(threshold, "❌")
                date_str = ""
                if a["date_applied"]:
                    dt = a["date_applied"]
                    if isinstance(dt, datetime):
                        date_str = dt.strftime("%d.%m.%Y")

                with ui.expansion(caption=date_str).classes("w-full mb-2") as exp:
                    # Expansion header row (title slot)
                    with exp.add_slot("header"):
                        with ui.row().classes("w-full items-center gap-3"):
                            # Score badge
                            with ui.element("div").classes("text-center min-w-12"):
                                ui.label(str(score)).classes(f"text-lg font-bold text-{color}")
                                ui.label("/100").classes("text-xs text-gray-500 leading-none")

                            # Company + role
                            with ui.column().classes("flex-1 gap-0"):
                                ui.label(a["company"] or "—").classes("text-sm font-semibold")
                                ui.label(a["role_title"] or "—").classes("text-xs text-gray-400")

                            ui.badge(label, color=color).classes("text-xs")
                            ui.label(date_str).classes("text-xs text-gray-500 min-w-20 text-right")

                    # Expansion body
                    with ui.tabs().classes("w-full") as tabs:
                        tab_diff = ui.tab("Lebenslauf-Diff")
                        tab_letter = ui.tab("Anschreiben")
                        if a["gaps"]:
                            tab_gaps = ui.tab("Lückenanalyse")

                    with ui.tab_panels(tabs, value=tab_diff).classes("w-full"):
                        with ui.tab_panel(tab_diff):
                            diff_box = ui.element("div")
                            _render_diff(a["cv_diff"] or "", diff_box)

                        with ui.tab_panel(tab_letter):
                            if a["anschreiben"]:
                                ui.label(a["anschreiben"]).classes(
                                    "text-sm whitespace-pre-wrap font-sans leading-6"
                                )
                            else:
                                ui.label("Kein Anschreiben (Bewerbung nicht empfohlen).").classes(
                                    "text-xs text-gray-500"
                                )

                        if a["gaps"]:
                            with ui.tab_panel(tab_gaps):
                                ui.label(a["gaps"]).classes("text-sm leading-6")

    # ── Header ────────────────────────────────────────────────────────────────
    with ui.element("div").classes("max-w-5xl mx-auto px-4 pt-6"):
        with ui.row().classes("items-center gap-4 mb-4"):
            ui.label("Bewerbungsverlauf").classes("text-xl font-bold")

            async def on_profile_change(e):
                selected_id[0] = e.value
                app.storage.user["active_profile_id"] = e.value
                await load_apps()

            ui.select(
                options=profiles,
                value=selected_id[0],
                label="Profil",
                on_change=on_profile_change,
            ).classes("min-w-48")

    await load_apps()
