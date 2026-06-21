"""
NiceGUI profile form dialog.
Handles both CREATE and UPDATE modes.
All labels are German. Avatar resized server-side via Pillow.
"""
import asyncio
import logging
from typing import Callable

from nicegui import ui

from backend.db import get_conn
from backend.models.profile import ProfileRow
from backend.pipeline.profile_extraction import run_profile_setup
from backend.ui.components.avatar import process_avatar

log = logging.getLogger(__name__)


def open_profile_modal(
    *,
    mode: str = "create",
    existing: ProfileRow | None = None,
    on_saved: Callable | None = None,
) -> None:
    """
    Open the profile creation/editing dialog.

    mode: 'create' | 'edit'
    existing: ProfileRow — required for edit mode
    on_saved: async callable(profile_id) — called after successful save
    """
    is_edit = mode == "edit"
    title = "Profil bearbeiten" if is_edit else "Neues Profil anlegen"

    # Local state
    avatar_data_url: list[str | None] = [existing.avatar_url if existing else None]
    status_msgs: list[str] = []

    with ui.dialog().props("maximized") as dialog, ui.card().classes("w-full max-w-3xl mx-auto"):

        # ── Header ────────────────────────────────────────────────────────────
        with ui.row().classes("w-full items-center justify-between mb-4"):
            ui.label(title).classes("text-xl font-bold")
            ui.button(icon="close", on_click=dialog.close).props("flat round")

        # ── Avatar upload ─────────────────────────────────────────────────────
        avatar_preview = ui.image(
            avatar_data_url[0] or ""
        ).classes("w-24 h-24 rounded-full object-cover mb-2").style(
            "display: block;" if avatar_data_url[0] else "display: none;"
        )
        avatar_placeholder = ui.icon("account_circle").classes(
            "text-8xl text-gray-400 mb-2"
        ).style("" if not avatar_data_url[0] else "display: none;")

        def handle_upload(e):
            try:
                data_url = process_avatar(e.content.read())
                avatar_data_url[0] = data_url
                avatar_preview.set_source(data_url)
                avatar_preview.style("display: block;")
                avatar_placeholder.style("display: none;")
            except ValueError as exc:
                ui.notify(str(exc), type="negative")

        ui.upload(
            label="Foto hochladen",
            on_upload=handle_upload,
            auto_upload=True,
        ).props("accept=image/* flat").classes("mb-4")

        # ── Basic info ────────────────────────────────────────────────────────
        with ui.row().classes("w-full gap-4"):
            inp_first = ui.input(
                "Vorname *", value=existing.first_name or "" if existing else ""
            ).classes("flex-1")
            inp_last = ui.input(
                "Nachname *", value=existing.last_name or "" if existing else ""
            ).classes("flex-1")

        inp_career = ui.input(
            "Karriereziel *",
            value=existing.career_target or "" if existing else "",
        ).classes("w-full")

        # ── Contact ───────────────────────────────────────────────────────────
        with ui.row().classes("w-full gap-4"):
            inp_code = ui.input(
                "Vorwahl",
                value=existing.phone_country_code or "+49" if existing else "+49",
            ).classes("w-24")
            inp_phone = ui.input(
                "Telefon",
                value=existing.phone_number or "" if existing else "",
            ).classes("flex-1")

        inp_email = ui.input(
            "E-Mail",
            value=existing.email or "" if existing else "",
        ).classes("w-full")

        # ── Address ───────────────────────────────────────────────────────────
        with ui.row().classes("w-full gap-4"):
            inp_street = ui.input(
                "Straße",
                value=existing.street_address or "" if existing else "",
            ).classes("flex-1")
            inp_postal = ui.input(
                "PLZ",
                value=existing.postal_code or "" if existing else "",
            ).classes("w-28")
            inp_city = ui.input(
                "Stadt",
                value=existing.city or "" if existing else "",
            ).classes("flex-1")

        # ── Social ────────────────────────────────────────────────────────────
        with ui.row().classes("w-full gap-4"):
            inp_linkedin = ui.input(
                "LinkedIn-URL",
                value=existing.linkedin_url or "" if existing else "",
            ).classes("flex-1")
            inp_github = ui.input(
                "GitHub-URL",
                value=existing.github_url or "" if existing else "",
            ).classes("flex-1")

        # ── CV text ───────────────────────────────────────────────────────────
        inp_cv = ui.textarea(
            "Lebenslauf (Text) *",
            value=existing.cv_text or "" if existing else "",
        ).classes("w-full").props("rows=12 outlined")

        # ── Market research ───────────────────────────────────────────────────
        inp_market = ui.textarea(
            "Marktrecherche *",
            value=existing.market_research or "" if existing else "",
        ).classes("w-full").props("rows=10 outlined")

        # ── Status area ───────────────────────────────────────────────────────
        status_label = ui.label("").classes("text-sm text-gray-500 mt-2")
        spinner = ui.spinner(size="sm").classes("mt-1")
        spinner.visible = False

        # ── Actions ───────────────────────────────────────────────────────────
        with ui.row().classes("w-full gap-3 mt-4 justify-end"):
            btn_cancel = ui.button(
                "Abbrechen", on_click=dialog.close
            ).props("flat")
            btn_save = ui.button("Speichern", color="primary")

        async def save() -> None:
            # Validate required fields
            required = {
                "Vorname": inp_first.value,
                "Nachname": inp_last.value,
                "Karriereziel": inp_career.value,
                "Lebenslauf": inp_cv.value,
                "Marktrecherche": inp_market.value,
            }
            missing = [k for k, v in required.items() if not v.strip()]
            if missing:
                ui.notify(
                    f"Pflichtfelder fehlen: {', '.join(missing)}", type="warning"
                )
                return

            btn_save.disable()
            btn_cancel.disable()
            spinner.visible = True

            def on_step(msg: str) -> None:
                status_label.set_text(msg)

            try:
                async with get_conn() as conn:
                    result = await run_profile_setup(
                        conn,
                        first_name=inp_first.value.strip(),
                        last_name=inp_last.value.strip(),
                        email=inp_email.value.strip() or None,
                        phone_country_code=inp_code.value.strip() or "+49",
                        phone_number=inp_phone.value.strip() or None,
                        street_address=inp_street.value.strip() or None,
                        postal_code=inp_postal.value.strip() or None,
                        city=inp_city.value.strip() or None,
                        linkedin_url=inp_linkedin.value.strip() or None,
                        github_url=inp_github.value.strip() or None,
                        avatar_url=avatar_data_url[0],
                        cv_text=inp_cv.value.strip(),
                        market_research=inp_market.value.strip(),
                        career_target=inp_career.value.strip(),
                        profile_id=existing.id if is_edit else None,
                        on_step=on_step,
                    )

                action_label = "aktualisiert" if result.action == "updated" else "erstellt"
                ui.notify(
                    f"Profil erfolgreich {action_label}!", type="positive"
                )
                dialog.close()
                if on_saved:
                    if asyncio.iscoroutinefunction(on_saved):
                        await on_saved(result.profile_id)
                    else:
                        on_saved(result.profile_id)

            except Exception as exc:
                log.exception("Profile save failed")
                ui.notify(f"Fehler: {exc}", type="negative")
                status_label.set_text("Fehler beim Speichern.")
            finally:
                spinner.visible = False
                btn_save.enable()
                btn_cancel.enable()

        btn_save.on_click(save)

    dialog.open()
