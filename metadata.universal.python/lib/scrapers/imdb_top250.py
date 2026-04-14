# -*- coding: UTF-8 -*-
#
# Copyright (C) 2024, Team Kodi
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# IMDb Top 250 lookup using IMDb GraphQL chart query.

"""
Fetches the IMDb Top 250 chart and provides rank lookups by IMDb ID.
Uses the IMDb GraphQL API to query the chart.
Results are cached to disk (JSON) for 24 hours.
"""

import json
import os
import time

try:
    from urllib.request import Request, urlopen
    from urllib.error import URLError, HTTPError
except ImportError:
    from urllib2 import Request, urlopen, URLError, HTTPError

try:
    import xbmc
    import xbmcvfs
    import xbmcaddon
except ModuleNotFoundError:
    xbmc = None
    xbmcvfs = None
    xbmcaddon = None

GRAPHQL_URL = 'https://graphql.imdb.com/'
HEADERS = {
    'Content-Type': 'application/json',
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                  '(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
    'Accept': 'application/json',
}

# In-memory cache: dict of imdb_id -> rank
_top250_cache = {}
_cache_timestamp = 0
CACHE_MAX_AGE = 86400  # 24 hours

CHART_QUERY = '''
query TopRatedMovies {
  topRatedMovies: chartTitles(input: {chartType: TOP_RATED_MOVIES, first: 250}) {
    edges {
      node {
        id
        titleText { text }
        ratingsSummary { aggregateRating }
      }
      currentRank
    }
  }
}
'''


def _log(msg, level=None):
    if xbmc:
        if level is None:
            level = xbmc.LOGDEBUG
        xbmc.log('[metadata.universal.python] Top250: {}'.format(msg), level)


def _graphql_request(query):
    payload = json.dumps({'query': query}).encode('utf-8')
    req = Request(GRAPHQL_URL, data=payload)
    for k, v in HEADERS.items():
        req.add_header(k, v)
    try:
        response = urlopen(req, timeout=20)
        return json.loads(response.read().decode('utf-8'))
    except Exception as e:
        _log('GraphQL error: {}'.format(e))
        return None


def _get_cache_path():
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
    return os.path.join(profile_path, 'top250_cache.json')


def _save_cache(data):
    try:
        with open(_get_cache_path(), 'w') as f:
            json.dump({'timestamp': time.time(), 'data': data}, f)
    except Exception as e:
        _log('Failed to save cache: {}'.format(e))


def _load_cache():
    global _top250_cache, _cache_timestamp
    try:
        cache_path = _get_cache_path()
        if os.path.exists(cache_path):
            with open(cache_path, 'r') as f:
                cached = json.load(f)
            if time.time() - cached.get('timestamp', 0) < CACHE_MAX_AGE:
                _top250_cache = cached.get('data', {})
                _cache_timestamp = cached['timestamp']
                return True
    except Exception as e:
        _log('Failed to load cache: {}'.format(e))
    return False


def _fetch_top250():
    """Fetch Top 250 from IMDb GraphQL."""
    _log('Fetching Top 250 via GraphQL...', xbmc.LOGINFO if xbmc else None)

    response = _graphql_request(CHART_QUERY)
    if not response:
        return None

    if 'errors' in response:
        _log('GraphQL chart query error: {}'.format(
            response['errors'][0].get('message', '?')[:200]))
        return None

    data = response.get('data', {})
    for key in ['topRatedMovies', 'chartTitles']:
        chart_data = data.get(key, {})
        edges = chart_data.get('edges', [])
        if edges:
            result = {}
            for edge in edges:
                node = edge.get('node', {})
                rank = edge.get('currentRank') or node.get('currentRank')
                imdb_id = node.get('id', '')
                if rank and imdb_id:
                    result[imdb_id] = int(rank)
            if result:
                _log('Fetched {} entries'.format(len(result)),
                     xbmc.LOGINFO if xbmc else None)
                return result

    _log('GraphQL chart query returned no data', xbmc.LOGWARNING if xbmc else None)
    return None


def _ensure_loaded():
    """Ensure the Top 250 cache is populated."""
    global _top250_cache, _cache_timestamp

    if _top250_cache and (time.time() - _cache_timestamp < CACHE_MAX_AGE):
        return

    if _load_cache():
        return

    data = _fetch_top250()
    if data:
        _top250_cache = data
        _cache_timestamp = time.time()
        _save_cache(data)


def get_top250_rank(imdb_id):
    """Get the Top 250 rank for a movie by IMDb ID.

    Returns:
        int rank (1-250) or None if not in Top 250.
    """
    if not imdb_id:
        return None
    _ensure_loaded()
    return _top250_cache.get(imdb_id)
