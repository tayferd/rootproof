"""RFC 9162 inclusion paths, ordered from the leaf toward the root."""

from collections.abc import Sequence

from integrity.merkle import MERKLE_VERSION, leaf_hash, merkle_root, node_hash

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


def verify_inclusion(
    entry: bytes, leaf_index: int, tree_size: int,
    audit_path: Sequence[bytes], root: bytes, *, version: str = MERKLE_VERSION,
) -> bool:
    """Verify RFC 9162 inclusion against a supplied root, not its provenance."""
    if version != MERKLE_VERSION:
        raise ValueError("Unsupported Merkle construction version")
    if type(leaf_index) is not int or type(tree_size) is not int or not 0 <= leaf_index < tree_size:
        return False
    if not isinstance(root, bytes) or len(root) != 32:
        return False
    if not isinstance(audit_path, Sequence) or isinstance(audit_path, (bytes, bytearray, str)):
        return False
    if any(not isinstance(node, bytes) or len(node) != 32 for node in audit_path):
        return False
    fn, sn = leaf_index, tree_size - 1
    value = leaf_hash(entry)
    for sibling in audit_path:
        if sn == 0:
            return False
        if fn & 1 or fn == sn:
            value = node_hash(sibling, value)
            while fn and not fn & 1:
                fn >>= 1
                sn >>= 1
        else:
            value = node_hash(value, sibling)
        fn >>= 1
        sn >>= 1
    return sn == 0 and value == root
