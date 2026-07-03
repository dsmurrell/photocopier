#!/bin/bash

# Exit on error
set -e

# NB: Make sure you bump the version in photocopier/__init__.py first

PY=./.venv/bin/python

# Lint + tests
echo "🔎 Linting..."
$PY -m ruff check photocopier tests

echo "🧪 Running tests..."
$PY -m pytest -q

# Clean previous builds
echo "🧹 Cleaning previous builds..."
rm -rf dist/ build/ *.egg-info/

# Build the package
echo "📦 Building package..."
$PY -m build

# Sanity-check metadata
$PY -m twine check dist/*

# Upload to PyPI
echo "🚀 Uploading to PyPI..."
$PY -m twine upload dist/*

echo "✅ Done!"
