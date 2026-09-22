from __future__ import annotations

import pytest

from investment_tracker.independent_audit.phase6.bundle import (
    build_plain_bundle,
    decrypt_bundle,
    encrypt_bundle,
    open_plain_bundle,
)


def test_bundle_is_canonical_identity_checked_and_encrypted():
    plain, manifest = build_plain_bundle(
        manifest={"schema_version": "test"},
        entries={"bars/A.csv": b"a,b\n1,2\n", "bars/B.csv": b"a,b\n3,4\n"},
    )
    parsed_manifest, entries = open_plain_bundle(plain)
    assert parsed_manifest == manifest
    assert entries["bars/A.csv"] == b"a,b\n1,2\n"

    encrypted, key = encrypt_bundle(
        plain,
        key=b"k" * 32,
        nonce=b"n" * 12,
    )
    assert encrypted != plain
    assert decrypt_bundle(encrypted, key=key) == plain


def test_ciphertext_or_key_tampering_fails_closed():
    plain, _ = build_plain_bundle(
        manifest={"schema_version": "test"},
        entries={"bars/A.csv": b"x"},
    )
    encrypted, key = encrypt_bundle(
        plain,
        key=b"k" * 32,
        nonce=b"n" * 12,
    )
    corrupted = encrypted[:-1] + bytes([encrypted[-1] ^ 1])
    with pytest.raises(ValueError, match="DECRYPTION_FAILED"):
        decrypt_bundle(corrupted, key=key)
    with pytest.raises(ValueError, match="DECRYPTION_FAILED"):
        decrypt_bundle(encrypted, key=b"z" * 32)
