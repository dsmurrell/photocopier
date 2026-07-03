# Photocopier

**Back up your photos and videos to external drives — organised by date, de-duplicated, and verified.**

Photocopier copies your media onto a backup drive into a tidy `TYPE/YYYY-MM/` structure,
never copies the same photo twice (even across runs and messy source folders), verifies
every copy byte-for-byte before trusting it, and can prove to you that everything made it
before you delete the originals.

```
dest/
├── JPG/
│   ├── 2024-05/2024-05-14_18-32-01_IMG_2041.jpg
│   └── 2024-06/…
├── HEIC/2024-06/…
├── CR3/2024-06/…
└── MP4/2024-06/…
```

## Install

Requires Python 3.10+ and [exiftool](https://exiftool.org) (for photo dates):

```bash
brew install exiftool pipx     # macOS
pipx install photocopier
```

## Usage

### 1. See what you have

```bash
photocopier stock ~/Pictures
```

Reports how many files photocopier recognises as media, and lists any extensions it
would skip (check those for anything you care about, e.g. `.zip` archives of photos).

### 2. Back up

```bash
photocopier copy ~/Pictures /Volumes/MyBackupDrive/photos
```

- Files are organised by the date the photo was taken (EXIF), falling back to the
  file's modification date.
- Duplicate content is skipped — a record of everything ever copied lives in
  `copied_hashes.txt` inside the destination. Don't delete that file.
- Every copy is **verified**: the destination bytes are re-read and compared to the
  source before the file is recorded as done.
- Interrupted runs (unplugged drive, Ctrl-C) are safe: in-flight files are cleaned up
  and re-copied next time.
- Add `--dry-run` to preview what would be copied without writing anything.

Run it again any time — already-copied files are skipped, so incremental backups
are fast and safe.

### 3. Verify before deleting anything

```bash
photocopier verify ~/Pictures /Volumes/MyBackupDrive/photos
```

Exit code 0 means every media file in the source is present in the destination — it is
safe to delete the source. Any missing or unreadable files are listed explicitly.

For a paranoid check that re-reads every file on the destination drive (catching files
that were corrupted *after* they were copied):

```bash
photocopier verify --deep ~/Pictures /Volumes/MyBackupDrive/photos
```

**Auditing two backup drives against each other** (recommended if you keep two copies):

```bash
photocopier verify --deep /Volumes/DriveA/photos /Volumes/DriveB/photos
photocopier verify --deep /Volumes/DriveB/photos /Volumes/DriveA/photos
```

Both exiting 0 means the two archives hold identical content.

## Supported formats

Photos: jpg, jpeg, png, gif, heic, heif, webp, avif, tif, tiff, bmp
RAW: cr2, cr3, dng, nef, arw, orf, raf, rw2
Video: mp4, mov, m4v, mkv, avi, mpg, mpeg, 3gp, 3g2, mts, m2ts, vob, flv, wmv, webm

## How de-duplication works

Each file's content is hashed (MD5, read in chunks). Hashes of everything ever copied
are stored in `copied_hashes.txt` in the destination. A file whose content hash is
already recorded is skipped, regardless of its name or folder — so re-organising your
source folders never causes duplicate copies.

> The hash algorithm is MD5 for continuity with existing archives; it's used for
> de-duplication, not security.

## Development

```bash
git clone https://github.com/dsmurrell/photocopier
cd photocopier
python -m venv .venv && ./.venv/bin/pip install -e ".[dev]"
./.venv/bin/pytest
```

## License

MIT
