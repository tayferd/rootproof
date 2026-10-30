"""Fixed cross-runtime vectors and a recursive reference for RFC 9162 trees."""

from datetime import datetime, timezone
import hashlib
from uuid import UUID

import pytest

from integrity.commitments import encode_registration
from integrity.merkle import MERKLE_VERSION, leaf_hash, merkle_root, node_hash


# Inputs are the one-byte strings 00, 01, ... up to size - 1.
# Independently computed with Node.js crypto and the recursive RFC definition.
ROOTS = [
    "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
    "96a296d224f285c67bee93c30f8a309157f0daa35dc5b87e410b78630a09cfc7",
    "a20bf9a7cc2dc8a08f5f415a71b19f6ac427bab54d24eec868b5d3103449953a",
    "3b6cccd7e3e023ff393006f030315ee7ad9eb111b022b41fba7e5b7a3973f688",
    "9bcd51240af4005168f033121ba85be5a6ed4f0e6a5fac262066729b8fbfdecb",
    "b855b42d6c30f5b087e05266783fbd6e394f7b926013ccaa67700a8b0c5a596f",
    "bb36e7d3d4cee5720cbd323d02fab15962e2ba1dadf5f8fc6eeef4fd6ad056a8",
    "3560191803028444b232018ac047fdb561c09c23a7a6876c85e08b5e4d48e9f3",
    "ef7f49b620f6c7ea9b963a214da34b5021c6ded8ed57734380a311ab726aa907",
]


@pytest.mark.parametrize("size", range(9))
def test_fixed_roots(size: int) -> None:
    assert merkle_root([bytes([i]) for i in range(size)]).hex() == ROOTS[size]


def reference_root(entries: list[bytes]) -> bytes:
    if not entries:
        return hashlib.sha256(b"").digest()
    if len(entries) == 1:
        return hashlib.sha256(b"\x00" + entries[0]).digest()
    split = 1 << ((len(entries) - 1).bit_length() - 1)
    return hashlib.sha256(b"\x01" + reference_root(entries[:split]) + reference_root(entries[split:])).digest()


@pytest.mark.parametrize("size", [0, 1, 2, 3, 5, 7, 15, 16, 17, 31, 32, 33, 255, 256, 257, 1025])
def test_streaming_matches_recursive_definition(size: int) -> None:
    entries = [i.to_bytes(4, "big") for i in range(size)]
    assert merkle_root(iter(entries)) == reference_root(entries)


def test_order_count_and_duplicate_entries_matter() -> None:
    assert merkle_root([b"a", b"b"]) != merkle_root([b"b", b"a"])
    assert merkle_root([b"a", b"b", b"c"]) != merkle_root([b"a", b"b", b"c", b"c"])
    assert merkle_root([b"a"]) != merkle_root([b"a", b"a"])
    assert merkle_root([]) != merkle_root([b""])


def test_leaf_and_node_domains_are_separate() -> None:
    left, right = leaf_hash(b"a"), leaf_hash(b"b")
    assert leaf_hash(left + right) != node_hash(left, right)
    assert merkle_root([b"a"]) == left


def test_registration_metadata_is_protected() -> None:
    fields = dict(
        registration_id=UUID("00000000-0000-0000-0000-000000000001"),
        digest="a" * 64, received_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )
    original = encode_registration(**fields, registration_metadata={"document_name": "first.pdf"})
    changed = encode_registration(**fields, registration_metadata={"document_name": "second.pdf"})
    assert merkle_root([original]) != merkle_root([changed])


@pytest.mark.parametrize("entries", [b"abc", "abc", {b"a", b"b"}, {"key": b"a"}, ["text"], [bytearray(b"a")]])
def test_invalid_entry_types(entries) -> None:
    with pytest.raises(TypeError):
        merkle_root(entries)


@pytest.mark.parametrize("left,right", [(b"", b"x" * 32), (b"x" * 32, b"x" * 31), (b"x" * 33, b"x" * 32)])
def test_invalid_node_lengths(left: bytes, right: bytes) -> None:
    with pytest.raises(ValueError):
        node_hash(left, right)


def test_unknown_version_rejected() -> None:
    with pytest.raises(ValueError):
        merkle_root([], version="future")
    assert len(merkle_root([], version=MERKLE_VERSION)) == 32
