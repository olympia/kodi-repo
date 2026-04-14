# -*- coding: UTF-8 -*-
#
# Copyright (C) 2024, Team Kodi
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# IMDb dataset approach based on "Light IMDb Ratings Update" by axlt2002

"""
Downloads the IMDb title.ratings.tsv.gz dataset file, imports it into a local
SQLite database, and provides fast lookups by IMDb ID (tconst).

The DB lives at:
  ~/.kodi/userdata/addon_data/metadata.universal.python/imdb_ratings.db
"""

import gzip
import io
import os
import sqlite3
import time

try:
    from urllib.request import Request, urlopen
    from urllib.error import URLError
except ImportError:
    from urllib2 import Request, urlopen, URLError

try:
    import xbmc
    import xbmcvfs
    import xbmcaddon
except ModuleNotFoundError:
    xbmc = None
    xbmcvfs = None
    xbmcaddon = None

DATASET_BASE_URL = 'https://datasets.imdbws.com/'
RATINGS_FILE = 'title.ratings.tsv.gz'

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                  '(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept-Encoding': 'identity',
}

# How many rows to INSERT in a single transaction batch
BATCH_SIZE = 25000


def _log(msg, level=None):
    if xbmc:
        if level is None:
            level = xbmc.LOGDEBUG
        xbmc.log('[metadata.universal.python] IMDb dataset: {}'.format(msg), level)


def _get_profile_path():
    """Return the addon profile directory path."""
    if xbmcaddon:
        addon = xbmcaddon.Addon('metadata.universal.python')
        profile = addon.getAddonInfo('profile')
        profile_path = xbmcvfs.translatePath(profile)
    else:
        profile_path = os.path.join(os.path.expanduser('~'), '.kodi',
                                     'userdata', 'addon_data',
                                     'metadata.universal.python')
    if not os.path.exists(profile_path):
        os.makedirs(profile_path)
    return profile_path


def _get_ratings_db_path():
    """Return the path to the ratings SQLite database file."""
    return os.path.join(_get_profile_path(), 'imdb_ratings.db')


def _get_ratings_connection():
    """Open (or create) the ratings SQLite database."""
    db_path = _get_ratings_db_path()
    conn = sqlite3.connect(db_path)
    conn.execute('PRAGMA journal_mode=WAL')
    conn.execute('PRAGMA synchronous=NORMAL')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS ratings (
            tconst TEXT PRIMARY KEY,
            averageRating REAL,
            numVotes INTEGER
        )
    ''')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS metadata (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    ''')
    conn.commit()
    return conn


def _stream_download_and_import_ratings(conn, progress_callback=None):
    """Download title.ratings.tsv.gz and import row-by-row using streaming
    decompression to minimize memory usage on low-RAM devices."""
    url = DATASET_BASE_URL + RATINGS_FILE
    _log('Downloading ratings from {}'.format(url), xbmc.LOGINFO if xbmc else None)
    req = Request(url, headers=HEADERS)

    try:
        response = urlopen(req, timeout=120)
    except (URLError, Exception) as e:
        _log('Download failed: {}'.format(e), xbmc.LOGWARNING if xbmc else None)
        return False

    # Read compressed data in chunks and decompress via GzipFile
    # This avoids holding the entire decompressed TSV (~20MB) in memory at once
    compressed_buf = io.BytesIO()
    chunk_size = 256 * 1024  # 256KB chunks
    while True:
        chunk = response.read(chunk_size)
        if not chunk:
            break
        compressed_buf.write(chunk)

    compressed_buf.seek(0)
    _log('Download complete, caching locally...', xbmc.LOGINFO if xbmc else None)

    # Stream-decompress and parse line by line
    batch = []
    count = 0
    try:
        with gzip.GzipFile(fileobj=compressed_buf) as gz:
            # Wrap in TextIOWrapper for line-by-line reading without loading all into memory
            text_stream = io.TextIOWrapper(gz, encoding='utf-8', errors='replace')
            header = text_stream.readline()  # skip header

            for line in text_stream:
                parts = line.rstrip('\n\r').split('\t')
                if len(parts) < 3:
                    continue
                tconst, rating_str, votes_str = parts[0], parts[1], parts[2]
                if tconst == '\\N' or rating_str == '\\N':
                    continue
                try:
                    batch.append((tconst, float(rating_str), int(votes_str)))
                except (ValueError, IndexError):
                    continue

                if len(batch) >= BATCH_SIZE:
                    conn.executemany(
                        'INSERT OR REPLACE INTO ratings (tconst, averageRating, numVotes) VALUES (?, ?, ?)',
                        batch)
                    conn.commit()
                    count += len(batch)
                    batch = []
                    if progress_callback:
                        # Estimate ~1.4M rows total
                        pct = min(95, int(30 + (count / 1400000.0) * 65))
                        progress_callback(pct, 'Caching IMDb ratings... {}%'.format(pct))
    except Exception as e:
        _log('Error during import: {}'.format(e), xbmc.LOGWARNING if xbmc else None)
        # Commit whatever we have so far
        if batch:
            conn.executemany(
                'INSERT OR REPLACE INTO ratings (tconst, averageRating, numVotes) VALUES (?, ?, ?)',
                batch)
            conn.commit()
            count += len(batch)
        return False

    if batch:
        conn.executemany(
            'INSERT OR REPLACE INTO ratings (tconst, averageRating, numVotes) VALUES (?, ?, ?)',
            batch)
        conn.commit()
        count += len(batch)

    _log('Cached {:,} IMDb ratings locally'.format(count), xbmc.LOGINFO if xbmc else None)
    return True


def _get_meta(conn, key):
    cur = conn.execute('SELECT value FROM metadata WHERE key = ?', (key,))
    row = cur.fetchone()
    return row[0] if row else None


def _set_meta(conn, key, value):
    conn.execute('INSERT OR REPLACE INTO metadata (key, value) VALUES (?, ?)', (key, str(value)))
    conn.commit()


def needs_update(max_age_days=7):
    """Check if the ratings dataset needs to be re-downloaded."""
    try:
        conn = _get_ratings_connection()
        last_updated = _get_meta(conn, 'last_updated')
        conn.close()
        if not last_updated:
            return True
        age = time.time() - float(last_updated)
        return age > (max_age_days * 86400)
    except Exception:
        return True


def update_database(progress_callback=None):
    """Download and import IMDb ratings dataset.

    Args:
        progress_callback: optional callable(percent, message) for progress reporting.
    Returns:
        True on success, False on failure.
    """
    def _progress(pct, msg):
        if progress_callback:
            progress_callback(pct, msg)

    try:
        conn = _get_ratings_connection()

        _progress(0, 'Downloading IMDb ratings...')
        success = _stream_download_and_import_ratings(conn, progress_callback)

        if success:
            _set_meta(conn, 'last_updated', str(time.time()))
            _progress(100, 'IMDb ratings cached successfully')

        conn.close()

        # Clean up old combined database if it exists
        old_db = os.path.join(_get_profile_path(), 'imdb_cache.db')
        if os.path.exists(old_db):
            try:
                os.remove(old_db)
                _log('Removed old imdb_cache.db', xbmc.LOGINFO if xbmc else None)
            except OSError:
                pass

        return success

    except Exception as e:
        _log('Database update failed: {}'.format(e), xbmc.LOGWARNING if xbmc else None)
        return False


def get_rating(imdb_id):
    """Look up rating and votes for an IMDb ID.

    Returns:
        dict with 'rating' (float) and 'votes' (int), or empty dict.
    """
    if not imdb_id:
        return {}
    try:
        conn = _get_ratings_connection()
        cur = conn.execute(
            'SELECT averageRating, numVotes FROM ratings WHERE tconst = ?',
            (imdb_id,))
        row = cur.fetchone()
        conn.close()
        if row:
            return {'rating': row[0], 'votes': row[1]}
    except Exception as e:
        _log('Rating lookup failed for {}: {}'.format(imdb_id, e))
    return {}
