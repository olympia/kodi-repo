#!/usr/bin/env python3
"""Build the general repository and the Kodi 21 Omega skin channel."""
import hashlib
from pathlib import Path
import re
import xml.etree.ElementTree as ET
import zipfile

REPO_ROOT = Path(__file__).resolve().parent
OMEGA_ADDONS = frozenset({'skin.confluence.olympia'})
EXCLUDED_DIRS = {'.git', '.github', '__pycache__'}


def get_addon_dirs():
    return sorted(p.name for p in REPO_ROOT.iterdir() if p.is_dir() and (p / 'addon.xml').is_file())


def generate_index(addons, directory):
    directory.mkdir(parents=True, exist_ok=True)
    parts = ['<?xml version="1.0" encoding="UTF-8"?>\n<addons>']
    for name in addons:
        text = (REPO_ROOT / name / 'addon.xml').read_text(encoding='utf-8').strip()
        ET.fromstring(text)
        text = re.sub(r'<\?xml[^?]*\?>', '', text).strip()
        parts.append('  ' + '\n  '.join(text.splitlines()))
    parts.append('</addons>')
    data = ('\n'.join(parts) + '\n').encode('utf-8')
    ET.fromstring(data)
    (directory / 'addons.xml').write_bytes(data)
    (directory / 'addons.xml.md5').write_text(hashlib.md5(data).hexdigest(), encoding='ascii')
    print(f'Index: {directory.relative_to(REPO_ROOT) or "."} ({len(addons)} addons)')


def package_addon(name):
    folder = REPO_ROOT / name
    version = ET.parse(folder / 'addon.xml').getroot().get('version')
    archive = folder / f'{name}-{version}.zip'
    files = {}
    for path in sorted(folder.rglob('*')):
        relative = path.relative_to(folder)
        if not path.is_file() or any(part in EXCLUDED_DIRS for part in relative.parts):
            continue
        if path.suffix.lower() in {'.zip', '.pyc', '.pyo', '.tmp', '.bak'}:
            continue
        files[name + '/' + relative.as_posix()] = path.read_bytes()
    # Preserve byte-identical existing archives; do not republish unrelated addons.
    if archive.exists():
        with zipfile.ZipFile(archive) as existing:
            if sorted(existing.namelist()) == sorted(files) and all(existing.read(k) == v for k, v in files.items()):
                print(f'Unchanged: {archive.name}')
                return
    temp = archive.with_suffix('.zip.tmp')
    with zipfile.ZipFile(temp, 'w', zipfile.ZIP_DEFLATED) as z:
        for name_in_zip, data in files.items():
            entry = zipfile.ZipInfo(name_in_zip, date_time=(1980, 1, 1, 0, 0, 0))
            entry.compress_type = zipfile.ZIP_DEFLATED
            entry.external_attr = 0o644 << 16
            z.writestr(entry, data)
    temp.replace(archive)
    # Previously released versions remain available for existing download links.
    print(f'Packaged: {archive.name}')


def main():
    addons = get_addon_dirs()
    if not addons:
        raise SystemExit('No addon sources found')
    generate_index([name for name in addons if name not in OMEGA_ADDONS], REPO_ROOT)
    generate_index([name for name in addons if name in OMEGA_ADDONS], REPO_ROOT / 'omega')
    for name in addons:
        package_addon(name)


if __name__ == '__main__':
    main()
