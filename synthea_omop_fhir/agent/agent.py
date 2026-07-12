"""Governed clinical cohort agent (LLM-agnostic).

Claude / GPT answers clinical questions ("how many female patients with breast
cancer?") ONLY by calling a small set of governed cohort tools. It never writes
SQL and never sees raw patient rows — it selects an operation + parameters, we
validate them, and the parameterized (read-only) cohort operation runs.

This is the health-appropriate version of governed agentic analytics.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field

from ..cohort import builder
from .llm import LLMClient, create_llm_client

MAX_STEPS = 6

SYSTEM_PROMPT = """You are a clinical cohort assistant working over an OMOP CDM
of **synthetic** patients (Synthea) — no real patient data.

Answer questions ONLY by calling the provided tools. You must NOT invent numbers.
Each tool runs a governed, read-only cohort operation; you only choose the
operation and its parameters. If a question cannot be answered with the tools,
say so plainly.

Condition and measurement labels use clinical terminology (SNOMED/LOINC), e.g.
"malignant neoplasm of breast" or "carcinoma", not lay terms. If a lay term
(like "breast cancer") returns 0 patients, retry with clinical synonyms
("neoplasm", "malignant", "carcinoma") before concluding there are none.

After a tool returns, answer concisely in the SAME LANGUAGE as the user, citing
the exact figures, and remind that the data is synthetic when relevant.
"""


# The governed tools = the cohort operations. No free-form SQL is ever exposed.
TOOLS = [
    {
        "name": "total_patients",
        "description": "Total number of patients in the OMOP database.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "cohort_by_condition",
        "description": "Count of distinct patients having a condition whose label "
                       "matches a term (e.g. 'breast cancer'), broken down by gender.",
        "input_schema": {
            "type": "object",
            "properties": {"term": {"type": "string", "description": "condition term"}},
            "required": ["term"],
        },
    },
    {
        "name": "condition_prevalence",
        "description": "Most frequent conditions by distinct patient count.",
        "input_schema": {
            "type": "object",
            "properties": {"top_n": {"type": "integer", "description": "1..100"}},
        },
    },
    {
        "name": "measurement_summary",
        "description": "Summary stats (n, mean, min, max, unit) for measurements "
                       "whose label matches a term (e.g. 'HbA1c', 'Body Height').",
        "input_schema": {
            "type": "object",
            "properties": {"term": {"type": "string", "description": "measurement term"}},
            "required": ["term"],
        },
    },
]
TOOL_NAMES = {t["name"] for t in TOOLS}


def _execute(name: str, args: dict) -> dict:
    """Validate + run one governed cohort operation."""
    if name not in TOOL_NAMES:
        raise ValueError(f"Unknown tool: {name}")
    if name == "total_patients":
        return {"total_patients": builder.total_patients()}
    if name == "cohort_by_condition":
        term = str(args.get("term", "")).strip()
        if not term:
            raise ValueError("term is required")
        return builder.condition_cohort(term)
    if name == "condition_prevalence":
        return {"prevalence": builder.condition_prevalence(int(args.get("top_n", 10)))}
    if name == "measurement_summary":
        term = str(args.get("term", "")).strip()
        if not term:
            raise ValueError("term is required")
        return builder.measurement_summary(term)
    raise ValueError(f"Unhandled tool: {name}")  # pragma: no cover


@dataclass
class AgentResult:
    answer: str
    steps: list[str] = field(default_factory=list)


class ClinicalCohortAgent:
    """Governed clinical agent that works with any LLMClient (Anthropic, OpenAI, …)."""

    def __init__(self, client: LLMClient | None = None):
        self._llm = create_llm_client(client=client)

    def run(self, question: str) -> AgentResult:
        messages: list[dict] = [{"role": "user", "content": question}]
        result = AgentResult(answer="")

        for _ in range(MAX_STEPS):
            resp = self._llm.chat_with_tools(
                system=SYSTEM_PROMPT,
                messages=messages,
                tools=TOOLS,
                max_tokens=1024,
            )
            if resp.stop_reason != "tool_use":
                result.answer = resp.text
                return result

            # Re-build Anthropic-style assistant message for the conversation loop
            assistant_content: list[dict] = []
            if resp.text:
                assistant_content.append({"type": "text", "text": resp.text})
            for tc in resp.tool_calls:
                assistant_content.append({
                    "type": "tool_use",
                    "id": tc.id,
                    "name": tc.name,
                    "input": tc.arguments,
                })
            messages.append({"role": "assistant", "content": assistant_content})

            tool_results: list[dict] = []
            for tc in resp.tool_calls:
                try:
                    data = _execute(tc.name, tc.arguments)
                    content, is_error = json.dumps(data), False
                    result.steps.append(f"OK {tc.name}({tc.arguments}) -> {data}")
                except Exception as e:  # noqa: BLE001
                    content, is_error = f"Error: {e}", True
                    result.steps.append(f"ERROR {tc.name}({tc.arguments}) -> {e}")
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": tc.id,
                    "content": content,
                    "is_error": is_error,
                })
            messages.append({"role": "user", "content": tool_results})

        result.answer = "Stopped after too many steps."
        return result


def ask(question: str) -> AgentResult:
    return ClinicalCohortAgent().run(question)
