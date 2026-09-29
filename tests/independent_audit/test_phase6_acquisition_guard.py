from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import pytest

from investment_tracker.independent_audit.phase6 import opend_qfq


def test_acquisition_authorization_is_consumed_before_provider_history(monkeypatch, tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    private = tmp_path / "private"
    contract = tmp_path / "contract.json"
    attestation = tmp_path / "attestation.json"
    authorization = tmp_path / "authorization.json"
    contract.write_text("{}", encoding="utf-8")
    attestation.write_text("{}", encoding="utf-8")
    authorization.write_text('{"authorization":"synthetic"}', encoding="utf-8")

    auth = SimpleNamespace(
        authorization_id="phase6-acquire-synthetic",
        candidate_id="phase4-" + "a" * 64,
        binding_sha256="b" * 64,
        implementation_sha256="c" * 64,
    )
    monkeypatch.setattr(opend_qfq, "load_frozen_contract", lambda path: {})
    monkeypatch.setattr(
        opend_qfq,
        "load_acquisition_authorization",
        lambda *args, **kwargs: auth,
    )

    calls = 0

    def stop_after_marker():
        nonlocal calls
        calls += 1
        raise RuntimeError("SYNTHETIC_PRE_PROVIDER_STOP")

    monkeypatch.setattr(opend_qfq, "expected_sessions", stop_after_marker)

    with pytest.raises(RuntimeError, match="SYNTHETIC_PRE_PROVIDER_STOP"):
        opend_qfq.acquire_and_seal(
            repository_root=repo,
            contract_path=contract,
            attestation_path=attestation,
            authorization_path=authorization,
            private_output_dir=private,
        )

    marker = private / "phase6-acquire-synthetic.acquisition-started.json"
    assert marker.is_file()
    assert calls == 1

    with pytest.raises(
        RuntimeError,
        match="PHASE6_ACQUISITION_AUTHORIZATION_ALREADY_CONSUMED",
    ):
        opend_qfq.acquire_and_seal(
            repository_root=repo,
            contract_path=contract,
            attestation_path=attestation,
            authorization_path=authorization,
            private_output_dir=private,
        )

    assert calls == 1


def test_validated_frame_normalizes_series_sessions():
    required = pd.DatetimeIndex(
        ["2023-01-03", "2023-01-04"],
        tz="UTC",
    )
    frame = pd.DataFrame(
        {
            "time_key": ["2023-01-03 00:00:00", "2023-01-04 00:00:00"],
            "open": [100.0, 101.0],
            "high": [102.0, 103.0],
            "low": [99.0, 100.0],
            "close": [101.0, 102.0],
        }
    )

    result = opend_qfq._validated_frame(
        frame,
        symbol="SYNTH",
        required_sessions=required,
    )

    assert result.index.equals(required)
    assert list(result.columns) == ["open", "high", "low", "close"]
