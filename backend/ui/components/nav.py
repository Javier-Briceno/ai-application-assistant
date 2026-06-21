"""Shared top navigation bar added to every page."""
from nicegui import ui


def add_nav(current: str = "main") -> None:
    """
    Render a slim top nav bar.
    current: 'main' | 'history'
    """
    with ui.header().classes("bg-gray-900 border-b border-gray-800 px-4 py-2"):
        with ui.row().classes("w-full items-center justify-between"):
            with ui.row().classes("items-center gap-3"):
                ui.label("🧠").classes("text-xl")
                ui.label("Bewerbungsassistent").classes("text-sm font-semibold text-gray-200")

            with ui.row().classes("gap-1"):
                ui.button(
                    "Analyse",
                    icon="search",
                    on_click=lambda: ui.navigate.to("/"),
                ).props(
                    f"flat size=sm {'color=primary' if current == 'main' else ''}"
                )
                ui.button(
                    "Verlauf",
                    icon="history",
                    on_click=lambda: ui.navigate.to("/verlauf"),
                ).props(
                    f"flat size=sm {'color=primary' if current == 'history' else ''}"
                )
