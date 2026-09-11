"""Derived, reproducible views over immutable research artifacts."""

from .generate_report import load_experiments, render_report, write_leaderboard, write_report

__all__ = ["load_experiments", "render_report", "write_leaderboard", "write_report"]
