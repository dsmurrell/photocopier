# Improvement Plan — photocopier

A 172-line Python CLI that organises photos/videos by date into `EXT/YYYY-MM/` folders with
MD5 de-duplication. Daniel's workflow: back up pictures onto two external drives before
deleting them from the laptop. Goal of this plan: (a) harden the core for that
delete-after-backup workflow, (b) package it so a regular person can install it,
(c) give it a runnem.com-style marketing/docs site (deploy URL assumed available).

## Part A — Core improvements (ordered by importance)

### 🔴 Data-integrity (this tool justifies deleting originals — these matter)

1. **Verify after copy.** `shutil.copy2` is trusted blindly today. Re-hash the destination
   file after copying and compare to the source hash before recording it as done. Catches
   silent corruption on flaky USB drives — precisely the failure mode external-drive
   backups suffer.
2. **Crash-safe copies.** If a copy is interrupted (drive unplugged, Ctrl-C), a partial
   file is left at the destination *without* its hash recorded → next run copies again to a
   `_1`-suffixed name, leaving a corrupt orphan alongside the good copy. Fix: copy to
   `name.part`, fsync, then atomically rename; on startup optionally sweep `*.part` files.
3. **`verify` command for the two-drive workflow.** Before deleting from the laptop,
   Daniel wants confidence both drives hold everything:
   `photocopier verify SRC DEST` — re-walk SRC, hash every media file, report any hash
   missing from DEST's `copied_hashes.txt` (or optionally re-hash DEST files themselves
   for a paranoid `--deep` mode). Exit code 0 = safe to delete. This is the single feature
   most aligned with how the tool is actually used.
   **Also: the one-time drive-vs-drive audit.** Because past copies were never verified,
   run `photocopier verify --deep DRIVE_A DRIVE_B` (and swapped) once after this ships:
   hash every file on each drive and confirm the two archives hold identical content
   hashes. Any silently-corrupted file on one drive will surface and can be re-copied
   from the other. This converts "very unlikely anything was lost" into "checked".
4. **A `--dry-run` flag** — show what would be copied where, copy nothing.

### 🟠 Coverage & correctness

5. **Missing formats a regular person has:** `.heic`/`.heif` (default iPhone format since
   2017!), `.webp`, `.avif`, `.dng`, `.nef` (Nikon), `.arw` (Sony), `.orf` (Olympus),
   `.raf` (Fuji), `.rw2` (Panasonic), `.tif/.tiff`, `.bmp`, `.webm`. HEIC alone makes the
   current tool near-useless for iPhone users.
6. **EXIF speed.** `pyexifinfo` spawns an `exiftool` process *per file* — on a 50k-photo
   library that's 50k process launches (hours). Options: exiftool's `-stay_open` batch
   mode via a small wrapper, or Pillow+`piexif` for JPEG/PNG/HEIC with exiftool fallback
   for RAW/video. 10–50× faster scans.
7. **Faster re-runs.** Every re-run re-hashes every source file even if it was copied last
   time. Add a source-side cache keyed on `(path, size, mtime) → hash` so unchanged files
   skip hashing. Turns a nightly re-run over a big library from hours into seconds.
8. **Use SHA-256 (or BLAKE2b) instead of MD5** — same cost with BLAKE2b, removes the
   "but MD5 collisions" conversation entirely; migrate old hash files by rehashing on a
   one-time `migrate` command (or keep supporting md5 lines side by side).
9. **Hash in chunks.** `file.read()` loads whole videos into RAM — a 20GB .mts file will
   hurt. Read in 1MB chunks.

### 🟡 UX

10. **Progress + summary.** Replace `.`/`+` dots with a progress bar (files done/total,
    MB/s) and end with a summary: N copied, N duplicates skipped, N errors, total size.
11. **Proper CLI shape**: subcommands `copy`, `verify`, `stock`, with `--help` examples.
    `dest_dir` is currently required even for stock-take (it's ignored) — fix.
12. **Live Photo awareness** (nice-to-have): keep `IMG_1234.HEIC` + `IMG_1234.mov` pairs
    together in the photo's folder rather than splitting HEIC/ and MOV/ trees.

## Part B — Packaging (make it installable by a human)

13. **Package it like runnem**: proper `pyproject.toml` with `[project]` metadata and a
    `photocopier` console-script entry point; publish to PyPI (reuse runnem's
    `build_and_upload.sh` pattern). Install story becomes: `pipx install photocopier`.
14. **Bundle the exiftool problem away** — either document `brew install exiftool` per
    platform, or prefer the pure-Python EXIF path (item 6) so exiftool is optional.
15. **Repo hygiene**: `copy_log.txt` (235KB) and `logs/` are sitting untracked in the repo
    dir — add to .gitignore; delete `old/` and `venv/` from disk; refresh README to match
    the new CLI; add a LICENSE (MIT) — required for people to actually use it.
16. **Tests + CI**: pytest for hashing/dedup/unique-path/date-fallback logic with tmp dirs
    (it's very testable), GitHub Actions on push. This repo has none.

## Part C — Marketing site (the runnem.com treatment)

Reuse the exact stack that worked for runnem: **Tailwind "Syntax" docs template**
(Next.js + Markdoc) — copy `runnem/runnem-docs` as the starting skeleton, restyle. Static
export → Amplify at the assumed URL.

Structure aimed at a *regular everyday person*, not a developer:

- **Hero**: "Get your photos off your laptop — safely." Sub: "Photocopier copies your
  photos and videos onto external drives, organised by date, with no duplicates — and
  proves the copy is safe before you delete anything."
- **The problem** (3 cards): "Your laptop is full" / "Your photos are chaos across
  folders, phones and SD cards" / "You don't trust yourself to delete anything"
- **How it works** (4 steps with real terminal output): install → plug in your drive →
  one command → verify, then delete with confidence
- **What you end up with**: a visual of the `JPG/2024-06/2024-06-14_18-32-01_IMG_2041.jpg`
  folder tree — this structure sells itself
- **The safety story**: duplicates never copied twice; every file verified after copy;
  works drive-by-drive so you can keep two copies (mention the 3-2-1 backup rule simply)
- **Honest install section**: it's a command-line tool; show the 2 commands
  (`brew install pipx && pipx install photocopier`) with a 60-second copy-paste guide,
  plus a short screen recording/GIF
- **Docs pages** (Markdoc): install, first backup, verifying before deleting, restoring,
  FAQ (HEIC? Live Photos? "what if I unplug the drive?"), troubleshooting
- **SEO basics from day one**: sitemap, robots, OG image, JSON-LD SoftwareApplication —
  and a link from dsmurrell.com's projects page
- Footer: GitHub link, dsmurrell.com link, Flow Myna cross-link

## Suggested execution order

1. Part A items 1–4 (integrity + verify command) — the workflow Daniel already trusts gets
   actually trustworthy
2. Item 5 (HEIC etc.) + 9–11 (chunked hashing, progress, CLI shape)
3. Part B packaging + PyPI publish
4. Part C site (needs the pipx story from B to exist first)
5. Items 6–8 and 12 as follow-ups

See COLD_STORAGE_PLAN.md for the AWS Deep Archive exploration — deliberately kept separate.
