import hashlib
import os
import shutil
from datetime import datetime

import pyexifinfo as p

allowed_extensions_lower = {
    ".jpg",
    ".jpeg",
    ".png",
    ".gif",
    ".cr3",
    ".cr2",
    ".mp4",
    ".mov",
}


def is_image_file(file):
    _, file_extension = os.path.splitext(file)
    return file_extension.lower() in allowed_extensions_lower, file_extension.lower()


def get_photo_date(file_path):
    try:
        data = p.get_json(file_path)
        for d in data:
            if "EXIF:DateTimeOriginal" in d:
                date_str = d["EXIF:DateTimeOriginal"]
                return datetime.strptime(date_str, "%Y:%m:%d %H:%M:%S")
    except Exception as e:
        print(f"Error reading metadata from {file_path}: {e}")

    # Fall back to using the file's last modification date
    mod_timestamp = os.path.getmtime(file_path)
    return datetime.fromtimestamp(mod_timestamp)


def get_image_sha_256_hash(file_path):
    try:
        with open(file_path, "rb") as file:
            return hashlib.sha256(file.read()).hexdigest()
    except Exception as e:
        print(f"Error calculating image hash for {file_path}: {e}")
    return None


def get_image_md5_hash(file_path):
    try:
        with open(file_path, "rb") as file:
            return hashlib.md5(file.read()).hexdigest()
    except Exception as e:
        print(f"Error calculating image hash for {file_path}: {e}")
    return None


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
                seen_hashes.add(line.strip())
    return seen_hashes


def save_hash(hashes_file, img_hash):
    with open(hashes_file, "a") as f:
        f.write(f"{img_hash}\n")


extensions = set()


def organize_by_date(src_dir, dest_dir, hashes_file, get_extensions_only=False):
    seen_hashes = load_hashes(hashes_file)
    print(f"Seen {len(seen_hashes)} hashes")
    if not os.path.exists(dest_dir):
        os.makedirs(dest_dir)

    for root, _, files in os.walk(src_dir):
        for file in files:
            is_image, extension = is_image_file(file)
            if extension not in extensions:
                extensions.add(extension)
            if get_extensions_only:
                continue

            if is_image:
                src_file_path = os.path.join(root, file)
                img_hash = get_image_md5_hash(src_file_path)
                if img_hash is None or img_hash in seen_hashes:
                    print(".", end="", flush=True)
                    continue

                photo_date = get_photo_date(src_file_path)
                if photo_date:
                    print("+", end="", flush=True)
                    # dest_folder = os.path.join(dest_dir, photo_date.strftime("%Y-%m"))
                    dest_folder = os.path.join(
                        dest_dir, extension[1:].upper(), photo_date.strftime("%Y-%m")
                    )
                    if not os.path.exists(dest_folder):
                        os.makedirs(dest_folder)

                    dest_file_path = os.path.join(
                        dest_folder,
                        photo_date.strftime("%Y-%m-%d_%H-%M-%S") + "_" + file,
                    )
                    dest_file_path = get_unique_filepath(dest_file_path)
                    try:
                        shutil.copy2(src_file_path, dest_file_path)
                        seen_hashes.add(img_hash)
                        save_hash(hashes_file, img_hash)
                    except Exception as e:
                        print(
                            f"Error copying file {src_file_path} to {dest_file_path}: {e}"
                        )


# src_dir = "/Users/getafix/Pictures/R6"
src_dir = "/Volumes/6TB2/Pictures from osx"
dest_dir = "/Volumes/6TB2/photocopied"

hashes_file = os.path.join(dest_dir, "copied_hashes.txt")
organize_by_date(src_dir, dest_dir, hashes_file, False)

print(extensions)
