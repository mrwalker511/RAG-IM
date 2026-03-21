import hashlib
from pathlib import Path


def compute_hash(path: Path) -> str:
    """Return SHA-256 hex digest of a file's raw bytes."""
    sha = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            sha.update(chunk)
    return sha.hexdigest()
