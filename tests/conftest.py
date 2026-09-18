from __future__ import annotations

import pytest


@pytest.fixture
def identity_factory():
    from investment_tracker.quant.phase4.gate3.models import ArtifactIdentity
    from investment_tracker.quant.phase4.preregistration.canonical import artifact_envelope_identity

    def make(kind: str, path: str, content_sha256: str = "0" * 64) -> ArtifactIdentity:
        return ArtifactIdentity(
            kind=kind,
            content_sha256=content_sha256,
            path=path,
            sha256=artifact_envelope_identity(
                content_sha256=content_sha256,
                kind=kind,
                path=path,
            ),
        )

    return make
