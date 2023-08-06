# Photocopier: Organize and De-duplicate Your Media

Photocopier is a Python script that organizes your images and videos by date and ensures you don't copy the same file twice. This is especially useful for large photo libraries where organization can get chaotic over time.

## 🌟 Features

- **Organization by Date**: Rearranges your media into folders by year and month.
- **De-duplication**: Uses MD5 hashing to avoid copying the same media file twice.
- **Stock Take**: A mode to get a quick overview of the extensions and the number of files in the source directory.
- **Logging**: Detailed logging to provide insight into the process.

## 🔧 Prerequisites

- Python 3.6 or higher
- Required Python libraries: `pyexifinfo`, `click`, `hashlib`, `os`, `shutil`, `datetime`

  Install them using:
  ```bash
  pip install click pyexifinfo
  ```

## 🚀 Usage

### Basic Organization

Copy and organize your images:
```bash
python photocopier.py /path/to/source /path/to/destination
```

### Stock Take Mode

For a stock take of extensions in the source directory:
```bash
python photocopier.py /path/to/source /path/to/destination -s
```

## 🛠 How It Works

1. **Stock Take (Optional)**: Analyzes the source directory to display the number of files and the file extensions.
2. **Load Existing Hashes**: Before organizing, the script checks a hash file (`copied_hashes.txt`) in the destination directory to see which files have been previously copied.
3. **Organization**: Each media file is read, its date is extracted (from metadata or the file's modification date), and it's copied into the appropriate year-month directory.
4. **Avoiding Duplicates**: Each media file's MD5 hash is calculated. If the hash exists in the hashes file, it's skipped; otherwise, it's copied to the destination and the hash is saved.

> 💡 **Note**: The `copied_hashes.txt` file is essential and should not be deleted. It resides in the destination directory and serves as a record of what's already been copied. Deleting this file would lose that record and may result in duplicates.

## 🖥️ Output

Whenever a hash exists, a dot (.) is printed to show that this file has been found in your library already. When a file is not found and copied across, a plus (+) is printed. The output can look something like this:

<img width="1507" alt="Screenshot 2023-08-06 at 22 17 29" src="https://github.com/dsmurrell/photocopier/assets/4035854/f48e991b-8883-4219-891b-6df9ec323d61">

## 🤝 Contributing

If you find any issues or have suggestions, feel free to open an issue or make a pull request.
