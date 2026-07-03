"""Core logic: hashing, dates, safe copying, and verification.

Hashing stays MD5 deliberately: existing archives hold years of MD5 entries in
copied_hashes.txt, and changing algorithm would make every past copy look new.
MD5 is fine for de-duplication (we are not defending against adversaries).
"""

import hashlib
import logging
import os
import shutil
from dataclasses import dataclass, field
from datetime import datetime

logger = logging.getLogger(__name__)

HASHES_FILENAME = "copied_hashes.txt"
PART_SUFFIX = ".part"
CHUNK_SIZE = 1024 * 1024  # 1MB

ALLOWED_EXTENSIONS = {
    # photos
    ".jpg",
    ".jpeg",
    ".png",
    ".gif",
    ".heic",
    ".heif",
    ".webp",
    ".avif",
    ".tif",
    ".tiff",
    ".bmp",
    # RAW
    ".cr3",
    ".cr2",
    ".dng",
    ".nef",
    ".arw",
    ".orf",
    ".raf",
    ".rw2",
    # video
    ".mp4",
    ".mov",
    ".m4v",
    ".mkv",
    ".avi",
    ".mpg",
    ".mpeg",
    ".3gp",
    ".3g2",
    ".mts",
    ".m2ts",
    ".vob",
    ".flv",
    ".wmv",
    ".webm",
}


def get_file_extension_lower(file):
    _, file_extension = os.path.splitext(file)
    return file_extension.lower()


def is_media_file(file):
    return get_file_extension_lower(file) in ALLOWED_EXTENSIONS


def hash_file(file_path):
    """MD5 of a file, read in chunks so large videos don't fill RAM.

    Returns None (and logs) if the file can't be read.
    """
    try:
        digest = hashlib.md5()
        with open(file_path, "rb") as f:
            while chunk := f.read(CHUNK_SIZE):
                digest.update(chunk)
        return digest.hexdigest()
    except Exception as e:
        logger.error(f"Error hashing {file_path}: {e}")
        return None


def get_photo_date(file_path):
    """Date taken from EXIF (via exiftool), falling back to file mtime."""
    try:
        import pyexifinfo as p

        data = p.get_json(file_path)
        for d in data:
            if "EXIF:DateTimeOriginal" in d:
                date_str = d["EXIF:DateTimeOriginal"]
                return datetime.strptime(date_str, "%Y:%m:%d %H:%M:%S")
    except Exception as e:
        logger.debug(f"No usable EXIF date for {file_path}: {e}")

    mod_timestamp = os.path.getmtime(file_path)
    return datetime.fromtimestamp(mod_timestamp)


def get_unique_filepath(dest_file_path):
    counter = 1
    file_name, file_extension = os.path.splitext(dest_file_path)
    while os.path.exists(dest_file_path):
        dest_file_path = f"{file_name}_{counter}{file_extension}"
        counter += 1
    return dest_file_path


def load_hashes(hashes_file):
    seen_hashes = set()
    if os.path.exists(hashes_file):
        with open(hashes_file, "r") as f:
            for line in f:
                line = line.strip()
                if line:
                    seen_hashes.add(line)
    return seen_hashes


def list_media_files(src_dir):
    """All media file paths under src_dir (sorted for stable ordering)."""
    media = []
    for root, _, files in os.walk(src_dir):
        for file in files:
            if is_media_file(file):
                media.append(os.path.join(root, file))
    media.sort()
    return media


def sweep_partial_files(dest_dir):
    """Remove leftover .part files from interrupted runs. Returns paths removed."""
    removed = []
    for root, _, files in os.walk(dest_dir):
        for file in files:
            if file.endswith(PART_SUFFIX):
                path = os.path.join(root, file)
                try:
                    os.remove(path)
                    removed.append(path)
                    logger.info(f"Removed partial file from interrupted run: {path}")
                except Exception as e:
                    logger.error(f"Could not remove partial file {path}: {e}")
    return removed


def dest_path_for(dest_dir, file_path, photo_date):
    """EXT/YYYY-MM/YYYY-MM-DD_HH-MM-SS_originalname layout (unchanged from v0)."""
    file = os.path.basename(file_path)
    extension = get_file_extension_lower(file)
    dest_folder = os.path.join(dest_dir, extension[1:].upper(), photo_date.strftime("%Y-%m"))
    return os.path.join(dest_folder, photo_date.strftime("%Y-%m-%d_%H-%M-%S") + "_" + file)


def safe_copy(src_file_path, dest_file_path, expected_hash):
    """Copy with crash-safety and verification.

    Copies to a .part file, verifies the destination bytes hash to
    expected_hash, then atomically renames into place. Raises on any failure
    (leaving no .part behind).
    """
    part_path = dest_file_path + PART_SUFFIX
    try:
        shutil.copy2(src_file_path, part_path)
        dest_hash = hash_file(part_path)
        if dest_hash != expected_hash:
            raise IOError(f"Verification failed after copy (source {expected_hash}, destination {dest_hash})")
        os.rename(part_path, dest_file_path)
    except BaseException:
        # Clean up the in-flight file on error or Ctrl-C, then re-raise
        try:
            if os.path.exists(part_path):
                os.remove(part_path)
        except Exception:
            pass
        raise


@dataclass
class CopyStats:
    copied: int = 0
    duplicates: int = 0
    errors: int = 0
    bytes_copied: int = 0
    would_copy: int = 0  # dry-run
    error_files: list = field(default_factory=list)


def copy_one(src_file_path, dest_dir, seen_hashes, hashes_f, stats, dry_run=False):
    """Process a single media file. Mutates seen_hashes and stats."""
    img_hash = hash_file(src_file_path)
    if img_hash is None:
        stats.errors += 1
        stats.error_files.append(src_file_path)
        return

    if img_hash in seen_hashes:
        stats.duplicates += 1
        return

    photo_date = get_photo_date(src_file_path)
    dest_file_path = get_unique_filepath(dest_path_for(dest_dir, src_file_path, photo_date))

    if dry_run:
        stats.would_copy += 1
        seen_hashes.add(img_hash)  # so intra-run duplicates still count as dups
        logger.info(f"[dry-run] would copy {src_file_path} -> {dest_file_path}")
        return

    os.makedirs(os.path.dirname(dest_file_path), exist_ok=True)
    try:
        safe_copy(src_file_path, dest_file_path, img_hash)
    except KeyboardInterrupt:
        raise
    except Exception as e:
        logger.error(f"Error copying {src_file_path} to {dest_file_path}: {e}")
        stats.errors += 1
        stats.error_files.append(src_file_path)
        return

    seen_hashes.add(img_hash)
    hashes_f.write(f"{img_hash}\n")
    hashes_f.flush()
    stats.copied += 1
    stats.bytes_copied += os.path.getsize(dest_file_path)


@dataclass
class VerifyResult:
    checked: int = 0
    present: int = 0
    missing: list = field(default_factory=list)
    unreadable: list = field(default_factory=list)


def build_dest_hash_set(dest_dir, progress=None):
    """Deep mode: hash every media file actually present in dest_dir."""
    hashes = set()
    for path in list_media_files(dest_dir):
        h = hash_file(path)
        if h:
            hashes.add(h)
        if progress:
            progress()
    return hashes


def verify_files(src_files, dest_hashes, progress=None):
    """Check that every source file's content hash is present in dest_hashes."""
    result = VerifyResult()
    for path in src_files:
        result.checked += 1
        h = hash_file(path)
        if h is None:
            result.unreadable.append(path)
        elif h in dest_hashes:
            result.present += 1
        else:
            result.missing.append(path)
        if progress:
            progress()
    return result


def take_stock(src_dir):
    """Counts by extension; returns (total_count, media_count, other_extensions)."""
    extensions = set()
    count = 0
    media_count = 0
    for root, _, files in os.walk(src_dir):
        for file in files:
            extension = get_file_extension_lower(file)
            extensions.add(extension)
            count += 1
            if extension in ALLOWED_EXTENSIONS:
                media_count += 1
    return count, media_count, extensions - ALLOWED_EXTENSIONS
