from __future__ import annotations

from datetime import date
from typing import Literal, NamedTuple


PHASE2_CAMPAIGN_ID = "PHASE2-CORRECTED-2010-2022-c33fb075"

PINNED_BOOTSTRAP_SOURCE_PATH = (
    "results/experiments/"
    "risk_managed_trend-ee8a71fb71e3d80f-"
    "20260911T194002253141Z-bcabf074.json"
)
PINNED_BOOTSTRAP_SOURCE_CONTENT_SHA256 = (
    "438dda42ceacece3c7d3b73512d9898017a4c180e1b368cdc7c6dee299f5d4b5"
)
PINNED_BOOTSTRAP_SOURCE_ARTIFACT_SHA256 = (
    "3e72fc05aa1c5d9e0ceca4a935ebb6672cd068d4bdf67b16c5d4fbbb121a797e"
)
PINNED_CANDIDATE_MANIFEST_SHA256 = (
    "378720494019e8904b50222a60f950c99307d57b27a4e40614f4641b8413cc3b"
)
PINNED_BOOTSTRAP_VECTOR_SHA256 = (
    "878b8400fcf93776feda23c454182d36dca5efd4c32f51d2aa232abf003bf0b5"
)


class PinnedBootstrapDataset(NamedTuple):
    symbol: str
    path: str
    content_hash: str


PINNED_BOOTSTRAP_DATASETS = (
    PinnedBootstrapDataset(
        symbol="QQQ",
        path=(
            "data/cache/moomoo/QQQ/1d/qfq/2010-01-01_2022-12-31/"
            "20260911T150943331113Z_"
            "3d28b4a98e049170f32db942751632a5a822807200dfb3daa90b07eea17d943f"
        ),
        content_hash=(
            "3d28b4a98e049170f32db942751632a5a822807200dfb3daa90b07eea17d943f"
        ),
    ),
    PinnedBootstrapDataset(
        symbol="TLT",
        path=(
            "data/cache/moomoo/TLT/1d/qfq/2010-01-01_2022-12-31/"
            "20260911T150945375035Z_"
            "56aed15476392a2b351d01096b94a7c34432552f383d994dc03ae8a1fb4aea34"
        ),
        content_hash=(
            "56aed15476392a2b351d01096b94a7c34432552f383d994dc03ae8a1fb4aea34"
        ),
    ),
    PinnedBootstrapDataset(
        symbol="IEF",
        path=(
            "data/cache/moomoo/IEF/1d/qfq/2010-01-01_2022-12-31/"
            "20260911T150945612969Z_"
            "fa0c89127c6cab2901a7a3a8bb8ed99b23aca4d24e2d42517fe295fb810b1bc9"
        ),
        content_hash=(
            "fa0c89127c6cab2901a7a3a8bb8ed99b23aca4d24e2d42517fe295fb810b1bc9"
        ),
    ),
)

PHASE3_UNIVERSE_PATH = (
    "results/phase3/universes/"
    "de880c30f4281c5f4a11358669e00c637a1a2fce9e635df963d607265d02ab76/"
    "manifest.json"
)
PHASE3_UNIVERSE_SHA256 = (
    "de880c30f4281c5f4a11358669e00c637a1a2fce9e635df963d607265d02ab76"
)
PHASE3_DQ_SNAPSHOT_PATH = (
    "results/phase3/campaigns/PHASE3-ETF-DQ-2014-2022-20260912T0254Z/"
    "dq-snapshots/"
    "2f1f8bfff500f61df97f091a2753134b193f1de7d881ab65708965cb4ed30e75.json"
)
PHASE3_DQ_SNAPSHOT_SHA256 = (
    "2f1f8bfff500f61df97f091a2753134b193f1de7d881ab65708965cb4ed30e75"
)
PHASE3_SYMBOLS = ("SPY", "QQQ", "IWM", "TLT", "IEF", "GLD", "VNQ", "XLP")


class PinnedPhase3Dataset(NamedTuple):
    symbol: str
    path: str
    sha256: str


def _phase3_dataset(symbol: str, sha256: str) -> PinnedPhase3Dataset:
    return PinnedPhase3Dataset(
        symbol=symbol,
        path=f"data/cache/phase3/normalized/sha256/{sha256}",
        sha256=sha256,
    )


PHASE3_DATASETS = (
    _phase3_dataset(
        "SPY", "1d52b313f43dcbe35ded7ab88d403b97e40e82b822b4eaa4aa29552cca5dc0c5"
    ),
    _phase3_dataset(
        "QQQ", "ee3379ac167c4403044c1b36196bf3b2f7e6a85f72ec2f2a8fd5a5dd6b812ed2"
    ),
    _phase3_dataset(
        "IWM", "f4095f49b54455e6fcde42b8dedea58f3723973998fd298d685c49ff991dbb03"
    ),
    _phase3_dataset(
        "TLT", "0e52e47f1dacbc01060ff8178429065d1bf02c8181d705ca8fa5e908e2660ab7"
    ),
    _phase3_dataset(
        "IEF", "a6e7573713d114ef171a43f9c6d4fca9911af0b9dcb39093adb210176fc686e4"
    ),
    _phase3_dataset(
        "GLD", "faa0bff3a8afa09f5bd16c7fd21c0b93b6a4dfbc01e9f7567f70b68f7aeb523b"
    ),
    _phase3_dataset(
        "VNQ", "104349e90a0b823f3980d2df25f88fcd291395e6986addc65eecabf90a17acba"
    ),
    _phase3_dataset(
        "XLP", "986b5949ddef81d603de79e664b63c9ce69d0ba4cbe1a984ef736cbafe16785f"
    ),
)

PHASE4_SPLIT_POLICY_VERSION = "PHASE4-TEMPORAL-SPLIT-v1"
PHASE4_TRAIN_START = date(2014, 1, 2)
PHASE4_TRAIN_END = date(2018, 12, 31)
PHASE4_VALIDATION_START = date(2019, 1, 1)
PHASE4_VALIDATION_END = date(2022, 12, 30)
PHASE4_TRAIN_ROW_COUNT = 1258
PHASE4_VALIDATION_ROW_COUNT = 1008

ArtifactKind = Literal[
    "phase2_experiment",
    "phase3_universe_manifest",
    "phase3_dq_snapshot",
    "phase3_normalized_dataset",
    "bootstrap_input_vector",
    "bootstrap_audit",
    "trial_authority",
    "phase4_split_manifest",
    "phase4_campaign_configuration",
    "phase4_readiness_manifest",
    "phase4_readiness_report",
]
