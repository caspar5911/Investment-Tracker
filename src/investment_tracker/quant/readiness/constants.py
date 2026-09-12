from __future__ import annotations

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
