"""
NiceGUI main application page.
Two-panel layout: left (profile + job posting), right (result).
German UI throughout.
"""
import logging

from nicegui import app, ui

from backend.db import get_conn
from backend.models.profile import ProfileSummary
from backend.pipeline.main_pipeline import run_main_pipeline
from backend.pipeline.profile_extraction import get_profile, list_profiles
from backend.ui.components.nav import add_nav
from backend.ui.components.profile_modal import open_profile_modal
from backend.ui.components.result_panel import render_result

log = logging.getLogger(__name__)


def _register_styles() -> None:
    ui.add_head_html("""
    <style>
      body { background: #0f0f11; color: #e8e8ea; }
      .app-shell { display: flex; height: 100vh; overflow: hidden; }
      .panel { flex: 1; overflow-y: auto; padding: 1.5rem; }
      .panel--input { border-right: 1px solid #2a2a2e; min-width: 380px; max-width: 520px; }
      .panel--result { flex: 2; }
      .app-title { font-size: 1.4rem; font-weight: 700; letter-spacing: -0.02em; }
      .app-subtitle { font-size: 0.75rem; color: #888; margin-top: 0.1rem; }
      .profile-bar { display: flex; align-items: center; gap: 0.5rem; margin: 1rem 0; }
      .empty-state { display: flex; flex-direction: column; align-items: center;
                     justify-content: center; height: 60vh; color: #444; text-align: center; }
      .empty-state__glyph { font-size: 3rem; margin-bottom: 1rem; }
      .posting-textarea .q-field__native { min-height: 260px !important; font-size: 0.85rem; }
    </style>
    """)


@ui.page("/")
async def main_page() -> None:
    _register_styles()
    add_nav(current="main")

    # ── Page-level state ──────────────────────────────────────────────────────
    profiles: list[ProfileSummary] = []
    profile_options: dict[int, str] = {}
    selected_id: list[int | None] = [None]
    is_submitting: list[bool] = [False]

    stored_id = app.storage.user.get("active_profile_id")
    if stored_id:
        selected_id[0] = int(stored_id)

    async def load_profiles() -> None:
        nonlocal profiles, profile_options
        async with get_conn() as conn:
            profiles = await list_profiles(conn)
        profile_options.clear()
        profile_options.update({p.id: p.display_name for p in profiles})

        if selected_id[0] and selected_id[0] not in profile_options:
            selected_id[0] = None
            app.storage.user["active_profile_id"] = None

        profile_select.set_options(profile_options, value=selected_id[0])
        profile_select.update()

    async def on_profile_changed(e) -> None:
        selected_id[0] = e.value
        app.storage.user["active_profile_id"] = e.value
        btn_edit.set_enabled(e.value is not None)
        btn_analyze.set_enabled(e.value is not None and not is_submitting[0])

    async def open_create() -> None:
        async def after_save(pid: int):
            selected_id[0] = pid
            app.storage.user["active_profile_id"] = pid
            await load_profiles()

        open_profile_modal(mode="create", on_saved=after_save)

    async def open_edit() -> None:
        if not selected_id[0]:
            return
        async with get_conn() as conn:
            existing = await get_profile(conn, selected_id[0])
        if not existing:
            ui.notify("Profil nicht gefunden.", type="negative")
            return

        async def after_edit(_pid: int):
            await load_profiles()

        open_profile_modal(mode="edit", existing=existing, on_saved=after_edit)

    async def analyze() -> None:
        if is_submitting[0]:
            return
        if not selected_id[0]:
            ui.notify("Bitte zuerst ein Profil auswählen.", type="warning")
            return
        posting = posting_textarea.value.strip()
        if not posting:
            ui.notify("Bitte Stellenanzeige einfügen.", type="warning")
            return

        is_submitting[0] = True
        btn_analyze.set_enabled(False)
        btn_analyze.set_text("Analysiert...")

        # Show loading state in result panel
        result_container.clear()
        with result_container:
            with ui.element("div").classes("empty-state"):
                ui.spinner(size="xl")
                status_label_ref = ui.label("Analyse wird gestartet...").classes(
                    "text-sm text-gray-400 mt-4"
                )

        def on_step(msg: str) -> None:
            try:
                status_label_ref.set_text(msg)
            except Exception:
                pass

        try:
            async with get_conn() as conn:
                result = await run_main_pipeline(
                    conn,
                    profile_id=selected_id[0],
                    job_posting=posting,
                    on_step=on_step,
                )

            # Fetch candidate name for DOCX filenames
            candidate_name = ""
            for p in profiles:
                if p.id == selected_id[0]:
                    candidate_name = p.display_name
                    break

            render_result(result_container, result, candidate_name)

        except Exception as exc:
            log.exception("Pipeline failed")
            result_container.clear()
            with result_container:
                with ui.element("div").classes("empty-state"):
                    ui.icon("error_outline").classes("text-5xl text-red-400 mb-3")
                    ui.label(f"Fehler: {exc}").classes("text-sm text-red-300 max-w-sm text-center")

        finally:
            is_submitting[0] = False
            btn_analyze.set_enabled(bool(selected_id[0]))
            btn_analyze.set_text("Analysieren & Paket erstellen")

    # ── Layout ────────────────────────────────────────────────────────────────
    with ui.element("div").classes("app-shell"):

        # ── Left panel ────────────────────────────────────────────────────────
        with ui.element("section").classes("panel panel--input"):

            with ui.element("header").classes("mb-4"):
                ui.element("h1").classes("app-title").text = "Bewerbungsassistent"
                ui.element("p").classes("app-subtitle").text = "Python · FastAPI · NiceGUI"

            # Profile bar
            with ui.element("div").classes("profile-bar"):
                profile_select = ui.select(
                    options=profile_options,
                    value=selected_id[0],
                    label="Aktives Profil",
                    on_change=on_profile_changed,
                ).classes("flex-1")

                btn_edit = ui.button(
                    icon="edit", on_click=open_edit
                ).props("flat round").tooltip("Profil bearbeiten")
                btn_edit.set_enabled(selected_id[0] is not None)

                ui.button(
                    icon="person_add", on_click=open_create
                ).props("flat round").tooltip("Neues Profil")

            # Job posting input
            ui.label("Stellenanzeige").classes("text-sm text-gray-400 mb-1 mt-4")
            posting_textarea = ui.textarea(
                placeholder=(
                    "Stellenanzeige hier einfügen — LinkedIn, StepStone, "
                    "Unternehmenswebsite, beliebiges Format..."
                ),
            ).classes("w-full posting-textarea").props("outlined autogrow")

            btn_analyze = ui.button(
                "Analysieren & Paket erstellen",
                on_click=analyze,
                color="primary",
            ).classes("w-full mt-3")
            btn_analyze.set_enabled(selected_id[0] is not None)

        # ── Right panel ───────────────────────────────────────────────────────
        with ui.element("section").classes("panel panel--result") as result_section:
            result_container = ui.element("div").classes("w-full")
            with result_container:
                with ui.element("div").classes("empty-state"):
                    ui.element("div").classes("empty-state__glyph").text = "∅"
                    ui.label(
                        "Stellenanzeige links einfügen und auf Analysieren klicken. "
                        "Score, Lebenslauf-Anpassungen und Anschreiben erscheinen hier."
                    ).classes("text-sm max-w-sm")

    await load_profiles()
