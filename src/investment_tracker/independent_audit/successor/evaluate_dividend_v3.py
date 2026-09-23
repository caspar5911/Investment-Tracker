from __future__ import annotations

from collections import defaultdict
from hashlib import sha256
from io import BytesIO
import json
import math
import os
from pathlib import Path, PurePosixPath
from typing import Any
import zipfile

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
import pandas as pd

from investment_tracker.quant.generation2.accounting import (
    DecisionTarget,
    DividendEvent,
    SplitEvent,
    replay_decision_targets,
)
from investment_tracker.quant.generation2.grid import GridCandidate
from investment_tracker.quant.generation2.performance import summarize
from investment_tracker.quant.generation2.strategy import build_targets
from investment_tracker.quant.generation2.survivor_identity import verify_survivor_identity
from investment_tracker.quant.successor.corporate_actions_v2 import (
    normalize_split_events,
)
from investment_tracker.quant.successor.dividend_reconciliation_v3 import (
    reconcile_structured_dividend_amounts,
)

from .acquisition import MAGIC, _canonical_bytes, expected_sessions
from .phase6_contract import verify_phase6_contract
from .release import _write_exclusive_verified, load_receipt, load_release

RESULT_SCHEMA = "SUCCESSOR-PHASE6-FINAL-HOLDOUT-EVALUATION-v2"


def _sha_bytes(payload: bytes) -> str:
    return sha256(payload).hexdigest()


def _sha_file(path: Path) -> str:
    return _sha_bytes(Path(path).read_bytes())


def _write_marker(path: Path, payload: dict[str, Any], *, exclusive: bool) -> None:
    data = _canonical_bytes(payload)
    path.parent.mkdir(parents=True, exist_ok=True)
    if exclusive:
        try:
            with path.open("xb") as handle:
                handle.write(data)
                handle.flush()
                os.fsync(handle.fileno())
        except FileExistsError as exc:
            raise RuntimeError("SUCCESSOR_PHASE6_RELEASE_ALREADY_CONSUMED") from exc
    else:
        partial = path.with_name(path.name + ".partial")
        with partial.open("wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(partial, path)
    if path.read_bytes() != data:
        raise OSError("SUCCESSOR_PHASE6_CONSUMPTION_MARKER_READBACK_FAILED")


def _decrypt(encrypted: bytes, key: bytes, contract_sha256: str) -> bytes:
    if not encrypted.startswith(MAGIC) or len(encrypted) <= len(MAGIC) + 12:
        raise ValueError("SUCCESSOR_PHASE6_BUNDLE_FORMAT_INVALID")
    offset = len(MAGIC)
    nonce = encrypted[offset : offset + 12]
    ciphertext = encrypted[offset + 12 :]
    try:
        return AESGCM(key).decrypt(nonce, ciphertext, contract_sha256.encode("ascii"))
    except Exception as exc:
        raise ValueError("SUCCESSOR_PHASE6_BUNDLE_DECRYPTION_FAILED") from exc


def _safe_member(name: str) -> bool:
    path = PurePosixPath(name)
    return (
        bool(name)
        and "\\" not in name
        and not name.startswith("/")
        and all(part not in {"", ".", ".."} for part in path.parts)
    )


def _open_bundle(
    plaintext: bytes, receipt: dict[str, Any]
) -> tuple[dict[str, Any], dict[str, bytes]]:
    try:
        with zipfile.ZipFile(BytesIO(plaintext), "r") as archive:
            names = archive.namelist()
            if len(names) != len(set(names)) or any(not _safe_member(name) for name in names):
                raise ValueError("SUCCESSOR_PHASE6_BUNDLE_MEMBER_INVALID")
            if "manifest.json" not in names:
                raise ValueError("SUCCESSOR_PHASE6_BUNDLE_MANIFEST_MISSING")
            manifest = json.loads(archive.read("manifest.json"))
            entries = {
                name: archive.read(name)
                for name in names
                if name != "manifest.json"
            }
    except (zipfile.BadZipFile, json.JSONDecodeError) as exc:
        raise ValueError("SUCCESSOR_PHASE6_BUNDLE_INVALID") from exc
    if (
        not isinstance(manifest, dict)
        or _sha_bytes(_canonical_bytes(manifest)) != receipt["bundle_manifest_sha256"]
    ):
        raise ValueError("SUCCESSOR_PHASE6_BUNDLE_MANIFEST_HASH_MISMATCH")
    listed = manifest.get("files")
    if not isinstance(listed, list):
        raise ValueError("SUCCESSOR_PHASE6_BUNDLE_FILE_MANIFEST_INVALID")
    expected = {
        item.get("path"): (item.get("sha256"), item.get("bytes"))
        for item in listed
        if isinstance(item, dict)
    }
    if set(expected) != set(entries) or len(expected) != len(listed):
        raise ValueError("SUCCESSOR_PHASE6_BUNDLE_FILE_SET_MISMATCH")
    for name, payload in entries.items():
        if expected[name] != (_sha_bytes(payload), len(payload)):
            raise ValueError(f"SUCCESSOR_PHASE6_BUNDLE_FILE_HASH_MISMATCH:{name}")
    return manifest, entries


def _validate_manifest(
    manifest: dict[str, Any],
    contract: dict[str, Any],
    warmup: pd.DatetimeIndex,
    scored: pd.DatetimeIndex,
) -> None:
    locked = tuple(contract["final_holdout"]["locked_symbols"])
    benchmark = contract["final_holdout"]["benchmark_reference_symbol"]
    expected = {
        "schema_version": "SUCCESSOR-PHASE6-HOLDOUT-ACQUISITION-v1",
        "authority": "INDEPENDENT_AUDIT",
        "successor_formal_name": contract["successor_formal_name"],
        "phase6_contract_sha256": _sha_file_from_contract(contract),
        "candidate_id": contract["strategy"]["candidate_id"],
        "binding_sha256": contract["strategy"]["binding_sha256"],
        "implementation_sha256": contract["strategy"]["implementation_sha256"],
        "successor_normalizer_sha256": contract["methodology"]["successor_normalizer_sha256"],
        "successor_evaluator_sha256": contract["methodology"]["successor_evaluator_sha256"],
        "locked_symbols": list(locked),
        "benchmark_reference_symbol": benchmark,
        "holdout_start": contract["final_holdout"]["calendar_start"],
        "holdout_end": contract["final_holdout"]["calendar_end"],
        "warmup_session_count": len(warmup),
        "scored_session_count": len(scored),
        "final_holdout_accessed": True,
        "protected_symbols_accessed": list(locked),
        "performance_computed": False,
        "performance_inspected": False,
        "candidate_search_executed": False,
        "candidate_parameters_changed": False,
        "phase7_started": False,
        "live_trading_capability": False,
    }
    if any(manifest.get(field) != value for field, value in expected.items()):
        raise ValueError("SUCCESSOR_PHASE6_BUNDLE_GOVERNANCE_MISMATCH")

    data_symbols = (*locked, benchmark)
    expected_paths = {
        f"{kind}/{symbol}.{extension}"
        for symbol in data_symbols
        for kind, extension in (
            ("bars/qfq", "csv"),
            ("bars/unadjusted", "csv"),
            ("corporate_actions/rehab", "csv"),
            ("corporate_actions/dividends", "json"),
            ("corporate_actions/splits", "json"),
        )
    }
    listed_paths = {item["path"] for item in manifest["files"]}
    if listed_paths != expected_paths:
        raise ValueError("SUCCESSOR_PHASE6_BUNDLE_REQUIRED_FILES_MISMATCH")


def _sha_file_from_contract(contract: dict[str, Any]) -> str:
    value = contract.get("_file_sha256")
    if not isinstance(value, str):
        raise ValueError("SUCCESSOR_PHASE6_CONTRACT_FILE_HASH_MISSING")
    return value


def _bar_frame(
    payload: bytes, required_sessions: pd.DatetimeIndex, identity: str
) -> pd.DataFrame:
    try:
        frame = pd.read_csv(BytesIO(payload))
    except Exception as exc:
        raise ValueError(f"SUCCESSOR_PHASE6_BAR_CSV_INVALID:{identity}") from exc
    if not {"session", "open", "high", "low", "close"}.issubset(frame.columns):
        raise ValueError(f"SUCCESSOR_PHASE6_BAR_SCHEMA_INVALID:{identity}")
    sessions = pd.to_datetime(frame["session"], errors="raise", utc=True).dt.normalize()
    if sessions.duplicated().any():
        raise ValueError(f"SUCCESSOR_PHASE6_BAR_SESSION_DUPLICATE:{identity}")
    values = frame.set_index(pd.DatetimeIndex(sessions))[
        ["open", "high", "low", "close"]
    ].apply(pd.to_numeric, errors="raise")
    matrix = values.to_numpy(dtype=float)
    if (
        not values.index.equals(required_sessions)
        or not all(
            math.isfinite(float(value)) and float(value) > 0.0
            for value in matrix.flat
        )
        or (values["low"] > values[["open", "close"]].min(axis=1)).any()
        or (values["high"] < values[["open", "close"]].max(axis=1)).any()
        or (values["low"] > values["high"]).any()
    ):
        raise ValueError(f"SUCCESSOR_PHASE6_BAR_VALUES_INVALID:{identity}")
    return values


def _date(value: object, identity: str) -> pd.Timestamp:
    if value is None or str(value).strip() in {"", "0", "nan", "None"}:
        raise ValueError(f"SUCCESSOR_PHASE6_CORPORATE_ACTION_DATE_MISSING:{identity}")
    try:
        text = str(value).strip()
        if text.isdigit() and len(text) >= 9:
            timestamp = pd.Timestamp(
                pd.to_datetime(int(text), unit="s", errors="raise", utc=True)
            )
        else:
            timestamp = pd.Timestamp(pd.to_datetime(text, errors="raise", utc=True))
    except Exception as exc:
        raise ValueError(
            f"SUCCESSOR_PHASE6_CORPORATE_ACTION_DATE_INVALID:{identity}"
        ) from exc
    return timestamp.normalize()


def _number(value: object, identity: str) -> float:
    if value is None or str(value).strip() in {"", "nan", "None"}:
        return 0.0
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            f"SUCCESSOR_PHASE6_CORPORATE_ACTION_NUMBER_INVALID:{identity}"
        ) from exc
    if not math.isfinite(result):
        raise ValueError(
            f"SUCCESSOR_PHASE6_CORPORATE_ACTION_NUMBER_INVALID:{identity}"
        )
    return result


def _corporate_actions(
    entries: dict[str, bytes],
    symbol: str,
    scored: pd.DatetimeIndex,
) -> tuple[list[SplitEvent], list[DividendEvent], dict[str, Any]]:
    try:
        rehab = pd.read_csv(BytesIO(entries[f"corporate_actions/rehab/{symbol}.csv"]))
        dividend_payload = json.loads(
            entries[f"corporate_actions/dividends/{symbol}.json"]
        )
        split_payload = json.loads(entries[f"corporate_actions/splits/{symbol}.json"])
    except Exception as exc:
        raise ValueError(
            f"SUCCESSOR_PHASE6_CORPORATE_ACTION_SOURCE_INVALID:{symbol}"
        ) from exc

    dividend_rows = (
        dividend_payload.get("dividend_list")
        if isinstance(dividend_payload, dict)
        else None
    )
    split_rows = (
        split_payload.get("split_list")
        if isinstance(split_payload, dict)
        else None
    )
    if not isinstance(dividend_rows, list) or not isinstance(split_rows, list):
        raise ValueError(
            f"SUCCESSOR_PHASE6_CORPORATE_ACTION_SOURCE_INVALID:{symbol}"
        )

    rehab_rows = [
        {
            str(key): (None if pd.isna(value) else value)
            for key, value in row.items()
        }
        for row in rehab.to_dict(orient="records")
    ]
    normalized_splits = normalize_split_events(
        symbol=symbol,
        rehab_rows=rehab_rows,
        endpoint_rows=split_rows,
        evaluation_start=scored[0].date(),
        evaluation_end=scored[-1].date(),
        scored_sessions=[session.date() for session in scored],
    )
    splits: list[SplitEvent] = []
    normalized_hashes: list[str] = []
    for item in normalized_splits.events:
        normalized = {
            "symbol": item.symbol,
            "event_type": "SPLIT",
            "effective_date": item.effective_date.isoformat(),
            "unit_multiplier": item.unit_multiplier,
            "rehab_adjustment_ratio": item.rehab_adjustment_ratio,
            "endpoint_rate": item.endpoint_rate,
            "rehab_record_sha256": item.rehab_record_sha256,
            "endpoint_record_sha256": item.endpoint_record_sha256,
        }
        identity = _sha_bytes(_canonical_bytes(normalized))
        splits.append(
            SplitEvent(
                symbol,
                pd.Timestamp(item.effective_date, tz="UTC"),
                item.unit_multiplier,
                identity,
            )
        )
        normalized_hashes.append(identity)

    first, last = scored[0], scored[-1]
    scored_set = set(scored)
    dividends_by_ex: dict[pd.Timestamp, list[dict[str, Any]]] = defaultdict(list)
    for row in dividend_rows:
        if not isinstance(row, dict):
            raise ValueError(
                f"SUCCESSOR_PHASE6_CORPORATE_ACTION_SOURCE_INVALID:{symbol}"
            )
        ex_date = _date(row.get("ex_date"), f"{symbol}:DIVIDEND_EX_DATE")
        if first <= ex_date <= last:
            if ex_date not in scored_set:
                raise ValueError(
                    f"SUCCESSOR_PHASE6_CORPORATE_ACTION_SESSION_INVALID:{symbol}:{ex_date.date()}"
                )
            dividends_by_ex[ex_date].append(row)

    dividends: list[DividendEvent] = []
    seen_rehab_dates: set[pd.Timestamp] = set()
    if "ex_div_date" not in rehab.columns:
        raise ValueError(f"SUCCESSOR_PHASE6_REHAB_SCHEMA_INVALID:{symbol}")

    for row_index, row in rehab.iterrows():
        ex_date = _date(row.get("ex_div_date"), f"{symbol}:REHAB:{row_index}")
        if not first <= ex_date <= last:
            continue
        if ex_date not in scored_set:
            raise ValueError(
                f"SUCCESSOR_PHASE6_CORPORATE_ACTION_SESSION_INVALID:{symbol}:{ex_date.date()}"
            )
        if ex_date in seen_rehab_dates:
            raise ValueError(
                f"SUCCESSOR_PHASE6_DUPLICATE_REHAB_DATE:{symbol}:{ex_date.date()}"
            )
        seen_rehab_dates.add(ex_date)
        row_dict = {
            str(key): (None if pd.isna(value) else value)
            for key, value in row.items()
        }
        row_hash = _sha_bytes(_canonical_bytes(row_dict))
        for unsupported in (
            "per_share_div_ratio",
            "per_share_trans_ratio",
            "allotment_ratio",
            "stk_spo_ratio",
            "spin_off_ratio",
        ):
            if abs(_number(row.get(unsupported), f"{symbol}:{unsupported}")) > 1e-12:
                raise ValueError(
                    f"SUCCESSOR_PHASE6_UNSUPPORTED_CORPORATE_ACTION:{symbol}:{unsupported}"
                )

        components = (
            (
                "ORDINARY_CASH",
                _number(row.get("per_cash_div"), f"{symbol}:per_cash_div"),
            ),
            (
                "SPECIAL_CASH",
                _number(row.get("special_dividend"), f"{symbol}:special_dividend"),
            ),
        )
        cash_components = [
            (name, amount) for name, amount in components if amount > 0.0
        ]
        endpoint = dividends_by_ex.pop(ex_date, [])
        if cash_components or endpoint:
            if not cash_components or not endpoint:
                raise ValueError(
                    f"SUCCESSOR_PHASE6_DIVIDEND_SOURCE_RECONCILIATION_FAILED:{symbol}:{ex_date.date()}"
                )
            identities = [
                _sha_bytes(_canonical_bytes(item))
                for item in endpoint
                if isinstance(item, dict)
            ]
            if len(identities) != len(endpoint) or len(identities) != len(set(identities)):
                raise ValueError(
                    f"SUCCESSOR_PHASE6_DUPLICATE_PROVIDER_EVENT:{symbol}:DIVIDEND"
                )
            pay_dates = {
                _date(
                    item.get("dividend_payable_date"),
                    f"{symbol}:DIVIDEND_PAY_DATE",
                )
                for item in endpoint
            }
            if len(pay_dates) != 1:
                raise ValueError(
                    f"SUCCESSOR_PHASE6_DIVIDEND_PAY_DATE_AMBIGUOUS:{symbol}:{ex_date.date()}"
                )
            pay_date = next(iter(pay_dates))
            if pay_date < ex_date:
                raise ValueError(
                    f"SUCCESSOR_PHASE6_DIVIDEND_PAY_DATE_INVALID:{symbol}:{ex_date.date()}"
                )
            reconcile_structured_dividend_amounts(
                endpoint,
                rehab_ordinary_amount=next(
                    (
                        amount
                        for component, amount in cash_components
                        if component == "ORDINARY_CASH"
                    ),
                    0.0,
                ),
                rehab_special_amount=next(
                    (
                        amount
                        for component, amount in cash_components
                        if component == "SPECIAL_CASH"
                    ),
                    0.0,
                ),
            )
            endpoint_hashes = sorted(identities)
            for component, amount in cash_components:
                normalized = {
                    "symbol": symbol,
                    "event_type": component,
                    "ex_date": ex_date.date().isoformat(),
                    "pay_date": pay_date.date().isoformat(),
                    "amount_per_unit": amount,
                    "rehab_record_sha256": row_hash,
                    "dividend_record_sha256": endpoint_hashes,
                }
                identity = _sha_bytes(_canonical_bytes(normalized))
                dividends.append(
                    DividendEvent(
                        symbol, ex_date, pay_date, amount, identity
                    )
                )
                normalized_hashes.append(identity)

    if dividends_by_ex:
        event_date = min(dividends_by_ex)
        raise ValueError(
            f"SUCCESSOR_PHASE6_DIVIDEND_SOURCE_RECONCILIATION_FAILED:{symbol}:{event_date.date()}"
        )

    return splits, dividends, {
        "symbol": symbol,
        "split_count": len(splits),
        "dividend_component_count": len(dividends),
        "normalized_event_sha256": sorted(normalized_hashes),
        "ignored_dated_split_endpoint_outside_window": normalized_splits.ignored_dated_endpoint_outside_window,
        "ignored_undated_split_endpoint_records": normalized_splits.ignored_undated_endpoint_records,
        "ignored_rehab_outside_window": normalized_splits.ignored_rehab_outside_window,
        "rehab_source_sha256": _sha_bytes(
            entries[f"corporate_actions/rehab/{symbol}.csv"]
        ),
        "dividend_source_sha256": _sha_bytes(
            entries[f"corporate_actions/dividends/{symbol}.json"]
        ),
        "split_source_sha256": _sha_bytes(
            entries[f"corporate_actions/splits/{symbol}.json"]
        ),
    }


def _metric(metric: Any) -> dict[str, Any]:
    return metric.model_dump(mode="json")


def _summary(replay: Any) -> dict[str, Any]:
    value = summarize(replay)
    return {
        "total_return": _metric(value.total_return),
        "cagr": _metric(value.cagr),
        "sharpe": _metric(value.sharpe),
        "sortino": _metric(value.sortino),
        "annualized_one_way_turnover": _metric(value.annualized_one_way_turnover),
        "rolling_12m_positive_fraction": _metric(
            value.rolling_12m_positive_fraction
        ),
        "max_drawdown": _metric(value.max_drawdown),
        "calmar": _metric(value.calmar),
        "all_session_exposure_invariant": value.exposure_invariant_passes,
        "session_count": value.session_count,
    }


def _require_primary_metrics(metrics: dict[str, Any]) -> None:
    required = (
        "total_return",
        "cagr",
        "sharpe",
        "sortino",
        "annualized_one_way_turnover",
        "rolling_12m_positive_fraction",
        "max_drawdown",
        "calmar",
    )
    missing = [
        name for name in required if metrics[name]["status"] != "AVAILABLE"
    ]
    if missing or metrics["all_session_exposure_invariant"] is not True:
        raise ValueError(
            "SUCCESSOR_PHASE6_REQUIRED_METRIC_UNKNOWN:"
            + ",".join(missing or ["all_session_exposure_invariant"])
        )


def _verify_executing_implementation(
    contract: dict[str, Any], repository_root: Path
) -> None:
    repository = Path(repository_root).resolve()
    report = verify_survivor_identity(
        repository / "data" / "governance" / "generation2-campaign",
        repository,
    )
    strategy = contract["strategy"]
    if (
        report["candidate_id"] != strategy["candidate_id"]
        or report["binding_sha256"] != strategy["binding_sha256"]
        or report["implementation_sha256"] != strategy["implementation_sha256"]
    ):
        raise ValueError("SUCCESSOR_PHASE6_EXECUTING_SURVIVOR_IDENTITY_MISMATCH")
    normalizer = (
        repository
        / "src"
        / "investment_tracker"
        / "quant"
        / "successor"
        / "corporate_actions_v2.py"
    )
    if _sha_file(normalizer) != contract["methodology"]["successor_normalizer_sha256"]:
        raise ValueError("SUCCESSOR_PHASE6_NORMALIZER_SOURCE_DRIFT")
    evaluator = Path(__file__).resolve()
    if _sha_file(evaluator) != contract["methodology"]["successor_evaluator_sha256"]:
        raise ValueError("SUCCESSOR_PHASE6_EVALUATOR_SOURCE_DRIFT")


def _evaluate_plaintext(
    plaintext: bytes,
    *,
    receipt: dict[str, Any],
    contract: dict[str, Any],
) -> dict[str, Any]:
    if _sha_bytes(plaintext) != receipt["plaintext_bundle_sha256"]:
        raise ValueError("SUCCESSOR_PHASE6_PLAINTEXT_HASH_MISMATCH")
    manifest, entries = _open_bundle(plaintext, receipt)
    warmup, scored = expected_sessions(contract)
    required = warmup.append(scored)
    _validate_manifest(manifest, contract, warmup, scored)

    locked = tuple(contract["final_holdout"]["locked_symbols"])
    benchmark_symbol = contract["final_holdout"]["benchmark_reference_symbol"]
    data_symbols = (*locked, benchmark_symbol)

    qfq = {
        symbol: _bar_frame(
            entries[f"bars/qfq/{symbol}.csv"], required, f"{symbol}:QFQ"
        )
        for symbol in locked
    }
    unadjusted = {
        symbol: _bar_frame(
            entries[f"bars/unadjusted/{symbol}.csv"], required, f"{symbol}:NONE"
        )
        for symbol in locked
    }
    benchmark_bars = _bar_frame(
        entries[f"bars/unadjusted/{benchmark_symbol}.csv"],
        required,
        f"{benchmark_symbol}:NONE",
    )

    all_splits: list[SplitEvent] = []
    all_dividends: list[DividendEvent] = []
    action_manifest: list[dict[str, Any]] = []
    for symbol in data_symbols:
        splits, dividends, evidence = _corporate_actions(entries, symbol, scored)
        all_splits.extend(splits)
        all_dividends.extend(dividends)
        action_manifest.append(evidence)

    strategy = contract["strategy"]
    candidate = GridCandidate(
        candidate_id=strategy["candidate_id"],
        family=strategy["family"],
        lookback=strategy["lookback"],
        skip=strategy["skip"],
        top_k=strategy["top_k"],
        rebalance=strategy["rebalance"],
        trend_ma=None,
        vol_lookback=None,
        horizon_set=None,
    )
    targets = build_targets(
        candidate,
        qfq,
        due_from=scored[0],
        due_until=scored[-1],
        align_start=scored[0],
    )
    friction_values = tuple(contract["friction"]["fixed_friction_cases_bps"])
    if (
        friction_values != (0, 3, 10, 25, 50)
        or contract["friction"]["primary_friction_bps"] != 3
    ):
        raise ValueError("SUCCESSOR_PHASE6_FRICTION_CONTRACT_MISMATCH")

    cases: dict[str, Any] = {}
    for bps in friction_values:
        replay = replay_decision_targets(
            unadjusted,
            targets,
            splits=[item for item in all_splits if item.symbol in locked],
            dividends=[item for item in all_dividends if item.symbol in locked],
            friction_bps=bps,
            initial_cash=contract["friction"]["initial_cash"],
            symbols=locked,
        )
        cases[str(bps)] = {
            "friction_bps": bps,
            "metrics": _summary(replay),
            "fill_count": len(replay.fills),
            "target_count": len(targets),
        }
    primary = cases["3"]["metrics"]
    _require_primary_metrics(primary)

    benchmark_target = DecisionTarget(
        "SUCCESSOR-PHASE6-BENCHMARK",
        warmup[-1],
        scored[0],
        {benchmark_symbol: 1.0},
    )
    benchmark = replay_decision_targets(
        {benchmark_symbol: benchmark_bars},
        [benchmark_target],
        splits=[
            item for item in all_splits if item.symbol == benchmark_symbol
        ],
        dividends=[
            item for item in all_dividends if item.symbol == benchmark_symbol
        ],
        friction_bps=3,
        initial_cash=contract["friction"]["initial_cash"],
        symbols=(benchmark_symbol,),
    )

    return {
        "schema_version": RESULT_SCHEMA,
        "authority": "COORDINATOR_UNDER_INDEPENDENT_AUDIT_RELEASE",
        "status": contract["result_contract"]["complete_status"],
        "successor_formal_name": contract["successor_formal_name"],
        "phase6_contract_sha256": _sha_file_from_contract(contract),
        "candidate_id": candidate.candidate_id,
        "binding_sha256": strategy["binding_sha256"],
        "implementation_sha256": strategy["implementation_sha256"],
        "successor_normalizer_sha256": contract["methodology"]["successor_normalizer_sha256"],
        "successor_evaluator_sha256": contract["methodology"]["successor_evaluator_sha256"],
        "locked_symbols": list(locked),
        "benchmark_reference_symbol": benchmark_symbol,
        "methodology": contract["methodology"]["accounting"],
        "signal_price_convention": contract["methodology"]["signal_price_convention"],
        "execution_price_convention": contract["methodology"]["execution_price_convention"],
        "primary_friction_bps": 3,
        "metrics": primary,
        "friction_cases": cases,
        "benchmark_metrics": _summary(benchmark),
        "corporate_action_reconciliation": action_manifest,
        "candidate_search_executed": False,
        "candidate_parameters_changed": False,
        "holdout_symbol_substitution_executed": False,
        "one_time_consumed": True,
        "phase7_authorized": False,
        "phase7_started": False,
        "production_readiness_approved": False,
        "recon009_status": "OPEN",
    }


def _sha_file_from_contract(contract: dict[str, Any]) -> str:
    value = contract.get("_file_sha256")
    if not isinstance(value, str):
        raise ValueError("SUCCESSOR_PHASE6_CONTRACT_FILE_HASH_MISSING")
    return value


def evaluate_released_holdout(
    *,
    repository_root: Path,
    release_path: Path,
    contract_path: Path,
    authorization_path: Path,
    selection_path: Path,
    virginity_attestation_path: Path,
    virginity_evidence_path: Path,
    receipt_path: Path,
    encrypted_bundle_path: Path,
    key_path: Path,
    marker_directory: Path,
    output_path: Path,
) -> dict[str, Any]:
    output = Path(output_path)
    if output.exists():
        raise FileExistsError("SUCCESSOR_PHASE6_EVALUATION_RESULT_ALREADY_EXISTS")

    contract = verify_phase6_contract(contract_path)
    contract["_file_sha256"] = _sha_file(contract_path)
    release = load_release(release_path, contract_path=contract_path)
    receipt = load_receipt(
        receipt_path,
        contract_path=contract_path,
        authorization_path=authorization_path,
        selection_path=selection_path,
        virginity_attestation_path=virginity_attestation_path,
        virginity_evidence_path=virginity_evidence_path,
    )
    receipt_bytes = Path(receipt_path).read_bytes()
    if (
        release["holdout_id"] != receipt["holdout_id"]
        or release["holdout_bundle_sha256"] != receipt["bundle_sha256"]
        or release["holdout_key_sha256"] != receipt["key_sha256"]
        or release["acquisition_receipt_file_sha256"]
        != _sha_bytes(receipt_bytes)
    ):
        raise ValueError("SUCCESSOR_PHASE6_RELEASE_RECEIPT_IDENTITY_MISMATCH")

    try:
        key = bytes.fromhex(Path(key_path).read_text(encoding="ascii"))
    except (OSError, ValueError) as exc:
        raise ValueError("SUCCESSOR_PHASE6_KEY_INVALID") from exc
    if _sha_bytes(key) != release["holdout_key_sha256"]:
        raise ValueError("SUCCESSOR_PHASE6_KEY_HASH_MISMATCH")

    repository = Path(repository_root).resolve()
    receipt_parent = Path(receipt_path).resolve().parent
    if (
        Path(encrypted_bundle_path).resolve().parent != receipt_parent
        or Path(key_path).resolve().parent != receipt_parent
    ):
        raise ValueError("SUCCESSOR_PHASE6_PRIVATE_ARTIFACT_DIRECTORY_MISMATCH")
    try:
        receipt_parent.relative_to(repository)
    except ValueError:
        pass
    else:
        raise ValueError("SUCCESSOR_PHASE6_PRIVATE_ARTIFACTS_MUST_BE_OUTSIDE_REPOSITORY")

    canonical_marker_directory = receipt_parent / "evaluation-markers"
    if Path(marker_directory).resolve() != canonical_marker_directory:
        raise ValueError("SUCCESSOR_PHASE6_MARKER_DIRECTORY_INVALID")

    _verify_executing_implementation(contract, repository)

    marker = canonical_marker_directory / f"{release['release_id']}.consumed.json"
    marker_payload = {
        "schema_version": "SUCCESSOR-PHASE6-HOLDOUT-CONSUMPTION-v1",
        "status": "FINAL_HOLDOUT_RELEASE_CONSUMED",
        "release_id": release["release_id"],
        "holdout_id": release["holdout_id"],
        "candidate_id": release["candidate_id"],
        "phase6_contract_sha256": release["phase6_contract_sha256"],
        "holdout_bundle_sha256": release["holdout_bundle_sha256"],
        "retry_allowed": False,
    }
    _write_marker(marker, marker_payload, exclusive=True)

    try:
        encrypted = Path(encrypted_bundle_path).read_bytes()
        if _sha_bytes(encrypted) != release["holdout_bundle_sha256"]:
            raise ValueError("SUCCESSOR_PHASE6_BUNDLE_HASH_MISMATCH")
        plaintext = _decrypt(
            encrypted, key, contract["_file_sha256"]
        )
        result = _evaluate_plaintext(
            plaintext, receipt=receipt, contract=contract
        )
        result.update(
            {
                "release_id": release["release_id"],
                "holdout_id": release["holdout_id"],
            }
        )
    except Exception as exc:
        result = {
            "schema_version": RESULT_SCHEMA,
            "authority": "COORDINATOR_UNDER_INDEPENDENT_AUDIT_RELEASE",
            "status": contract["result_contract"]["incomplete_or_dq_status"],
            "reason": f"{type(exc).__name__}:{exc}",
            "successor_formal_name": contract["successor_formal_name"],
            "phase6_contract_sha256": contract["_file_sha256"],
            "release_id": release["release_id"],
            "holdout_id": release["holdout_id"],
            "candidate_id": contract["strategy"]["candidate_id"],
            "binding_sha256": contract["strategy"]["binding_sha256"],
            "implementation_sha256": contract["strategy"]["implementation_sha256"],
            "successor_normalizer_sha256": contract["methodology"]["successor_normalizer_sha256"],
            "successor_evaluator_sha256": contract["methodology"]["successor_evaluator_sha256"],
            "locked_symbols": list(contract["final_holdout"]["locked_symbols"]),
            "one_time_consumed": True,
            "retry_authorized": False,
            "candidate_search_executed": False,
            "candidate_parameters_changed": False,
            "holdout_symbol_substitution_executed": False,
            "phase7_authorized": False,
            "phase7_started": False,
            "production_readiness_approved": False,
            "recon009_status": "OPEN",
        }

    result_payload = _canonical_bytes(result)
    _write_exclusive_verified(output, result_payload)
    marker_payload.update(
        {
            "evaluation_status": result["status"],
            "evaluation_result_sha256": _sha_bytes(result_payload),
            "result_readback_verified": True,
        }
    )
    _write_marker(marker, marker_payload, exclusive=False)
    return result
