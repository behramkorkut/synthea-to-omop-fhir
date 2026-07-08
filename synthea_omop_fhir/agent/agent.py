"""Governed clinical cohort agent.

Claude answers clinical questions ("how many female patients with breast
cancer?") ONLY by calling a small set of governed cohort tools. It never writes
SQL and never sees raw patient rows — it selects an operation + parameters, we
validate them, and the parameterized (read-only) cohort operation runs.

This is the health-appropriate version of governed agentic analytics.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field

import anthropic

from ..cohort import builder
from ..config import settings

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
    def __init__(self, client: anthropic.Anthropic | None = None):
        if client is not None:
            self.client = client
        else:
            if not settings.anthropic_api_key:
                raise RuntimeError("ANTHROPIC_API_KEY is not set. Add it to your .env.")
            self.client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

    def run(self, question: str) -> AgentResult:
        messages: list[dict] = [{"role": "user", "content": question}]
        result = AgentResult(answer="")

        for _ in range(MAX_STEPS):
            resp = self.client.messages.create(
                model=settings.anthropic_model,
                max_tokens=1024,
                system=SYSTEM_PROMPT,
                tools=TOOLS,
                messages=messages,
            )
            if resp.stop_reason != "tool_use":
                result.answer = "".join(
                    b.text for b in resp.content if b.type == "text"
                ).strip()
                return result

            messages.append({"role": "assistant", "content": resp.content})
            tool_results = []
            for block in resp.content:
                if block.type != "tool_use":
                    continue
                try:
                    data = _execute(block.name, block.input or {})
                    content, is_error = json.dumps(data), False
                    result.steps.append(f"OK {block.name}({block.input}) -> {data}")
                except Exception as e:  # noqa: BLE001
                    content, is_error = f"Error: {e}", True
                    result.steps.append(f"ERROR {block.name}({block.input}) -> {e}")
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": content,
                    "is_error": is_error,
                })
            messages.append({"role": "user", "content": tool_results})

        result.answer = "Stopped after too many steps."
        return result


def ask(question: str) -> AgentResult:
    return ClinicalCohortAgent().run(question)
