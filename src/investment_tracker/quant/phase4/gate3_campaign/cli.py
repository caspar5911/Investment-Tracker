"""Nonexecuting result-schema seal and explicit-hash preflight only."""
from __future__ import annotations
import argparse,json,sys
from pathlib import Path
from .result_methodology import preflight_result_schema,seal_result_schema

def main(argv=None):
    parser=argparse.ArgumentParser(prog='phase4-gate3-result-schema');commands=parser.add_subparsers(dest='command',required=True)
    seal=commands.add_parser('seal');seal.add_argument('--repository-root',required=True);seal.add_argument('--source-revision',required=True)
    preflight=commands.add_parser('preflight');preflight.add_argument('--repository-root',required=True);preflight.add_argument('--manifest-content-sha256',required=True)
    args=parser.parse_args(argv)
    try:
        if args.command=='seal': output={'status':'GATE3_CAMPAIGN_RESULT_SCHEMA_SEALED','manifest':seal_result_schema(Path(args.repository_root),args.source_revision).model_dump(mode='json')}
        else: output=preflight_result_schema(Path(args.repository_root),args.manifest_content_sha256).model_dump(mode='json')
    except (ValueError,OSError) as exc: print(str(exc),file=sys.stderr);return 1
    print(json.dumps(output,sort_keys=True,separators=(',',':')));return 0

if __name__=='__main__': raise SystemExit(main())
