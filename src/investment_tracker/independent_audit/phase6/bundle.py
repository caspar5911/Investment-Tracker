from __future__ import annotations

from hashlib import sha256
from io import BytesIO
import json
from pathlib import PurePosixPath
import zipfile

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from .authority import CONTRACT_SHA256, canonical_json_bytes, sha256_bytes

MAGIC = b"PHASE6-AESGCM-v1\n"
NONCE_BYTES = 12
KEY_BYTES = 32


def _safe_name(name: str) -> str:
    path = PurePosixPath(name)
    if (
        not name
        or "\\" in name
        or name.startswith("/")
        or any(part in {"", ".", ".."} for part in path.parts)
    ):
        raise ValueError("PHASE6_BUNDLE_PATH_INVALID")
    return name


def _write_member(archive: zipfile.ZipFile, name: str, payload: bytes) -> None:
    info = zipfile.ZipInfo(_safe_name(name), date_time=(1980, 1, 1, 0, 0, 0))
    info.compress_type = zipfile.ZIP_STORED
    info.create_system = 3
    info.external_attr = 0o600 << 16
    archive.writestr(info, payload)


def build_plain_bundle(
    *,
    manifest: dict[str, object],
    entries: dict[str, bytes],
) -> tuple[bytes, dict[str, object]]:
    if "files" in manifest:
        raise ValueError("PHASE6_BUNDLE_MANIFEST_FILES_RESERVED")
    ordered_entries = {name: entries[name] for name in sorted(entries)}
    files = [
        {
            "path": _safe_name(name),
            "sha256": sha256_bytes(payload),
            "bytes": len(payload),
        }
        for name, payload in ordered_entries.items()
    ]
    full_manifest = {**manifest, "files": files}
    manifest_bytes = canonical_json_bytes(full_manifest)

    buffer = BytesIO()
    with zipfile.ZipFile(buffer, mode="w") as archive:
        _write_member(archive, "manifest.json", manifest_bytes)
        for name, payload in ordered_entries.items():
            _write_member(archive, name, payload)
    return buffer.getvalue(), full_manifest


def open_plain_bundle(payload: bytes) -> tuple[dict[str, object], dict[str, bytes]]:
    try:
        archive = zipfile.ZipFile(BytesIO(payload), mode="r")
    except zipfile.BadZipFile as exc:
        raise ValueError("PHASE6_BUNDLE_ARCHIVE_INVALID") from exc
    with archive:
        names = archive.namelist()
        if not names or names[0] != "manifest.json" or len(names) != len(set(names)):
            raise ValueError("PHASE6_BUNDLE_ARCHIVE_LAYOUT_INVALID")
        if any(_safe_name(name) != name for name in names):
            raise ValueError("PHASE6_BUNDLE_ARCHIVE_LAYOUT_INVALID")
        try:
            manifest = json.loads(archive.read("manifest.json"))
        except (KeyError, json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise ValueError("PHASE6_BUNDLE_MANIFEST_INVALID") from exc
        if not isinstance(manifest, dict):
            raise ValueError("PHASE6_BUNDLE_MANIFEST_INVALID")
        files = manifest.get("files")
        if not isinstance(files, list):
            raise ValueError("PHASE6_BUNDLE_FILESET_INVALID")
        expected_names: list[str] = []
        entries: dict[str, bytes] = {}
        for item in files:
            if not isinstance(item, dict):
                raise ValueError("PHASE6_BUNDLE_FILESET_INVALID")
            name = item.get("path")
            expected_sha = item.get("sha256")
            expected_bytes = item.get("bytes")
            if (
                not isinstance(name, str)
                or not isinstance(expected_sha, str)
                or not isinstance(expected_bytes, int)
            ):
                raise ValueError("PHASE6_BUNDLE_FILESET_INVALID")
            _safe_name(name)
            try:
                member = archive.read(name)
            except KeyError as exc:
                raise ValueError("PHASE6_BUNDLE_MEMBER_MISSING") from exc
            if len(member) != expected_bytes or sha256_bytes(member) != expected_sha:
                raise ValueError("PHASE6_BUNDLE_MEMBER_IDENTITY_MISMATCH")
            expected_names.append(name)
            entries[name] = member
        if names != ["manifest.json", *sorted(expected_names)]:
            raise ValueError("PHASE6_BUNDLE_ARCHIVE_LAYOUT_INVALID")
        return manifest, entries


def encrypt_bundle(
    plaintext: bytes,
    *,
    key: bytes | None = None,
    nonce: bytes | None = None,
) -> tuple[bytes, bytes]:
    import os

    actual_key = AESGCM.generate_key(bit_length=256) if key is None else bytes(key)
    actual_nonce = os.urandom(NONCE_BYTES) if nonce is None else bytes(nonce)
    if len(actual_key) != KEY_BYTES or len(actual_nonce) != NONCE_BYTES:
        raise ValueError("PHASE6_BUNDLE_CIPHER_INPUT_INVALID")
    ciphertext = AESGCM(actual_key).encrypt(
        actual_nonce,
        plaintext,
        CONTRACT_SHA256.encode("ascii"),
    )
    return MAGIC + actual_nonce + ciphertext, actual_key


def decrypt_bundle(payload: bytes, *, key: bytes) -> bytes:
    if len(key) != KEY_BYTES or not payload.startswith(MAGIC):
        raise ValueError("PHASE6_BUNDLE_CIPHER_FORMAT_INVALID")
    offset = len(MAGIC)
    nonce = payload[offset : offset + NONCE_BYTES]
    ciphertext = payload[offset + NONCE_BYTES :]
    if len(nonce) != NONCE_BYTES or not ciphertext:
        raise ValueError("PHASE6_BUNDLE_CIPHER_FORMAT_INVALID")
    try:
        return AESGCM(bytes(key)).decrypt(
            nonce,
            ciphertext,
            CONTRACT_SHA256.encode("ascii"),
        )
    except Exception as exc:
        raise ValueError("PHASE6_BUNDLE_DECRYPTION_FAILED") from exc


def bundle_identity(payload: bytes) -> str:
    return sha256(payload).hexdigest()
