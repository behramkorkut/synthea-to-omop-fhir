"""Tests du point d'entrée CLI de l'agent (agent/cli.py) — agent entièrement doublé.

Aucune clé API ni appel LLM : la classe ``ClinicalCohortAgent`` est remplacée
par un double contrôlable. On vérifie le contrat du point d'entrée `make ask` :
usage (exit 2) sans question, réponse + étapes imprimées avec une question.
"""

from __future__ import annotations

import sys

import pytest

from synthea_omop_fhir.agent import cli
from synthea_omop_fhir.agent.agent import AgentResult


class _FakeAgent:
    """Double de ClinicalCohortAgent : pas de clé API, réponse fixe."""

    def __init__(self) -> None:
        self.questions: list[str] = []

    def run(self, question: str) -> AgentResult:
        self.questions.append(question)
        return AgentResult(
            answer="42 patientes",
            steps=["OK count_patients({'gender': 'female'}) -> 42"],
        )


def test_main_without_question_prints_usage_and_exits_2(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(cli, "ClinicalCohortAgent", _FakeAgent)
    monkeypatch.setattr(sys, "argv", ["agent.cli"])
    with pytest.raises(SystemExit) as exc:
        cli.main()
    assert exc.value.code == 2
    assert "Usage" in capsys.readouterr().out


def test_main_runs_agent_and_prints_answer_and_steps(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(cli, "ClinicalCohortAgent", _FakeAgent)
    monkeypatch.setattr(sys, "argv", ["agent.cli", "Combien", "de", "patientes", "?"])
    cli.main()
    out = capsys.readouterr().out
    assert "42 patientes" in out
    assert "OK count_patients" in out


def test_main_joins_multiword_question(monkeypatch: pytest.MonkeyPatch) -> None:
    agent = _FakeAgent()
    monkeypatch.setattr(cli, "ClinicalCohortAgent", lambda: agent)
    monkeypatch.setattr(sys, "argv", ["agent.cli", "cancer", "du", "sein"])
    cli.main()
    assert agent.questions == ["cancer du sein"]
