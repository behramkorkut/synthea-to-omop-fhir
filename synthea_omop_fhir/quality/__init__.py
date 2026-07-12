"""OMOP CDM data-quality checks (Pandera / DQD-like)."""

from .run import QualityReport, run

__all__ = ["QualityReport", "run"]
