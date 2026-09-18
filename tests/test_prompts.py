"""Contract tests for the centralized, grounded prompt registry."""

import re

import pytest

from seo_agent.audit.prompts import PROMPT_REGISTRY, PROMPT_VERSION

pytestmark = pytest.mark.unit


def test_prompt_registry_contains_every_llm_task() -> None:
    assert set(PROMPT_REGISTRY) == {
        "understand_site",
        "select_pages",
        "analyze_findings",
        "evaluate_findings",
        "report",
    }
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}-v\d+", PROMPT_VERSION)


def test_every_prompt_pair_enforces_grounding_and_prompt_injection_boundaries() -> None:
    for pair in PROMPT_REGISTRY.values():
        combined = f"{pair.system_prompt}\n{pair.user_prompt}".lower()

        assert "untrusted data" in combined
        assert re.search(r"never\s+instructions", combined)
        for forbidden_invention in (
            "facts",
            "urls",
            "citations",
            "prices",
            "features",
            "relationships",
        ):
            assert forbidden_invention in combined
        assert "observed facts" in combined
        assert "model interpretations" in combined
        assert "unvalidated hypotheses" in combined
        assert "missing information is not proof of absence" in combined


def test_prompt_templates_accept_their_documented_runtime_values() -> None:
    PROMPT_REGISTRY["understand_site"].user_prompt.format(
        homepage_evidence="homepage evidence",
    )
    PROMPT_REGISTRY["select_pages"].user_prompt.format(
        site_context="context",
        candidates="candidates",
        additional_page_limit=4,
    )
    PROMPT_REGISTRY["analyze_findings"].user_prompt.format(
        site_context="context",
        findings="findings",
        performance="performance",
    )
    PROMPT_REGISTRY["evaluate_findings"].user_prompt.format(
        findings="findings",
        remaining_investigation_rounds=1,
        remaining_investigation_fetches=2,
    )
    PROMPT_REGISTRY["report"].user_prompt.format(
        site_context="context",
        scope="scope",
        findings="findings",
        performance="performance",
        collection_warnings="warnings",
    )
