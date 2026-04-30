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
# IMDb GraphQL API client for fetching plot, tagline, outline, cast,
# certifications, and other data.

"""
Fetches movie data from IMDb's public GraphQL API (graphql.imdb.com).
This endpoint is used by IMDb's own website and is not blocked by their WAF.
"""

import json

try:
    from urllib.request import Request, urlopen
    from urllib.error import URLError, HTTPError
except ImportError:
    from urllib2 import Request, urlopen, URLError, HTTPError

try:
    import xbmc
except ModuleNotFoundError:
    xbmc = None

from . import get_imdb_id

GRAPHQL_URL = 'https://graphql.imdb.com/'

HEADERS = {
    'Content-Type': 'application/json',
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                  '(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
    'Accept': 'application/json',
}

# Full GraphQL query — plot, outline, tagline, cast with photos, certifications
MOVIE_QUERY = '''
query GetMovieDetails($id: ID!) {
  title(id: $id) {
    titleText { text }
    originalTitleText { text }
    releaseDate { year month day }
    countriesOfOrigin { countries { id text } }
    primaryImage { url }
    plot {
      plotText { plainText }
    }
    summaries: plots(first: 5, filter: {spoilers: EXCLUDE_SPOILERS}) {
      edges {
        node {
          plotText { plainText }
        }
      }
    }
    allPlots: plots(first: 10) {
      edges {
        node {
          plotText { plainText }
        }
      }
    }
    taglines(first: 3) {
      edges {
        node {
          text
        }
      }
    }
    ratingsSummary {
      aggregateRating
      voteCount
      topRanking { rank }
    }
    genres {
      genres {
        text
      }
    }
    runtime {
      seconds
    }
    certificate {
      rating
      country {
        id
        text
      }
    }
    certificates(first: 50) {
      edges {
        node {
          rating
          country {
            id
            text
          }
        }
      }
    }
    credits(first: 50, filter: { categories: ["actor", "actress"] }) {
      edges {
        node {
          name {
            id
            nameText { text }
            primaryImage {
              url
              width
              height
            }
          }
          ... on Cast {
            characters {
              name
            }
          }
        }
      }
    }
    directors: credits(first: 10, filter: { categories: ["director"] }) {
      edges {
        node {
          name {
            id
            nameText { text }
          }
        }
      }
    }
    writers: credits(first: 10, filter: { categories: ["writer"] }) {
      edges {
        node {
          name {
            id
            nameText { text }
          }
        }
      }
    }
  }
}
'''


def _log(msg, level=None):
    if xbmc:
        if level is None:
            level = xbmc.LOGDEBUG
        xbmc.log('[metadata.universal.python] IMDb GraphQL: {}'.format(msg), level)


def _graphql_request(query, variables):
    """Send a GraphQL request to IMDb and return parsed JSON response."""
    payload = json.dumps({'query': query, 'variables': variables}).encode('utf-8')
    req = Request(GRAPHQL_URL, data=payload)
    for k, v in HEADERS.items():
        req.add_header(k, v)
    try:
        response = urlopen(req, timeout=15)
        body = response.read().decode('utf-8')
        return json.loads(body)
    except HTTPError as e:
        _log('HTTP error {}'.format(e.code), xbmc.LOGWARNING if xbmc else None)
        return {'error': 'HTTP error {}'.format(e.code)}
    except URLError as e:
        _log('URL error: {}'.format(e.reason), xbmc.LOGWARNING if xbmc else None)
        return {'error': 'URL error: {}'.format(e.reason)}
    except Exception as e:
        _log('Error: {}'.format(e), xbmc.LOGWARNING if xbmc else None)
        return {'error': str(e)}


def get_details(uniqueids, include_spoilers=False):
    """Fetch movie details from IMDb GraphQL API.

    Args:
        uniqueids: dict with 'imdb' key
        include_spoilers: if True, the 'plot' field returns the best spoiler
            summary (IMDb's full synopsis) when available; otherwise it returns
            the best spoiler-free summary. 'outline' is always the short
            outline shown at the top of IMDb's title page.

    Returns dict with optional keys:
      'info': plot, outline, tagline, genres, mpaa, title, premiered, ...
      'ratings': imdb rating/votes
      'cast': list of cast dicts with name, role, thumbnail, order
      'directors': list of director names
      'writers': list of writer names
      'certifications': dict of country_code -> rating
    """
    imdb_id = get_imdb_id(uniqueids)
    if not imdb_id:
        return {}

    _log('Fetching details for {}'.format(imdb_id))
    response = _graphql_request(MOVIE_QUERY, {'id': imdb_id})

    if 'error' in response:
        return {'error': response['error']}

    # Check for GraphQL-level errors
    if 'errors' in response and response['errors']:
        error_msg = response['errors'][0].get('message', 'Unknown GraphQL error')
        _log('GraphQL error: {}'.format(error_msg), xbmc.LOGWARNING if xbmc else None)
        # Still try to use partial data if available
        if not response.get('data', {}).get('title'):
            return {'error': error_msg}

    title_data = (response.get('data') or {}).get('title')
    if not title_data:
        _log('No title data in response for {}'.format(imdb_id))
        return {}

    result = {}
    info = {}

    # Title
    title_text = (title_data.get('titleText') or {}).get('text', '')
    if title_text:
        info['title'] = title_text

    # Release date → premiered (YYYY-MM-DD)
    release = title_data.get('releaseDate')
    if release and release.get('year'):
        y = release['year']
        m = release.get('month')
        d = release.get('day')
        if m and d:
            info['premiered'] = '{:04d}-{:02d}-{:02d}'.format(y, m, d)
        elif m:
            info['premiered'] = '{:04d}-{:02d}-01'.format(y, m)
        else:
            info['premiered'] = '{:04d}-01-01'.format(y)

    # Countries of origin
    countries_data = (title_data.get('countriesOfOrigin') or {}).get('countries', [])
    if countries_data:
        info['countries'] = [c['text'] for c in countries_data if c.get('text')]

    # Primary image (poster)
    primary_image = title_data.get('primaryImage')
    if primary_image and primary_image.get('url'):
        info['poster_url'] = primary_image['url']

    # Plot outline — always the short text shown at the top of IMDb's title
    # page (title.plot scalar). This is the IMDb "Outline" plot type.
    outline_text = ''
    plot_data = title_data.get('plot')
    if plot_data and plot_data.get('plotText'):
        outline_text = plot_data['plotText'].get('plainText', '') or ''
    if outline_text:
        info['outline'] = outline_text

    # Longer plot — choose from the plots connection.
    #   summaries: best spoiler-free summary
    #   synopsis:  best spoiler summary (IMDb's full "Synopsis" plot type),
    #              computed as allPlots minus summaries
    summary_texts = []
    for edge in ((title_data.get('summaries') or {}).get('edges', []) or []):
        text = ((edge.get('node') or {}).get('plotText') or {}).get('plainText', '')
        if text:
            summary_texts.append(text)

    all_texts = []
    for edge in ((title_data.get('allPlots') or {}).get('edges', []) or []):
        text = ((edge.get('node') or {}).get('plotText') or {}).get('plainText', '')
        if text:
            all_texts.append(text)

    best_summary = max(summary_texts, key=len) if summary_texts else ''
    summary_set = set(summary_texts)
    spoiler_candidates = [t for t in all_texts if t not in summary_set]
    best_spoiler = max(spoiler_candidates, key=len) if spoiler_candidates else ''

    if include_spoilers:
        plot_text = best_spoiler or best_summary or outline_text
    else:
        plot_text = best_summary or outline_text
    if plot_text:
        info['plot'] = plot_text

    # Tagline
    taglines_edges = (title_data.get('taglines') or {}).get('edges', [])
    if taglines_edges:
        first_tagline = taglines_edges[0].get('node', {}).get('text', '')
        if first_tagline:
            info['tagline'] = first_tagline

    # Genres
    genres_data = (title_data.get('genres') or {}).get('genres', [])
    if genres_data:
        info['genres'] = [g['text'] for g in genres_data if g.get('text')]

    # Default certification
    cert_data = title_data.get('certificate')
    if cert_data and cert_data.get('rating'):
        info['mpaa'] = cert_data['rating']

    # Top 250 rank — only if the movie is actually in the top 250
    ratings_summary = title_data.get('ratingsSummary') or {}
    top_ranking = ratings_summary.get('topRanking') or {}
    rank = top_ranking.get('rank')
    if rank and rank <= 250:
        info['top250'] = rank

    if info:
        result['info'] = info

    # Certifications by country
    certs_edges = (title_data.get('certificates') or {}).get('edges', [])
    if certs_edges:
        certifications = {}
        for edge in certs_edges:
            node = edge.get('node', {})
            country = (node.get('country') or {}).get('id', '')
            rating = node.get('rating', '')
            if country and rating:
                certifications[country.upper()] = rating
        if certifications:
            result['certifications'] = certifications

    # Ratings
    ratings_data = title_data.get('ratingsSummary')
    if ratings_data and ratings_data.get('aggregateRating'):
        result['ratings'] = {
            'imdb': {
                'rating': float(ratings_data['aggregateRating']),
                'votes': int(ratings_data.get('voteCount', 0))
            }
        }

    # Cast with photos
    cast_edges = (title_data.get('credits') or {}).get('edges', [])
    if cast_edges:
        cast = []
        for i, edge in enumerate(cast_edges):
            node = edge.get('node', {})
            name_data = node.get('name', {})
            name = (name_data.get('nameText') or {}).get('text', '')
            if not name:
                continue
            characters = node.get('characters', [])
            role = characters[0].get('name', '') if characters else ''
            thumbnail = ''
            primary_image = name_data.get('primaryImage')
            if primary_image and primary_image.get('url'):
                thumbnail = primary_image['url']
            cast.append({
                'name': name,
                'role': role,
                'thumbnail': thumbnail,
                'order': i
            })
        if cast:
            result['cast'] = cast

    # Directors
    dir_edges = (title_data.get('directors') or {}).get('edges', [])
    if dir_edges:
        result['directors'] = [
            (e.get('node', {}).get('name', {}).get('nameText', {}) or {}).get('text', '')
            for e in dir_edges
        ]
        result['directors'] = [d for d in result['directors'] if d]

    # Writers
    wr_edges = (title_data.get('writers') or {}).get('edges', [])
    if wr_edges:
        result['writers'] = [
            (e.get('node', {}).get('name', {}).get('nameText', {}) or {}).get('text', '')
            for e in wr_edges
        ]
        result['writers'] = [w for w in result['writers'] if w]

    return result
