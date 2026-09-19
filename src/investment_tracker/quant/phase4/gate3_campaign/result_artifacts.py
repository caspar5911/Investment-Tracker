"""Append-only exact-byte publication for future candidate results."""
from __future__ import annotations

from hashlib import sha256
import os
from pathlib import Path
import tempfile

from investment_tracker.quant.phase4.gate3.filesystem import contained_path, resolve_repository_root
from investment_tracker.quant.phase4.gate3.models import ArtifactIdentity, Gate3AuthorityError
from investment_tracker.quant.phase4.preregistration.canonical import artifact_envelope_identity, normalize_repository_path

from .codec import canonical_bytes, decode
from .result_schema import CandidateResult
from .validation import validate_result


class ResultArtifactStore:
    """A fixed candidate-result subtree; construction follows no latest pointer."""

    def __init__(self, repository_root: Path) -> None:
        try:
            self.root = resolve_repository_root(repository_root, code='ARTIFACT_PATH_INVALID')
            contained_path(self.root, ('results','phase4','gate3','campaign','candidate_result'), code='ARTIFACT_PATH_INVALID')
        except Gate3AuthorityError as exc:
            raise ValueError('ARTIFACT_PATH_INVALID: redirect or escape rejected') from exc

    def _path(self, content: str) -> Path:
        if len(content) != 64 or any(ch not in '0123456789abcdef' for ch in content):
            raise ValueError('ARTIFACT_IDENTITY_INVALID: canonical digest required')
        try:
            return contained_path(self.root, ('results','phase4','gate3','campaign','candidate_result','sha256',content,'record.json'), code='ARTIFACT_PATH_INVALID')
        except Gate3AuthorityError as exc:
            raise ValueError('ARTIFACT_PATH_INVALID: redirect or escape rejected') from exc

    def _identity(self, content: str) -> ArtifactIdentity:
        path = self._path(content)
        relative = normalize_repository_path(self.root, path)
        return ArtifactIdentity(kind='phase4_gate3_candidate_result', content_sha256=content, path=relative,
                                sha256=artifact_envelope_identity(content_sha256=content, kind='phase4_gate3_candidate_result', path=relative))

    def _publish(self, payload: bytes, identity: ArtifactIdentity) -> None:
        destination = self._path(identity.content_sha256)
        if destination.exists() or destination.is_symlink():
            if destination.is_symlink() or not destination.is_file() or destination.read_bytes() != payload:
                raise ValueError('IMMUTABLE_ARTIFACT_COLLISION: unequal fixed-address content')
            return
        destination.parent.mkdir(parents=True, exist_ok=True)
        self._path(identity.content_sha256)
        handle, name = tempfile.mkstemp(prefix='.tmp-gate3-result-', dir=destination.parent)
        temporary = Path(name)
        try:
            with os.fdopen(handle, 'wb') as stream:
                stream.write(payload); stream.flush(); os.fsync(stream.fileno())
            try:
                os.link(temporary, destination)
            except FileExistsError:
                if destination.is_symlink() or not destination.is_file() or destination.read_bytes() != payload:
                    raise ValueError('IMMUTABLE_ARTIFACT_COLLISION: concurrent unequal content')
        finally:
            temporary.unlink(missing_ok=True)

    def write_result(self, record: CandidateResult, authority) -> ArtifactIdentity:
        record = validate_result(record, authority, resolver=lambda identity: self.read_result(identity, authority))
        payload = canonical_bytes(record)
        identity = self._identity(sha256(payload).hexdigest())
        self._publish(payload, identity)
        return identity

    def read_result(self, identity: ArtifactIdentity, authority) -> CandidateResult:
        if not isinstance(identity, ArtifactIdentity):
            raise ValueError('ARTIFACT_IDENTITY_INVALID: typed identity required')
        expected = self._identity(identity.content_sha256)
        if identity != expected:
            raise ValueError('ARTIFACT_IDENTITY_INVALID: noncanonical path or envelope')
        path = self._path(identity.content_sha256)
        try:
            payload = path.read_bytes()
        except OSError as exc:
            raise ValueError('ARTIFACT_BYTES_INVALID: referenced bytes missing') from exc
        if sha256(payload).hexdigest() != identity.content_sha256:
            raise ValueError('ARTIFACT_BYTES_INVALID: content digest changed')
        try:
            record = decode(CandidateResult, payload)
        except (TypeError, ValueError) as exc:
            raise ValueError('ARTIFACT_BYTES_INVALID: invalid canonical result') from exc
        if canonical_bytes(record) != payload:
            raise ValueError('ARTIFACT_BYTES_INVALID: noncanonical JSON')
        return validate_result(record, authority, resolver=lambda item: self.read_result(item, authority))
