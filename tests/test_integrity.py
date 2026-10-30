"""Known digests and exact encoding vectors for independently reproducible bytes."""

from datetime import datetime, timedelta, timezone
from pathlib import Path
import subprocess
import sys
from uuid import UUID

import pytest

from integrity.commitments import encode_registration
from integrity.hashing import hash_file


@pytest.mark.parametrize(("contents", "expected"), [
    (b"", "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"),
    (b"abc", "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"),
    (b"a" * 1_000_000, "cdc76e5c9914fb9281a1c7e284d73e67f1809a48a497200e046d39ccc7112cd0"),
], ids=["empty", "abc", "million-a"])
def test_sha256_vectors(tmp_path: Path, contents: bytes, expected: str) -> None:
    path = tmp_path / "sample.bin"
    path.write_bytes(contents)
    assert hash_file(path) == expected


def test_changed_bytes_and_renaming(tmp_path: Path) -> None:
    path = tmp_path / "original.txt"
    path.write_bytes(b"abc")
    original = hash_file(path)
    renamed = path.rename(tmp_path / "renamed.txt")
    assert hash_file(renamed) == original
    renamed.write_bytes(b"abc\n")
    assert hash_file(renamed) != original


def registration(**overrides):
    return dict(
        registration_id=UUID("00000000-0000-0000-0000-000000000001"),
        digest="a" * 64,
        received_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        registration_metadata={"document_name": "example.pdf"},
    ) | overrides


def test_exact_commitment_vector() -> None:
    expected = (
        '{"digest":"' + "a" * 64 + '","format_version":1,"hash_algorithm":"sha256",'
        '"id":"00000000-0000-0000-0000-000000000001",'
        '"received_at":"2026-01-01T00:00:00.000000Z",'
        '"registration_metadata":{"document_name":"example.pdf"},'
        '"type":"rootproof.registration"}'
    ).encode()
    assert encode_registration(**registration()) == expected


def test_key_order_and_timezone_are_canonical() -> None:
    first = registration(registration_metadata={"b": 2, "a": {"d": 4, "c": 3}})
    second = registration(
        registration_metadata={"a": {"c": 3, "d": 4}, "b": 2},
        received_at=datetime(2025, 12, 31, 19, tzinfo=timezone(timedelta(hours=-5))),
    )
    assert encode_registration(**first) == encode_registration(**second)


@pytest.mark.parametrize("changes", [
    {"digest": "b" * 64},
    {"registration_metadata": {"document_name": "changed.pdf"}},
    {"registration_id": UUID("00000000-0000-0000-0000-000000000002")},
    {"received_at": datetime(2026, 1, 2, tzinfo=timezone.utc)},
])
def test_protected_field_changes_change_encoding(changes) -> None:
    assert encode_registration(**registration(**changes)) != encode_registration(**registration())


@pytest.mark.parametrize("changes", [
    {"digest": "A" * 64}, {"hash_algorithm": "md5"}, {"format_version": 2},
    {"format_version": True}, {"received_at": datetime(2026, 1, 1)},
    {"registration_metadata": []},
])
def test_invalid_commitment_fields(changes) -> None:
    with pytest.raises(ValueError):
        encode_registration(**registration(**changes))


@pytest.mark.parametrize("value", [float("nan"), float("inf"), 2**53, 1e20])
def test_nonportable_numbers_rejected(value) -> None:
    with pytest.raises(ValueError):
        encode_registration(**registration(registration_metadata={"number": value}))


def test_changes_during_hashing_are_reported(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import os

    path = tmp_path / "changing.txt"
    path.write_bytes(b"abc")
    original_fstat = os.fstat
    calls = 0

    def changing_fstat(descriptor):
        nonlocal calls
        calls += 1
        if calls == 2:
            with path.open("ab") as changed:
                changed.write(b"d")
        return original_fstat(descriptor)

    monkeypatch.setattr("integrity.hashing.os.fstat", changing_fstat)
    with pytest.raises(ValueError, match="changed while being read"):
        hash_file(path)


def test_cli_success_and_missing_file(tmp_path: Path) -> None:
    path = tmp_path / "sample.txt"
    path.write_bytes(b"abc")
    result = subprocess.run([sys.executable, "-m", "clients", "hash", str(path)], capture_output=True, text=True)
    assert result.returncode == 0
    assert '"digest": "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"' in result.stdout
    missing = subprocess.run([sys.executable, "-m", "clients", "hash", str(path) + ".missing"], capture_output=True, text=True)
    assert missing.returncode == 1
    assert "Hashing failed" in missing.stderr
