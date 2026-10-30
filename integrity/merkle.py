"""SHA-256 Merkle tree hashes following RFC 9162 section 2.1."""

from collections.abc import Iterable, Mapping, Set
import hashlib

MERKLE_VERSION = "rootproof.merkle.rfc9162.sha256.v1"


def leaf_hash(entry: bytes) -> bytes:
    """Hash encoded registration bytes, not a hex string or prehashed leaf."""
    if not isinstance(entry, bytes):
        raise TypeError("Merkle entries must be bytes")
    return hashlib.sha256(b"\x00" + entry).digest()


def node_hash(left: bytes, right: bytes) -> bytes:
    if not isinstance(left, bytes) or not isinstance(right, bytes):
        raise TypeError("Merkle child hashes must be bytes")
    if len(left) != 32 or len(right) != 32:
        raise ValueError("Merkle child hashes must each contain 32 bytes")
    return hashlib.sha256(b"\x01" + left + right).digest()


def merkle_root(entries: Iterable[bytes], *, version: str = MERKLE_VERSION) -> bytes:
    """Preserve entry order; return the RFC tree hash using logarithmic memory."""
    if version != MERKLE_VERSION:
        raise ValueError("Unsupported Merkle construction version")
    if isinstance(entries, (bytes, bytearray, str, Mapping, Set)):
        raise TypeError("Provide an ordered iterable of byte entries")
    stack: list[bytes] = []
    count = 0
    for entry in entries:
        current = leaf_hash(entry)
        occupied = count
        while occupied & 1:
            current = node_hash(stack.pop(), current)
            occupied >>= 1
        stack.append(current)
        count += 1
    if not stack:
        return hashlib.sha256(b"").digest()
    current = stack.pop()
    while stack:
        current = node_hash(stack.pop(), current)
    return current
