#!/usr/bin/env python3
"""
Kodi Repository Generator
==========================
Scans subdirectories for addon.xml files, then:
  1. Builds a combined addons.xml
  2. Generates addons.xml.md5
  3. Creates versioned zip packages for each addon

Usage:
    python _generator.py

Run this from the repo root before every git push.
"""

import hashlib
import os
import re
import sys
import zipfile
from xml.etree import ElementTree as ET

REPO_ROOT = os.path.dirname(os.path.abspath(__file__))

# Directories / files to exclude from zip packages
ZIP_EXCLUDES = {
    ".git",
    ".github",
    "__pycache__",
    ".gitignore",
    "_generator.py",
    "addons.xml",
    "addons.xml.md5",
    "README.md",
}


def get_addon_dirs():
    """Return a sorted list of directories that contain an addon.xml."""
    dirs = []
    for name in sorted(os.listdir(REPO_ROOT)):
        path = os.path.join(REPO_ROOT, name)
        if os.path.isdir(path) and os.path.isfile(os.path.join(path, "addon.xml")):
            dirs.append(name)
    return dirs


def read_addon_xml(addon_dir):
    """Read and return the raw XML text of an addon.xml, stripped of the
    <?xml …?> declaration so it can be embedded in the combined file."""
    path = os.path.join(REPO_ROOT, addon_dir, "addon.xml")
    with open(path, "r", encoding="utf-8") as f:
        content = f.read().strip()
    # Remove XML declaration if present
    content = re.sub(r"<\?xml[^?]*\?>", "", content).strip()
    return content


def get_addon_version(addon_dir):
    """Parse the version attribute from an addon's addon.xml."""
    path = os.path.join(REPO_ROOT, addon_dir, "addon.xml")
    tree = ET.parse(path)
    return tree.getroot().attrib["version"]


def generate_addons_xml(addon_dirs):
    """Generate the combined addons.xml from all discovered addons."""
    parts = ['<?xml version="1.0" encoding="UTF-8"?>\n<addons>']
    for addon_dir in addon_dirs:
        xml_text = read_addon_xml(addon_dir)
        parts.append("  " + "\n  ".join(xml_text.splitlines()))
    parts.append("</addons>")

    combined = "\n".join(parts) + "\n"
    out_path = os.path.join(REPO_ROOT, "addons.xml")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(combined)
    print(f"  [OK] addons.xml ({len(addon_dirs)} addon(s))")
    return combined


def generate_md5(addons_xml_content):
    """Generate addons.xml.md5 checksum file."""
    md5 = hashlib.md5(addons_xml_content.encode("utf-8")).hexdigest()
    out_path = os.path.join(REPO_ROOT, "addons.xml.md5")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(md5)
    print(f"  [OK] addons.xml.md5 ({md5})")


def generate_zip(addon_dir):
    """Create a versioned zip for an addon.
    The zip is placed at: <addon_dir>/<addon_dir>-<version>.zip
    Inside the zip the root folder is the addon_dir name."""
    version = get_addon_version(addon_dir)
    zip_name = f"{addon_dir}-{version}.zip"
    zip_path = os.path.join(REPO_ROOT, addon_dir, zip_name)

    # Remove old zips for this addon
    addon_path = os.path.join(REPO_ROOT, addon_dir)
    for existing in os.listdir(addon_path):
        if existing.endswith(".zip"):
            os.remove(os.path.join(addon_path, existing))

    # Build the zip
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(addon_path):
            # Skip excluded dirs
            dirs[:] = [d for d in dirs if d not in ZIP_EXCLUDES]
            for filename in files:
                if filename.endswith(".zip"):
                    continue
                filepath = os.path.join(root, filename)
                arcname = os.path.relpath(filepath, os.path.join(addon_path, ".."))
                zf.write(filepath, arcname)

    print(f"  [OK] {addon_dir}/{zip_name}")


def main():
    print("Kodi Repository Generator")
    print("=" * 40)

    addon_dirs = get_addon_dirs()
    if not addon_dirs:
        print("  [!] No addon directories found.")
        sys.exit(1)

    print(f"\nFound addons: {', '.join(addon_dirs)}\n")

    print("Generating addons.xml ...")
    content = generate_addons_xml(addon_dirs)

    print("Generating checksum ...")
    generate_md5(content)

    print("Creating zip packages ...")
    for addon_dir in addon_dirs:
        generate_zip(addon_dir)

    print(f"\nDone! Push to GitHub and the repo is live at:")
    print(f"  https://olympia.github.io/kodi-repo/")


if __name__ == "__main__":
    main()
