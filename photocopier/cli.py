"""Photocopier CLI: copy, verify, and stock commands."""

import logging
import os
import sys

import click

from photocopier import __version__
from photocopier.core import (
    HASHES_FILENAME,
    CopyStats,
    build_dest_hash_set,
    copy_one,
    list_media_files,
    load_hashes,
    sweep_partial_files,
    take_stock,
    verify_files,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


@click.group()
@click.version_option(version=__version__)
def main():
    """Photocopier: back up photos and videos to external drives, organised
    by date, de-duplicated, and verified."""


@main.command()
@click.argument("src_dir", type=click.Path(exists=True, file_okay=False))
@click.argument("dest_dir", type=click.Path(file_okay=False))
@click.option("--dry-run", is_flag=True, help="Show what would be copied without copying anything.")
def copy(src_dir, dest_dir, dry_run):
    """Copy media from SRC_DIR into DEST_DIR, organised by date.

    Every file is verified after copying (the destination bytes are re-hashed
    and compared to the source) before it is recorded as done. Duplicates —
    files whose content was copied before — are skipped.
    """
    if not dry_run:
        os.makedirs(dest_dir, exist_ok=True)
        removed = sweep_partial_files(dest_dir)
        if removed:
            click.echo(f"Cleaned up {len(removed)} partial file(s) from an interrupted run.")

    hashes_file = os.path.join(dest_dir, HASHES_FILENAME)
    seen_hashes = load_hashes(hashes_file)
    click.echo(f"Loaded {len(seen_hashes)} previously copied hashes.")

    click.echo("Scanning for media files…")
    media_files = list_media_files(src_dir)
    click.echo(f"Found {len(media_files)} media files in {src_dir}")

    stats = CopyStats()

    def process_all(hashes_f):
        with click.progressbar(media_files, label="Copying", show_pos=True) as bar:
            for src_file_path in bar:
                copy_one(src_file_path, dest_dir, seen_hashes, hashes_f, stats, dry_run=dry_run)

    if dry_run:

        class _NullFile:
            def write(self, _):
                pass

            def flush(self):
                pass

        process_all(_NullFile())
    else:
        with open(hashes_file, "a") as hashes_f:
            process_all(hashes_f)

    click.echo("")
    if dry_run:
        click.echo(f"Dry run: {stats.would_copy} file(s) would be copied, {stats.duplicates} duplicate(s) skipped, {stats.errors} unreadable.")
    else:
        gb = stats.bytes_copied / (1024**3)
        click.echo(f"Copied {stats.copied} file(s) ({gb:.2f} GB). Skipped {stats.duplicates} duplicate(s). Errors: {stats.errors}.")
    if stats.error_files:
        click.echo("\nFiles that FAILED (not backed up — do not delete these from the source):")
        for path in stats.error_files:
            click.echo(f"  {path}")
        sys.exit(1)


@main.command()
@click.argument("src_dir", type=click.Path(exists=True, file_okay=False))
@click.argument("dest_dir", type=click.Path(exists=True, file_okay=False))
@click.option(
    "--deep",
    is_flag=True,
    help="Re-hash every file in DEST_DIR instead of trusting its hash record. Slower, but detects corrupted copies.",
)
def verify(src_dir, dest_dir, deep):
    """Check that every media file in SRC_DIR exists in DEST_DIR.

    Exit code 0 means everything in SRC_DIR is present in DEST_DIR — it is
    safe to delete the source. Fast mode trusts DEST_DIR's copied_hashes.txt;
    --deep re-reads every destination file, so it also catches files that were
    corrupted on the destination drive after copying.

    Tip: to audit two backup drives against each other, run
    `photocopier verify --deep DRIVE_A DRIVE_B` and then again with the
    arguments swapped.
    """
    click.echo("Scanning source for media files…")
    src_files = list_media_files(src_dir)
    click.echo(f"Found {len(src_files)} media files in {src_dir}")

    if deep:
        dest_files = list_media_files(dest_dir)
        click.echo(f"Deep mode: hashing {len(dest_files)} files in {dest_dir}…")
        with click.progressbar(length=len(dest_files), label="Hashing destination") as bar:
            dest_hashes = build_dest_hash_set(dest_dir, progress=lambda: bar.update(1))
    else:
        hashes_file = os.path.join(dest_dir, HASHES_FILENAME)
        if not os.path.exists(hashes_file):
            click.echo(f"No {HASHES_FILENAME} in {dest_dir} — use --deep to verify against the actual files.")
            sys.exit(2)
        dest_hashes = load_hashes(hashes_file)
        click.echo(f"Loaded {len(dest_hashes)} hashes from {hashes_file}")

    with click.progressbar(length=len(src_files), label="Verifying source") as bar:
        result = verify_files(src_files, dest_hashes, progress=lambda: bar.update(1))

    click.echo("")
    click.echo(f"Checked {result.checked} file(s): {result.present} present, {len(result.missing)} missing, {len(result.unreadable)} unreadable.")

    if result.missing:
        click.echo("\nMISSING from destination (do NOT delete these from the source):")
        for path in result.missing:
            click.echo(f"  {path}")
    if result.unreadable:
        click.echo("\nUNREADABLE source files (check these manually):")
        for path in result.unreadable:
            click.echo(f"  {path}")

    if result.missing or result.unreadable:
        sys.exit(1)
    click.echo("\n✓ Everything in the source is present in the destination.")


@main.command()
@click.argument("src_dir", type=click.Path(exists=True, file_okay=False))
def stock(src_dir):
    """Report file counts and any extensions photocopier would skip."""
    count, media_count, other_extensions = take_stock(src_dir)
    click.echo(f"Found {count} files, of which {media_count} are recognised media files.")
    skipped = count - media_count
    if skipped:
        click.echo(f"{skipped} file(s) would be skipped, with these extensions:")
        click.echo(f"  {sorted(e if e else '(no extension)' for e in other_extensions)}")
        click.echo("If any of these contain photos you care about (e.g. .zip archives), handle them separately.")
    else:
        click.echo("Everything here is recognised media.")


if __name__ == "__main__":
    main()
