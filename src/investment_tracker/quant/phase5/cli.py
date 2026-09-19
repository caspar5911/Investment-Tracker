from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path

from .artifacts import seal_evaluation
from .opend import export_opend_bundle
from .reconstruction import evaluate_bundle

SPEC_PATH = "docs/superpowers/specs/2026-09-19-phase-5-decision-grade-long-history-design.md"


def _spec_sha(root: Path) -> str:
    return sha256((root / SPEC_PATH).read_bytes()).hexdigest()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="investment-tracker-phase5")
    sub = parser.add_subparsers(dest="command", required=True)

    export = sub.add_parser("export-opend")
    export.add_argument("--output-dir", required=True)
    export.add_argument("--host", default="127.0.0.1")
    export.add_argument("--port", type=int, default=11111)

    evaluate = sub.add_parser("evaluate")
    evaluate.add_argument("--provider-dir", required=True)
    evaluate.add_argument("--repository-root", default=".")
    evaluate.add_argument("--massive-snapshot")
    evaluate.add_argument("--output")

    seal = sub.add_parser("seal")
    seal.add_argument("--provider-dir", required=True)
    seal.add_argument("--repository-root", default=".")
    seal.add_argument("--massive-snapshot", required=True)
    seal.add_argument("--results-root", default="results/phase5")
    seal.add_argument("--source-revision", required=True)

    args = parser.parse_args(argv)
    if args.command == "export-opend":
        print(export_opend_bundle(Path(args.output_dir), host=args.host, port=args.port))
        return 0

    repository = Path(args.repository_root).resolve()
    result = evaluate_bundle(
        Path(args.provider_dir),
        repository_root=repository,
        massive_snapshot=None if not getattr(args, "massive_snapshot", None) else Path(args.massive_snapshot),
    )
    if args.command == "evaluate":
        payload = json.dumps(result, sort_keys=True, separators=(",", ":"))
        if args.output:
            Path(args.output).write_text(payload, encoding="utf-8")
        print(payload)
        return 0 if result["status"] != "PHASE5_UNKNOWN_ABSTAIN" else 2

    manifest = seal_evaluation(
        Path(args.results_root),
        result,
        source_revision=args.source_revision,
        spec_content_sha256=_spec_sha(repository),
    )
    print(json.dumps(manifest, sort_keys=True, separators=(",", ":")))
    return 0 if result["status"] != "PHASE5_UNKNOWN_ABSTAIN" else 2


if __name__ == "__main__":
    raise SystemExit(main())
