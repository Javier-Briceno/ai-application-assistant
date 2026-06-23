"""
Tests for the Anschreiben style-quality patches (patch 1 + patch 2 + patch 3).

Patch 1 (RULE 9-11):
A1 — Prompt explicitly forbids em dashes (—) and en dashes (–) (RULE 9)
A2 — Prompt lists forbidden AI-sounding cliché phrases (RULE 10)
A3 — Prompt contains natural sentence-rhythm guidance (RULE 11)
A4 — Deterministic em-dash guard strips em dashes from generated text
A5 — Guard logs a warning when em dashes are found
A6 — Text without em dashes passes through unchanged

Patch 2 (RULE 12):
B1 — Prompt discourages buzzword stacking
B2 — Prompt forbids "einzahlen auf"
B3 — Prompt forbids "entspricht genau dem"
B4 — Prompt limits overuse of "direkt", "genau", "konkret", "produktionsnah"
B5 — Patch 1 em-dash rule still intact after patch 2 changes

Patch 3 (RULE 9 extension + RULE 10 extension + RULE 12 density):
C1 — Prompt forbids en dash (–) in prose (RULE 9 updated)
C2 — Prompt forbids template connector phrases "genau das, womit", "genau in diesem Bereich", "passt zu den Aufgaben" (RULE 10 updated)
C3 — Prompt limits dense technical term lists to 2 terms per sentence (RULE 12 updated)

Patch 4 (STRUCTURE mandatory elements + RULE 10 variants + RULE 13):
D1 — Prompt explicitly requires the greeting "Sehr geehrte Damen und Herren,"
D2 — Prompt explicitly requires candidate full name after "Mit freundlichen Grüßen"
D3 — Prompt bans near-variants of "genau in diesem [X]" template constructions
D4 — Prompt bans near-variants of "passt [X] zu den Aufgaben" template constructions
"""
import logging
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ── A1: Prompt forbids em dashes and en dashes ───────────────────────────────

def test_prompt_forbids_em_dash():
    from backend.prompts.loader import load_prompt
    prompt = load_prompt("anschreiben")
    assert "—" in prompt or "em dash" in prompt.lower(), (
        "Prompt must explicitly mention the em dash character or 'em dash' to forbid it"
    )
    assert "–" in prompt or "en dash" in prompt.lower(), (
        "Prompt must explicitly mention the en dash character or 'en dash' to forbid it"
    )
    assert "RULE 9" in prompt


# ── A2: Prompt lists specific forbidden clichés ───────────────────────────────

def test_prompt_forbids_ai_cliches():
    from backend.prompts.loader import load_prompt
    prompt = load_prompt("anschreiben")
    forbidden = [
        "mit großer Begeisterung",
        "ich bin überzeugt",
        "perfekte Ergänzung",
        "spannende Herausforderung",
        "maßgeschneiderte Lösung",
        "genau das, womit",
        "genau in diesem Bereich",
        "passt zu den Aufgaben",
    ]
    for phrase in forbidden:
        assert phrase in prompt, (
            f"Prompt must list the forbidden cliché phrase: {phrase!r}"
        )
    assert "RULE 10" in prompt


# ── A3: Prompt contains sentence-rhythm / natural-style guidance ──────────────

def test_prompt_contains_rhythm_guidance():
    from backend.prompts.loader import load_prompt
    prompt = load_prompt("anschreiben")
    assert "RULE 11" in prompt
    assert "rhythm" in prompt.lower() or "Vary sentence" in prompt or "sentence" in prompt.lower()


# ── A4: Em-dash guard strips em dashes from generated text ────────────────────

@pytest.mark.asyncio
async def test_em_dash_stripped_from_output():
    from backend.pipeline.anschreiben import run_anschreiben
    from backend.models.company import CompanyResearchResult

    raw_with_em_dash = "Ich entwickle skalierbare Systeme — zuverlässig und effizient."
    expected_clean    = "Ich entwickle skalierbare Systeme , zuverlässig und effizient."

    with patch("backend.pipeline.anschreiben.llm.call_raw", AsyncMock(return_value=raw_with_em_dash)):
        result = await run_anschreiben(
            MagicMock(),
            job_posting="Software Engineer role",
            cv_text="Python developer",
            career_target="Software Engineer",
            candidate_profile={"name": "Test User"},
            company_result=CompanyResearchResult(company_name="Acme", company_profile=""),
        )

    assert "—" not in result
    assert result == expected_clean


# ── A5: Guard logs a warning when em dashes are present ──────────────────────

@pytest.mark.asyncio
async def test_em_dash_guard_logs_warning():
    from backend.pipeline.anschreiben import run_anschreiben
    from backend.models.company import CompanyResearchResult

    raw_with_em_dash = "Ergebnis — sehr gut."
    captured: list[str] = []

    class _CaptureLogs(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            if record.levelno >= logging.WARNING:
                captured.append(record.getMessage())

    import backend.pipeline.anschreiben as _mod
    logger = logging.getLogger(_mod.__name__)
    handler = _CaptureLogs()
    logger.addHandler(handler)
    old_level = logger.level
    logger.setLevel(logging.WARNING)

    try:
        with patch("backend.pipeline.anschreiben.llm.call_raw", AsyncMock(return_value=raw_with_em_dash)):
            await run_anschreiben(
                MagicMock(),
                job_posting="role",
                cv_text="cv",
                career_target="target",
                candidate_profile={},
                company_result=CompanyResearchResult(company_name="Co", company_profile=""),
            )
    finally:
        logger.setLevel(old_level)
        logger.removeHandler(handler)

    assert any("em dash" in msg.lower() for msg in captured), (
        "Expected a warning log mentioning 'em dash' when the character is found in output"
    )


# ── A6: Clean text passes through unchanged ───────────────────────────────────

@pytest.mark.asyncio
async def test_clean_text_unchanged():
    from backend.pipeline.anschreiben import run_anschreiben
    from backend.models.company import CompanyResearchResult

    clean = "Ich bewerbe mich als Python-Entwickler. Meine Erfahrung umfasst fünf Jahre."

    with patch("backend.pipeline.anschreiben.llm.call_raw", AsyncMock(return_value=clean)):
        result = await run_anschreiben(
            MagicMock(),
            job_posting="role",
            cv_text="cv",
            career_target="target",
            candidate_profile={},
            company_result=CompanyResearchResult(company_name="Co", company_profile=""),
        )

    assert result == clean


# ── B1: Prompt discourages buzzword stacking ──────────────────────────────────

def test_prompt_discourages_buzzword_stacking():
    from backend.prompts.loader import load_prompt
    prompt = load_prompt("anschreiben")
    assert "RULE 12" in prompt
    assert "buzzword" in prompt.lower() or "stack" in prompt.lower() or "chains" in prompt.lower() or "chain" in prompt.lower()


# ── B2: Prompt forbids "einzahlen auf" ───────────────────────────────────────

def test_prompt_forbids_einzahlen_auf():
    from backend.prompts.loader import load_prompt
    prompt = load_prompt("anschreiben")
    assert "einzahlen auf" in prompt, (
        "Prompt must explicitly call out 'einzahlen auf' as a forbidden corporate filler verb"
    )


# ── B3: Prompt forbids "entspricht genau dem" ────────────────────────────────

def test_prompt_forbids_entspricht_genau():
    from backend.prompts.loader import load_prompt
    prompt = load_prompt("anschreiben")
    assert "entspricht genau" in prompt, (
        "Prompt must explicitly forbid the formulaic phrase 'entspricht genau dem'"
    )


# ── B4: Prompt limits intensifier overuse ────────────────────────────────────

def test_prompt_limits_intensifier_overuse():
    from backend.prompts.loader import load_prompt
    prompt = load_prompt("anschreiben")
    # All four problem intensifiers should be named
    for word in ("direkt", "genau", "konkret", "produktionsnah"):
        assert word in prompt, (
            f"Prompt must mention the overused intensifier {word!r} as a word to limit"
        )


# ── B5: Patch 1 em-dash rule still intact after patch 2 ──────────────────────

def test_em_dash_rule_still_present_after_patch2():
    from backend.prompts.loader import load_prompt
    prompt = load_prompt("anschreiben")
    assert "RULE 9" in prompt
    assert "—" in prompt or "em dash" in prompt.lower()


# ── C1: Prompt forbids en dash (–) in prose ──────────────────────────────────

def test_prompt_forbids_en_dash():
    from backend.prompts.loader import load_prompt
    prompt = load_prompt("anschreiben")
    assert "–" in prompt or "en dash" in prompt.lower(), (
        "Prompt must explicitly forbid the en dash character (–) in prose"
    )
    assert "RULE 9" in prompt


# ── C2: Prompt forbids template connector phrases ─────────────────────────────

def test_prompt_forbids_template_connectors():
    from backend.prompts.loader import load_prompt
    prompt = load_prompt("anschreiben")
    template_phrases = [
        "genau das, womit",
        "genau in diesem Bereich",
        "genau in diesem Kontext",
        "passt zu den Aufgaben",
        "passt direkt zu den Aufgaben",
    ]
    for phrase in template_phrases:
        assert phrase in prompt, (
            f"Prompt must forbid the template connector phrase: {phrase!r}"
        )


# ── C3: Prompt limits dense technical term lists ──────────────────────────────

def test_prompt_limits_technical_term_density():
    from backend.prompts.loader import load_prompt
    prompt = load_prompt("anschreiben")
    assert "2 technical terms" in prompt or "two technical terms" in prompt.lower() or "Maximum 2" in prompt, (
        "Prompt must explicitly limit the number of technical terms per sentence (max 2)"
    )


# ── D1: Prompt requires the greeting line ────────────────────────────────────

def test_prompt_requires_greeting():
    from backend.prompts.loader import load_prompt
    prompt = load_prompt("anschreiben")
    assert "Sehr geehrte Damen und Herren" in prompt, (
        "Prompt must require the greeting 'Sehr geehrte Damen und Herren,'"
    )
    assert "RULE 13" in prompt or "greeting" in prompt.lower(), (
        "Prompt must treat the greeting as mandatory (RULE 13 or explicit 'greeting' instruction)"
    )


# ── D2: Prompt requires candidate full name after closing formula ─────────────

def test_prompt_requires_candidate_name_in_closing():
    from backend.prompts.loader import load_prompt
    prompt = load_prompt("anschreiben")
    assert "Mit freundlichen Grüßen" in prompt, (
        "Prompt must include the closing formula 'Mit freundlichen Grüßen'"
    )
    assert "full name" in prompt.lower() or "candidate full name" in prompt.lower() or "Kandidatenname" in prompt, (
        "Prompt must require the candidate's full name after 'Mit freundlichen Grüßen'"
    )
    assert "RULE 13" in prompt


# ── D3: Prompt bans "genau in diesem [X]" variant constructions ───────────────

def test_prompt_bans_genau_in_diesem_variants():
    from backend.prompts.loader import load_prompt
    prompt = load_prompt("anschreiben")
    for variant in ("genau in diesem Kontext", "genau in diesem Zusammenhang"):
        assert variant in prompt, (
            f"Prompt must explicitly name the forbidden variant {variant!r} "
            "or instruct the model to avoid all 'genau in diesem [X]' constructions"
        )


# ── D4: Prompt bans "passt [X] zu den Aufgaben" variant constructions ─────────

def test_prompt_bans_passt_zu_variants():
    from backend.prompts.loader import load_prompt
    prompt = load_prompt("anschreiben")
    assert "passt direkt zu den Aufgaben" in prompt, (
        "Prompt must explicitly name 'passt direkt zu den Aufgaben' as a forbidden variant"
    )
    assert "passt gut zu" in prompt, (
        "Prompt must explicitly name 'passt gut zu' as a forbidden variant"
    )
