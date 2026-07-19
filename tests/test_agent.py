"""Governed clinical agent tests: tool allow-list (unit) + loop (integration)."""

from types import SimpleNamespace as NS

import pytest

from synthea_omop_fhir.agent.agent import TOOL_NAMES, ClinicalCohortAgent, _execute
from synthea_omop_fhir.config import settings

needs_warehouse = pytest.mark.skipif(
    not settings.warehouse_db_abs.exists(),
    reason="Build the warehouse first (make warehouse).",
)


def test_tool_allow_list():
    assert {
        "total_patients",
        "cohort_by_condition",
        "condition_prevalence",
        "measurement_summary",
    } <= TOOL_NAMES


def test_execute_rejects_unknown_tool():
    with pytest.raises(ValueError):
        _execute("drop_table", {})


def test_execute_requires_term():
    with pytest.raises(ValueError):
        _execute("cohort_by_condition", {"term": ""})


@needs_warehouse
def test_execute_cohort_runs():
    r = _execute("cohort_by_condition", {"term": "diabetes"})
    assert r["patient_count"] > 0


class _FakeMessages:
    def __init__(self):
        self.n = 0

    def create(self, **_):
        self.n += 1
        if self.n == 1:
            tu = NS(
                type="tool_use",
                name="condition_prevalence",
                id="t1",
                input={"top_n": 3},
            )
            return NS(stop_reason="tool_use", content=[tu])
        return NS(
            stop_reason="end_turn",
            content=[NS(type="text", text="Top conditions listed.")],
        )


class _FakeClient:
    def __init__(self):
        self.messages = _FakeMessages()


@needs_warehouse
def test_agent_loop_with_fake_client():
    agent = ClinicalCohortAgent(client=_FakeClient())
    res = agent.run("What are the most frequent conditions?")
    assert res.answer == "Top conditions listed."
    assert any("condition_prevalence" in s for s in res.steps)
