from __future__ import annotations

import argparse
import ast
import json
from pathlib import Path

from investment_tracker.quant import cli


class FakeOutcome:
    stop_reason = "PHASE_3_UNIVERSE_FROZEN"

    def model_dump(self, *, mode: str):
        assert mode == "json"
        return {
            "campaign_id": "phase3-cli-test",
            "window_start": "2014-01-01",
            "window_end": "2022-12-31",
            "dq_snapshot": {
                "kind": "dq_snapshot",
                "sha256": "a" * 64,
                "path": "phase3/snapshot.json",
            },
            "dq_report": {
                "kind": "dq_report",
                "sha256": "b" * 64,
                "path": "phase3/report.md",
            },
            "universe_manifest": {
                "kind": "universe_manifest",
                "sha256": "c" * 64,
                "path": "phase3/manifest.json",
            },
            "stop_reason": self.stop_reason,
        }


def phase3_options() -> set[str]:
    root = cli.parser()
    subparsers = next(
        action
        for action in root._actions
        if isinstance(action, argparse._SubParsersAction)
    )
    phase3 = subparsers.choices["phase3-universe"]
    return {
        option
        for action in phase3._actions
        for option in action.option_strings
    }


def test_phase3_cli_uses_fixed_campaign_and_prints_artifact_digests(
    monkeypatch, capsys, tmp_path: Path
) -> None:
    observed: dict[str, object] = {}

    class FakeSource:
        def __init__(self, *, host: str, port: int) -> None:
            observed["source"] = (host, port)

    class FakeStore:
        def __init__(self, evidence_root: Path, results_root: Path) -> None:
            observed["store"] = (evidence_root, results_root)

    def fake_campaign(source, store, *, campaign_id: str):
        observed["campaign"] = (source, store, campaign_id)
        return FakeOutcome()

    monkeypatch.setattr(
        "investment_tracker.quant.data.moomoo_client.MoomooHistoricalDataSource",
        FakeSource,
    )
    monkeypatch.setattr(
        "investment_tracker.quant.universe.artifacts.Phase3ArtifactStore",
        FakeStore,
    )
    monkeypatch.setattr(
        "investment_tracker.quant.universe.campaign.run_phase3_campaign",
        fake_campaign,
    )

    exit_code = cli.main(
        [
            "phase3-universe",
            "--host",
            "127.0.0.1",
            "--port",
            "11111",
            "--evidence-root",
            str(tmp_path / "cache"),
            "--results-root",
            str(tmp_path / "results"),
            "--campaign-id",
            "phase3-cli-test",
        ]
    )
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert observed["source"] == ("127.0.0.1", 11111)
    assert observed["store"] == (tmp_path / "cache", tmp_path / "results")
    assert observed["campaign"][2] == "phase3-cli-test"
    assert payload["status"] == "PHASE_3_UNIVERSE_FROZEN"
    assert payload["dq_snapshot"]["sha256"] == "a" * 64
    assert payload["dq_report"]["sha256"] == "b" * 64
    assert payload["universe_manifest"]["sha256"] == "c" * 64


def test_phase3_cli_exposes_no_symbol_window_refresh_or_strategy_override() -> None:
    options = phase3_options()
    assert {"--host", "--port", "--evidence-root", "--results-root", "--campaign-id"} <= options
    assert options.isdisjoint(
        {"--start", "--end", "--symbol", "--symbols", "--refresh", "--strategy"}
    )


def test_quant_source_has_no_forbidden_trading_api_names() -> None:
    forbidden = {
        "OpenTradeContext",
        "OpenSecTradeContext",
        "OpenFutureTradeContext",
        "OpenCryptoTradeContext",
        "place_order",
        "modify_order",
        "cancel_order",
        "unlock_trade",
        "get_acc_list",
        "position_list_query",
        "accinfo_query",
    }
    found: list[tuple[str, str]] = []
    for path in Path("src/investment_tracker/quant").rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            name = None
            if isinstance(node, ast.Name):
                name = node.id
            elif isinstance(node, ast.Attribute):
                name = node.attr
            if name in forbidden:
                found.append((str(path), name))
    assert found == []
