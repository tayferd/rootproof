"""SHA-256 over exact file bytes, read in bounded chunks."""

import hashlib
import os
from pathlib import Path
import stat


def hash_file(path: Path) -> str:
    if not path.is_file():
        raise ValueError("Choose an existing regular file")
    digest = hashlib.sha256()
    with path.open("rb") as source:
        before = os.fstat(source.fileno())
        if not stat.S_ISREG(before.st_mode):
            raise ValueError("Choose a regular file")
        for chunk in iter(lambda: source.read(64 * 1024), b""):
            digest.update(chunk)
        after = os.fstat(source.fileno())
    if (before.st_size, before.st_mtime_ns, before.st_ctime_ns) != (
        after.st_size, after.st_mtime_ns, after.st_ctime_ns
    ):
        raise ValueError("File changed while being read; retry with a saved, stable file")
    return digest.hexdigest()
