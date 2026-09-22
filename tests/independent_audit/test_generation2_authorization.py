from pathlib import Path
import json
import pytest
from investment_tracker.independent_audit.generation2 import authorization as a

def _w(p, obj):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, sort_keys=True, separators=(",", ":")), encoding="utf-8")
    return p

def test_issue_requires_green_ci(monkeypatch, tmp_path: Path):
    with pytest.raises(ValueError, match="GEN2_AUTH_CI_NOT_GREEN"):
        a.issue_authorization(
            repository_root=tmp_path,
            contract_path=tmp_path/"c",
            preaccess_status_path=tmp_path/"p",
            attestation_path=tmp_path/"a",
            evidence_path=tmp_path/"e",
            provenance_root=tmp_path/"prov",
            evidence_commit_sha="a"*40,
            ci_run_id=1,
            ci_conclusion="failure",
            output_path=tmp_path/"out.json",
        )

def test_issue_binds_all_inputs(monkeypatch, tmp_path: Path):
    contract_path=_w(tmp_path/"contract.json", {"x":1})
    pre=_w(tmp_path/"pre.json", {
        "status":"GENERATION2_PHASE6_PREACCESS_READY",
        "historical_acquisition_authorized":False,
        "locked_symbols":list(a.LOCKED_SYMBOLS),
    })
    att=_w(tmp_path/"att.json", {"x":2})
    ev=_w(tmp_path/"ev.json", {"x":3})
    monkeypatch.setattr(a, "verify_contract", lambda p: {
        "contract_sha256":"c"*64,
        "strategy":{
            "candidate_id":a.FROZEN_CANDIDATE_ID,
            "binding_sha256":a.FROZEN_BINDING_SHA256,
            "implementation_sha256":a.FROZEN_IMPLEMENTATION_SHA256,
            "survivor_identity_report_sha256":a.FROZEN_IDENTITY_SHA256,
        },
        "final_holdout":{
            "locked_symbols":list(a.LOCKED_SYMBOLS),
            "preaccess_status_sha256":a._sha(pre),
            "virginity_attestation_sha256":a._sha(att),
            "virginity_evidence_sha256":a._sha(ev),
            "independent_reconciliation_sha256":"d"*64,
        },
        "governance":{"historical_access_authorized":False},
    })
    monkeypatch.setattr(a, "verify_attestation", lambda **k: {"locked_symbols":list(a.LOCKED_SYMBOLS)})
    monkeypatch.setattr(a, "verify_cache_provenance", lambda p: {
        "status":"MATCHED","independent_source_established":True,"decision_critical":False,
        "reconciliation_sha256":"d"*64,
    })
    out=tmp_path/"auth.json"
    a.issue_authorization(
        repository_root=tmp_path,
        contract_path=contract_path,
        preaccess_status_path=pre,
        attestation_path=att,
        evidence_path=ev,
        provenance_root=tmp_path/"prov",
        evidence_commit_sha="9"*40,
        ci_run_id=123,
        ci_conclusion="success",
        output_path=out,
    )
    payload=json.loads(out.read_text())
    assert payload["status"]==a.AUTH_STATUS
    assert payload["one_time"] is True
    assert payload["acquisition_start_marker_required_before_provider_read"] is True
    assert payload["retry_after_historical_access_allowed"] is False
    assert payload["holdout_performance_inspected"] is False

def test_existing_authorization_refused(monkeypatch, tmp_path: Path):
    out=tmp_path/"auth.json"; out.write_text("{}")
    with pytest.raises(ValueError, match="GEN2_AUTH_CI_NOT_GREEN"):
        a.issue_authorization(
            repository_root=tmp_path, contract_path=tmp_path/"c", preaccess_status_path=tmp_path/"p",
            attestation_path=tmp_path/"a", evidence_path=tmp_path/"e", provenance_root=tmp_path/"prov",
            evidence_commit_sha="a"*40, ci_run_id=1, ci_conclusion="failure", output_path=out
        )
