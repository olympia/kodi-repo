# -*- coding: UTF-8 -*-
#
# Copyright (C) 2024, Team Kodi
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
#
# OMDb API client for Rotten Tomatoes scores, MetaCritic scores, and outline.
# Requires a free API key from https://www.omdbapi.com/apikey.aspx

"""
Fetches movie data from OMDb API (omdbapi.com).

Available data:
  - Rotten Tomatoes score (Tomatometer)
  - MetaCritic score
  - Short plot (outline)
  - IMDb rating (as fallback)
"""

from . import api_utils
from . import get_imdb_id

try:
    import xbmc
except ModuleNotFoundError:
    xbmc = None

OMDB_URL = 'https://www.omdbapi.com/'

HEADERS = (
    ('User-Agent', 'Kodi Movie scraper by Team Kodi'),
    ('Accept', 'application/json'),
)


def _log(msg, level=None):
    if xbmc:
        if level is None:
            level = xbmc.LOGDEBUG
        xbmc.log('[metadata.universal.python] OMDb: {}'.format(msg), level)


def get_details(uniqueids, api_key):
    """Fetch movie details from OMDb API.

    Args:
        uniqueids: dict with 'imdb' key
        api_key: OMDb API key (required)

    Returns dict with optional keys:
        'info': outline (short plot)
        'ratings': rotten_tomatoes and/or metacritic ratings
    """
    if not api_key or api_key == 'Please Enter Your OMDB API Key':
        return {}

    imdb_id = get_imdb_id(uniqueids)
    if not imdb_id:
        return {}

    _log('Fetching details for {} with OMDb'.format(imdb_id))
    api_utils.set_headers(dict(HEADERS))
    params = {
        'i': imdb_id,
        'apikey': api_key,
        'plot': 'short',
        'tomatoes': 'true',
    }
    response = api_utils.load_info(OMDB_URL, params=params, default={})

    if not response or response.get('Response') == 'False':
        error = response.get('Error', 'Unknown error') if response else 'No response'
        _log('OMDb error: {}'.format(error), xbmc.LOGWARNING if xbmc else None)
        return {'error': error}

    _log('DEBUG OMDb response keys: {}'.format(list(response.keys())), xbmc.LOGINFO if xbmc else None)
    _log('DEBUG OMDb tomatoConsensus: "{}"'.format(response.get('tomatoConsensus', 'NOT_PRESENT')[:100]),
         xbmc.LOGINFO if xbmc else None)
    _log('DEBUG OMDb Plot: "{}"'.format(response.get('Plot', 'NOT_PRESENT')[:100]),
         xbmc.LOGINFO if xbmc else None)

    result = {}
    info = {}

    # Short plot as outline
    plot = response.get('Plot', '')
    if plot and plot != 'N/A':
        info['outline'] = plot

    # Rotten Tomatoes Critics' Consensus (OMDb tomatoes=true may return this)
    consensus = response.get('tomatoConsensus', '')
    if consensus and consensus != 'N/A':
        info['rt_consensus'] = consensus

    # Rotten Tomatoes URL (for scraping consensus if not in OMDb response)
    rt_url = response.get('tomatoURL', '')
    if rt_url and rt_url != 'N/A':
        info['rt_url'] = rt_url

    if info:
        result['info'] = info

    # Ratings
    ratings = {}

    # Parse Ratings array
    for rating_entry in response.get('Ratings', []):
        source = rating_entry.get('Source', '')
        value = rating_entry.get('Value', '')
        if source == 'Rotten Tomatoes' and value:
            try:
                # Value is like "85%"
                rt_score = int(value.replace('%', ''))
                ratings['rottentomatoes'] = {
                    'rating': float(rt_score) / 10.0,  # Kodi expects 0-10 scale
                    'votes': 0
                }
            except (ValueError, TypeError):
                pass
        elif source == 'Metacritic' and value:
            try:
                # Value is like "75/100"
                mc_score = int(value.split('/')[0])
                ratings['metacritic'] = {
                    'rating': float(mc_score) / 10.0,  # Kodi expects 0-10 scale
                    'votes': 0
                }
            except (ValueError, TypeError):
                pass

    # Fallback: Metascore field
    if 'metacritic' not in ratings:
        metascore = response.get('Metascore', '')
        if metascore and metascore != 'N/A':
            try:
                ratings['metacritic'] = {
                    'rating': float(int(metascore)) / 10.0,
                    'votes': 0
                }
            except (ValueError, TypeError):
                pass

    if ratings:
        result['ratings'] = ratings

    return result
