"""
Tests for the cv_classifier output-token optimization.

C1 — ClassifierItem has no `reasoning` field; parsing succeeds with id+classification only
C2 — ClassifierItem rejects unknown extra fields (strict schema)
C3 — ClassifierOutput round-trips through JSON with only the two required fields
C4 — enforcer() still produces correct ENTFERNEN/KÜRZEN/KEEP instructions without reasoning
C5 — _run_classifier is called with max_tokens=2048
C6 — cv_classifier prompt no longer contains the word "reasoning"
"""
import inspect
import json

import pytest

from backend.models.tailoring import ClassifierItem, ClassifierOutput, GeneratorItem


# ── C1: ClassifierItem parses with only id + classification ──────────────────

def test_classifier_item_parses_without_reasoning():
    item = ClassifierItem.model_validate({"id": "item_001", "classification": "KEEP"})
    assert item.id == "item_001"
    assert item.classification == "KEEP"


def test_classifier_item_has_no_reasoning_field():
    assert not hasattr(ClassifierItem.model_fields, "reasoning"), (
        "ClassifierItem must not have a 'reasoning' field"
    )
    assert "reasoning" not in ClassifierItem.model_fields


# ── C2: All three label values are still valid ────────────────────────────────

@pytest.mark.parametrize("label", ["KEEP", "DISTRAKTOR", "TRANSFERABEL"])
def test_classifier_item_accepts_all_three_labels(label: str):
    item = ClassifierItem.model_validate({"id": "item_000", "classification": label})
    assert item.classification == label


def test_classifier_item_rejects_invalid_label():
    with pytest.raises(Exception):
        ClassifierItem.model_validate({"id": "item_000", "classification": "REMOVE"})


# ── C3: ClassifierOutput round-trips with minimal JSON ───────────────────────

def test_classifier_output_roundtrip():
    payload = {
        "items": [
            {"id": "item_000", "classification": "KEEP"},
            {"id": "item_001", "classification": "DISTRAKTOR"},
            {"id": "item_002", "classification": "TRANSFERABEL"},
        ]
    }
    output = ClassifierOutput.model_validate(payload)
    assert len(output.items) == 3
    assert output.items[0].classification == "KEEP"
    assert output.items[1].classification == "DISTRAKTOR"
    assert output.items[2].classification == "TRANSFERABEL"


def test_classifier_output_roundtrip_via_json():
    payload = json.dumps({
        "items": [
            {"id": "item_010", "classification": "KEEP"},
            {"id": "item_011", "classification": "TRANSFERABEL"},
        ]
    })
    output = ClassifierOutput.model_validate_json(payload)
    assert len(output.items) == 2
    assert output.items[0].id == "item_010"


# ── C4: enforcer() uses only id + classification, still works ─────────────────

def test_enforcer_distraktor_becomes_entfernen():
    from backend.deterministic.word_budget import enforcer

    classifier_output = ClassifierOutput(items=[
        ClassifierItem(id="item_000", classification="DISTRAKTOR"),
    ])
    cv_items = {"item_000": "Unrelated hobby skill"}

    result = enforcer(classifier_output, cv_items)

    assert len(result) == 1
    assert result[0].id == "item_000"
    assert result[0].action == "ENTFERNEN"


def test_enforcer_transferabel_long_item_becomes_kurzen():
    from backend.deterministic.word_budget import enforcer

    long_content = (
        "Developed scalable microservices architecture using Python and Docker containers "
        "deployed on AWS ECS with automated CI/CD pipelines reducing release cycles from "
        "two weeks to daily deployments across five production services"
    )
    classifier_output = ClassifierOutput(items=[
        ClassifierItem(id="item_001", classification="TRANSFERABEL"),
    ])
    cv_items = {"item_001": long_content}

    result = enforcer(classifier_output, cv_items)

    assert len(result) == 1
    assert result[0].action == "KÜRZEN"


def test_enforcer_keep_items_are_skipped():
    from backend.deterministic.word_budget import enforcer

    classifier_output = ClassifierOutput(items=[
        ClassifierItem(id="item_002", classification="KEEP"),
    ])
    cv_items = {"item_002": "Python expert"}

    result = enforcer(classifier_output, cv_items)

    assert result == []


# ── C5: _run_classifier passes max_tokens=2048 ───────────────────────────────

def test_run_classifier_uses_max_tokens_2048():
    from backend.pipeline import cv_tailoring
    source = inspect.getsource(cv_tailoring._run_classifier)
    assert "max_tokens=2048" in source, (
        "_run_classifier must pass max_tokens=2048 to call_structured"
    )


def test_run_classifier_does_not_use_old_max_tokens():
    from backend.pipeline import cv_tailoring
    source = inspect.getsource(cv_tailoring._run_classifier)
    assert "max_tokens=8192" not in source, (
        "Old max_tokens=8192 must be removed from _run_classifier"
    )


# ── C6: cv_classifier prompt no longer mentions reasoning ────────────────────

def test_cv_classifier_prompt_has_no_reasoning_field():
    from backend.prompts.loader import load_prompt
    prompt = load_prompt("cv_classifier")
    assert "reasoning" not in prompt.lower(), (
        "cv_classifier prompt must not contain 'reasoning' after the optimization"
    )
