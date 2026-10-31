"""Check proof generation using an independently structured RFC verifier."""

import hashlib

import pytest

from integrity.merkle import merkle_root
from integrity.proofs import inclusion_proof


def reference_verify(entry: bytes, index: int, size: int, path: list[bytes], root: bytes) -> bool:
    """RFC 9162 section 2.1.3.2; does not call production hashing helpers."""
    if not 0 <= index < size:
        return False
    fn, sn = index, size - 1
    value = hashlib.sha256(b"\x00" + entry).digest()
    for sibling in path:
        if sn == 0:
            return False
        if fn & 1 or fn == sn:
            value = hashlib.sha256(b"\x01" + sibling + value).digest()
            while fn and not fn & 1:
                fn >>= 1
                sn >>= 1
        else:
            value = hashlib.sha256(b"\x01" + value + sibling).digest()
        fn >>= 1
        sn >>= 1
    return sn == 0 and value == root


@pytest.mark.parametrize("size", [1, 2, 3, 5, 7, 8, 9, 15, 16, 17, 31, 32, 33, 1000])
def test_every_leaf_proof_verifies(size: int) -> None:
    entries = [i.to_bytes(4, "big") for i in range(size)]
    root = merkle_root(entries)
    # Check all positions for small trees and boundary/interior positions at max size.
    indexes = range(size) if size < 1000 else [0, 1, 499, 511, 512, 998, 999]
    for index in indexes:
        path = inclusion_proof(entries, index)
        assert reference_verify(entries[index], index, size, path, root)
        assert not reference_verify(b"tampered", index, size, path, root)


def test_singleton_and_odd_tree_paths() -> None:
    assert inclusion_proof([b"a"], 0) == []
    entries = [b"a", b"b", b"c"]
    assert inclusion_proof(entries, 2) == [merkle_root(entries[:2])]
    assert inclusion_proof(entries, 0) == [merkle_root([b"b"]), merkle_root([b"c"])]


@pytest.mark.parametrize("index", [-1, 3, True, 0.0])
def test_invalid_indexes(index) -> None:
    with pytest.raises(ValueError):
        inclusion_proof([b"a", b"b", b"c"], index)


def test_empty_tree_and_unknown_version() -> None:
    with pytest.raises(ValueError):
        inclusion_proof([], 0)
    with pytest.raises(ValueError):
        inclusion_proof([b"a"], 0, version="unknown")


@pytest.mark.parametrize("entries", [b"a", "a", {b"a"}, ["a"], [bytearray(b"a")]])
def test_invalid_entries(entries) -> None:
    with pytest.raises(TypeError):
        inclusion_proof(entries, 0)
