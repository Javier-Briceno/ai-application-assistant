"""
Tests for pure helper functions in backend/scripts/llm_cost_report.py.

These functions have no DB dependencies and can be tested directly.
"""
import pytest


# ── _fmt_ms ───────────────────────────────────────────────────────────────────

def test_fmt_ms_returns_em_dash_for_none():
    from backend.scripts.llm_cost_report import _fmt_ms
    assert _fmt_ms(None) == "—"


def test_fmt_ms_formats_sub_10s_as_milliseconds():
    from backend.scripts.llm_cost_report import _fmt_ms
    assert _fmt_ms(0) == "0ms"
    assert _fmt_ms(500) == "500ms"
    assert _fmt_ms(9999) == "9999ms"


def test_fmt_ms_formats_10s_and_above_as_seconds():
    from backend.scripts.llm_cost_report import _fmt_ms
    assert _fmt_ms(10000) == "10.0s"
    assert _fmt_ms(20600) == "20.6s"
    assert _fmt_ms(23700) == "23.7s"


# ── _fmt_usd ──────────────────────────────────────────────────────────────────

def test_fmt_usd_returns_em_dash_for_none():
    from backend.scripts.llm_cost_report import _fmt_usd
    assert _fmt_usd(None) == "—"


def test_fmt_usd_marks_zero_with_warning_symbol():
    from backend.scripts.llm_cost_report import _fmt_usd
    assert _fmt_usd(0) == "$0 ⚠"


def test_fmt_usd_formats_sub_millidollar_with_six_decimals():
    from backend.scripts.llm_cost_report import _fmt_usd
    assert _fmt_usd(0.0005) == "$0.000500"
    assert _fmt_usd(0.0001) == "$0.000100"


def test_fmt_usd_formats_normal_values_with_four_decimals():
    from backend.scripts.llm_cost_report import _fmt_usd
    assert _fmt_usd(0.001) == "$0.0010"
    assert _fmt_usd(0.0123) == "$0.0123"
    assert _fmt_usd(1.5) == "$1.5000"


# ── _classify_pricing_state ───────────────────────────────────────────────────

def test_classify_current_gap_when_models_are_missing():
    from backend.scripts.llm_cost_report import _classify_pricing_state
    assert _classify_pricing_state(["claude-haiku-4-5-20251001"], zero_calls=10) == "current_gap"


def test_classify_current_gap_takes_priority_over_zero_calls():
    from backend.scripts.llm_cost_report import _classify_pricing_state
    # Even with zero-cost rows, a missing pricing entry is the more urgent state.
    assert _classify_pricing_state(["some-model"], zero_calls=0) == "current_gap"
    assert _classify_pricing_state(["some-model"], zero_calls=20) == "current_gap"


def test_classify_historical_zeros_when_pricing_complete_but_old_rows_remain():
    from backend.scripts.llm_cost_report import _classify_pricing_state
    assert _classify_pricing_state([], zero_calls=5) == "historical_zeros"
    assert _classify_pricing_state([], zero_calls=61) == "historical_zeros"


def test_classify_complete_when_pricing_full_and_no_zero_rows():
    from backend.scripts.llm_cost_report import _classify_pricing_state
    assert _classify_pricing_state([], zero_calls=0) == "complete"


def test_classify_multiple_missing_models_still_current_gap():
    from backend.scripts.llm_cost_report import _classify_pricing_state
    assert _classify_pricing_state(["model-a", "model-b"], zero_calls=0) == "current_gap"
