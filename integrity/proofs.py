"""RFC 9162 inclusion paths, ordered from the leaf toward the root."""

from collections.abc import Sequence

from integrity.merkle import MERKLE_VERSION, merkle_root

PROOF_VERSION = "rootproof.inclusion.rfc9162.sha256.v1"


def inclusion_proof(
    entries: Sequence[bytes], leaf_index: int, *, version: str = MERKLE_VERSION,
) -> list[bytes]:
    if version != MERKLE_VERSION:
        raise ValueError("Unsupported Merkle construction version")
    if not isinstance(entries, Sequence) or isinstance(entries, (bytes, bytearray, str)):
        raise TypeError("Provide an ordered sequence of byte entries")
    snapshot = tuple(entries)
    if any(not isinstance(entry, bytes) for entry in snapshot):
        raise TypeError("Merkle entries must be bytes")
    if type(leaf_index) is not int or not 0 <= leaf_index < len(snapshot):
        raise ValueError("Leaf index is outside the tree")

    def path(items: tuple[bytes, ...], index: int) -> list[bytes]:
        if len(items) == 1:
            return []
        split = 1 << ((len(items) - 1).bit_length() - 1)
        if index < split:
            return path(items[:split], index) + [merkle_root(items[split:])]
        return path(items[split:], index - split) + [merkle_root(items[:split])]

    return path(snapshot, leaf_index)
