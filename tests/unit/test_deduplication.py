import tempfile
from pathlib import Path

from ragcore.ingestion.deduplication import compute_hash


def test_hash_is_deterministic(tmp_path):
    f = tmp_path / "doc.txt"
    f.write_bytes(b"hello world")
    assert compute_hash(f) == compute_hash(f)


def test_different_content_different_hash(tmp_path):
    f1 = tmp_path / "a.txt"
    f2 = tmp_path / "b.txt"
    f1.write_bytes(b"content a")
    f2.write_bytes(b"content b")
    assert compute_hash(f1) != compute_hash(f2)


def test_hash_length_is_64():
    with tempfile.NamedTemporaryFile(delete=False, suffix=".txt") as tf:
        tf.write(b"test")
        path = Path(tf.name)
    assert len(compute_hash(path)) == 64
