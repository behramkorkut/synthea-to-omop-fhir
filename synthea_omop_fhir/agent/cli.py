"""Ask the governed clinical cohort agent from the terminal.

Usage:
    uv run python -m synthea_omop_fhir.agent.cli "Combien de patientes ont un cancer du sein ?"
"""

from __future__ import annotations

import sys

from .agent import ClinicalCohortAgent


def main() -> None:
    agent = ClinicalCohortAgent()  # checks API key
    question = " ".join(sys.argv[1:]).strip()
    if not question:
        print('Usage: ... agent.cli "your clinical question"')
        raise SystemExit(2)
    res = agent.run(question)
    print("\n" + res.answer + "\n")
    for s in res.steps:
        print("  ·", s)


if __name__ == "__main__":
    main()
