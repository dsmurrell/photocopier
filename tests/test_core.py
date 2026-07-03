"""Tests for photocopier.core — pure logic, no exiftool needed.

EXIF lookup falls back to file mtime when pyexifinfo/exiftool are unavailable
or the file has no EXIF, so tests use plain files with controlled mtimes.
"""

import os
import time

import pytest

from photocopier.core import (
    CopyStats,
    build_dest_hash_set,
    copy_one,
    dest_path_for,
    get_photo_date,
    get_unique_filepath,
    hash_file,
    is_media_file,
    list_media_files,
    load_hashes,
    safe_copy,
    sweep_partial_files,
    take_stock,
    verify_files,
)


def make_file(path, content=b"hello"):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        f.write(content)
    return path


class TestBasics:
    def test_is_media_file(self):
        assert is_media_file("a.JPG")
        assert is_media_file("b.heic")
        assert is_media_file("c.NEF")
        assert not is_media_file("d.txt")
        assert not is_media_file("e.zip")

    def test_hash_file(self, tmp_path):
        p = make_file(str(tmp_path / "a.jpg"), b"content")
        assert hash_file(p) == hash_file(p)
        q = make_file(str(tmp_path / "b.jpg"), b"different")
        assert hash_file(p) != hash_file(q)

    def test_hash_file_unreadable(self, tmp_path):
        assert hash_file(str(tmp_path / "missing.jpg")) is None

    def test_unique_filepath(self, tmp_path):
        p = make_file(str(tmp_path / "x.jpg"))
        assert get_unique_filepath(p) == str(tmp_path / "x_1.jpg")
        make_file(str(tmp_path / "x_1.jpg"))
        assert get_unique_filepath(p) == str(tmp_path / "x_2.jpg")

    def test_load_hashes_skips_blank_lines(self, tmp_path):
        hf = tmp_path / "copied_hashes.txt"
        hf.write_text("abc\n\ndef\n")
        assert load_hashes(str(hf)) == {"abc", "def"}

    def test_photo_date_falls_back_to_mtime(self, tmp_path):
        p = make_file(str(tmp_path / "a.jpg"))
        mtime = time.mktime((2021, 6, 15, 12, 0, 0, 0, 0, -1))
        os.utime(p, (mtime, mtime))
        d = get_photo_date(p)
        assert (d.year, d.month, d.day) == (2021, 6, 15)

    def test_dest_path_layout(self, tmp_path):
        p = make_file(str(tmp_path / "IMG_1.jpg"))
        mtime = time.mktime((2021, 6, 15, 12, 30, 45, 0, 0, -1))
        os.utime(p, (mtime, mtime))
        dest = dest_path_for(str(tmp_path / "out"), p, get_photo_date(p))
        assert dest == str(tmp_path / "out" / "JPG" / "2021-06" / "2021-06-15_12-30-45_IMG_1.jpg")


class TestSafeCopy:
    def test_copies_and_verifies(self, tmp_path):
        src = make_file(str(tmp_path / "src" / "a.jpg"), b"payload")
        dest = str(tmp_path / "dest" / "a.jpg")
        os.makedirs(os.path.dirname(dest))
        safe_copy(src, dest, hash_file(src))
        assert open(dest, "rb").read() == b"payload"
        assert not os.path.exists(dest + ".part")

    def test_bad_hash_leaves_nothing(self, tmp_path):
        src = make_file(str(tmp_path / "src" / "a.jpg"), b"payload")
        dest = str(tmp_path / "dest" / "a.jpg")
        os.makedirs(os.path.dirname(dest))
        with pytest.raises(IOError):
            safe_copy(src, dest, "not-the-right-hash")
        assert not os.path.exists(dest)
        assert not os.path.exists(dest + ".part")

    def test_sweep_partial_files(self, tmp_path):
        part = make_file(str(tmp_path / "JPG" / "2021-06" / "x.jpg.part"))
        keep = make_file(str(tmp_path / "JPG" / "2021-06" / "y.jpg"))
        removed = sweep_partial_files(str(tmp_path))
        assert removed == [part]
        assert os.path.exists(keep)


class TestCopyOne:
    def run_copy(self, tmp_path, files, dry_run=False):
        src_dir = tmp_path / "src"
        dest_dir = tmp_path / "dest"
        os.makedirs(dest_dir, exist_ok=True)
        for name, content in files.items():
            make_file(str(src_dir / name), content)
        stats = CopyStats()
        seen = set()
        hashes_path = str(dest_dir / "copied_hashes.txt")
        with open(hashes_path, "a") as f:
            for path in list_media_files(str(src_dir)):
                copy_one(path, str(dest_dir), seen, f, stats, dry_run=dry_run)
        return stats, str(dest_dir), hashes_path

    def test_copies_new_files_and_records_hashes(self, tmp_path):
        stats, dest_dir, hashes_path = self.run_copy(tmp_path, {"a.jpg": b"one", "b.png": b"two"})
        assert stats.copied == 2
        assert stats.duplicates == 0
        assert len(load_hashes(hashes_path)) == 2
        assert len(list_media_files(dest_dir)) == 2

    def test_skips_duplicate_content(self, tmp_path):
        stats, dest_dir, _ = self.run_copy(tmp_path, {"a.jpg": b"same", "copy_of_a.jpg": b"same"})
        assert stats.copied == 1
        assert stats.duplicates == 1
        assert len(list_media_files(dest_dir)) == 1

    def test_dry_run_copies_nothing(self, tmp_path):
        stats, dest_dir, hashes_path = self.run_copy(tmp_path, {"a.jpg": b"one"}, dry_run=True)
        assert stats.would_copy == 1
        assert list_media_files(dest_dir) == []
        assert load_hashes(hashes_path) == set()

    def test_rerun_skips_already_copied(self, tmp_path):
        stats1, dest_dir, hashes_path = self.run_copy(tmp_path, {"a.jpg": b"one"})
        assert stats1.copied == 1
        # Second run against the same dest: reload hashes like the CLI does
        stats2 = CopyStats()
        seen = load_hashes(hashes_path)
        with open(hashes_path, "a") as f:
            for path in list_media_files(str(tmp_path / "src")):
                copy_one(path, dest_dir, seen, f, stats2, dry_run=False)
        assert stats2.copied == 0
        assert stats2.duplicates == 1


class TestVerify:
    def test_all_present(self, tmp_path):
        src = make_file(str(tmp_path / "src" / "a.jpg"), b"one")
        dest_hashes = {hash_file(src)}
        result = verify_files([src], dest_hashes)
        assert result.present == 1
        assert result.missing == []

    def test_missing_detected(self, tmp_path):
        src = make_file(str(tmp_path / "src" / "a.jpg"), b"one")
        result = verify_files([src], set())
        assert result.missing == [src]

    def test_deep_dest_hashing_catches_corruption(self, tmp_path):
        # Source file and a CORRUPTED destination copy with a stale hash record
        src = make_file(str(tmp_path / "src" / "a.jpg"), b"good bytes")
        make_file(str(tmp_path / "dest" / "JPG" / "2021-06" / "a.jpg"), b"corrupted!")
        dest_hashes = build_dest_hash_set(str(tmp_path / "dest"))
        result = verify_files([src], dest_hashes)
        # Deep mode sees the corruption: source hash not present on the drive
        assert result.missing == [src]


class TestStock:
    def test_counts_and_other_extensions(self, tmp_path):
        make_file(str(tmp_path / "a.jpg"))
        make_file(str(tmp_path / "b.heic"))
        make_file(str(tmp_path / "c.zip"))
        count, media_count, other = take_stock(str(tmp_path))
        assert count == 3
        assert media_count == 2
        assert other == {".zip"}
