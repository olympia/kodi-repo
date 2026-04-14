# -*- coding: UTF-8 -*-
#
# Copyright (C) 2024, Team Kodi
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Rotten Tomatoes Critics' Consensus scraper.
# Fetches the consensus text and Tomatometer data from a Rotten Tomatoes movie page.

"""
Scrapes the Critics' Consensus text and rating data from a Rotten Tomatoes movie page.
"""

import json
import re

try:
    from urllib.request import Request, urlopen
    from urllib.error import URLError, HTTPError
except ImportError:
    from urllib2 import Request, urlopen, URLError, HTTPError

try:
    import xbmc
except ModuleNotFoundError:
    xbmc = None

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                  '(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.5',
}

# Patterns to find Critics' Consensus on RT page
CONSENSUS_PATTERNS = [
    # Current RT layout (2025+): <div id="critics-consensus"> ... <p>TEXT</p>
    re.compile(r'id="critics-consensus"[^>]*>.*?<p>(.*?)</p>', re.DOTALL),
    # data-qa attribute variant
    re.compile(r'data-qa="critics-consensus"[^>]*>([^<]+)<', re.DOTALL),
    # Scoreboard element with consensus slot
    re.compile(r'<span\s+data-qa="critics-consensus">([^<]+)</span>', re.DOTALL),
    # JSON-LD or script data
    re.compile(r'"criticsConsensus"\s*:\s*"([^"]+)"', re.DOTALL),
    # Consensus paragraph
    re.compile(r'class="what-to-know__section-body"[^>]*>([^<]+)<', re.DOTALL),
    # Older RT layout
    re.compile(r'class="mop-ratings-wrap__text--concensus"[^>]*>([^<]+)<', re.DOTALL),
    # Another older variant
    re.compile(r'class="critics-consensus[^"]*"[^>]*>([^<]+)<', re.DOTALL),
    # Even older
    re.compile(r'Critics Consensus:?\s*</span>\s*([^<]+)<', re.DOTALL | re.IGNORECASE),
]


def _log(msg, level=None):
    if xbmc:
        if level is None:
            level = xbmc.LOGDEBUG
        xbmc.log('[metadata.universal.python] RT: {}'.format(msg), level)


def get_rt_data(rt_url):
    """Fetch Critics' Consensus and Tomatometer data from a Rotten Tomatoes movie page.

    Args:
        rt_url: Full URL to the RT movie page

    Returns:
        dict with keys:
            'consensus': str - Critics' Consensus text (empty if not found)
            'tomatometer': int or None - Tomatometer score (0-100)
            'reviewcount': int or None - Number of critic reviews
    """
    result = {'consensus': '', 'tomatometer': None, 'reviewcount': None}
    if not rt_url:
        return result

    _log('Fetching data from {}'.format(rt_url))
    req = Request(rt_url)
    for k, v in HEADERS.items():
        req.add_header(k, v)

    try:
        response = urlopen(req, timeout=15)
        html = response.read().decode('utf-8', errors='replace')
    except HTTPError as e:
        _log('HTTP error {}: {}'.format(e.code, rt_url), xbmc.LOGWARNING if xbmc else None)
        return result
    except URLError as e:
        _log('URL error: {}'.format(e.reason), xbmc.LOGWARNING if xbmc else None)
        return result
    except Exception as e:
        _log('Error fetching RT page: {}'.format(e), xbmc.LOGWARNING if xbmc else None)
        return result

    # Extract Tomatometer score and review count from JSON-LD
    tomatometer, reviewcount = _parse_jsonld_ratings(html)
    result['tomatometer'] = tomatometer
    result['reviewcount'] = reviewcount
    if tomatometer is not None:
        _log('Found Tomatometer: {}% ({} reviews)'.format(tomatometer, reviewcount),
             xbmc.LOGINFO if xbmc else None)

    # Extract Critics' Consensus
    consensus = _find_consensus(html)
    result['consensus'] = consensus

    return result


def _find_consensus(html):
    """Try all patterns to find Critics' Consensus text."""
    for i, pattern in enumerate(CONSENSUS_PATTERNS):
        match = pattern.search(html)
        if match:
            text = match.group(1).strip()
            text = _clean_html(text)
            if text and len(text) > 10 and not text.startswith('Discover reviews'):
                _log('Found consensus with pattern {}: "{}"'.format(i, text[:100]),
                     xbmc.LOGINFO if xbmc else None)
                return text

    consensus = _parse_jsonld_consensus(html)
    if consensus:
        _log('Found consensus in JSON-LD: "{}"'.format(consensus[:100]),
             xbmc.LOGINFO if xbmc else None)
        return consensus

    broad_match = re.search(
        r'(?:critics.?consensus|what.to.know)[^>]*>([^<]{20,500})',
        html, re.IGNORECASE)
    if broad_match:
        text = _clean_html(broad_match.group(1).strip())
        if text and len(text) > 15 and not text.startswith('Discover reviews'):
            _log('Found consensus with broad search: "{}"'.format(text[:100]),
                 xbmc.LOGINFO if xbmc else None)
            return text

    consensus_pos = html.lower().find('consensus')
    if consensus_pos >= 0:
        snippet = html[max(0, consensus_pos-200):consensus_pos+300]
        _log('DEBUG: HTML near "consensus": {}'.format(repr(snippet[:400])),
             xbmc.LOGINFO if xbmc else None)
    else:
        _log('DEBUG: "consensus" not found in page HTML at all',
             xbmc.LOGINFO if xbmc else None)
        _log('DEBUG: HTML length={}, starts with: {}'.format(len(html), repr(html[:200])),
             xbmc.LOGINFO if xbmc else None)

    _log('No consensus found on page', xbmc.LOGWARNING if xbmc else None)
    return ''


def _parse_jsonld_ratings(html):
    """Extract Tomatometer score and review count from JSON-LD aggregateRating."""
    try:
        ld_matches = re.findall(
            r'<script\s+type="application/ld\+json"[^>]*>(.*?)</script>',
            html, re.DOTALL)
        for ld_text in ld_matches:
            try:
                data = json.loads(ld_text)
                if not isinstance(data, dict):
                    continue
                agg = data.get('aggregateRating')
                if not agg or not isinstance(agg, dict):
                    continue
                score = agg.get('ratingValue')
                count = agg.get('reviewCount') or agg.get('ratingCount')
                if score is not None:
                    try:
                        return int(score), int(count) if count else None
                    except (ValueError, TypeError):
                        pass
            except (json.JSONDecodeError, ValueError):
                continue
    except Exception:
        pass
    return None, None


def _parse_jsonld_consensus(html):
    """Try to extract consensus from JSON-LD structured data on RT page."""
    try:
        ld_matches = re.findall(
            r'<script\s+type="application/ld\+json"[^>]*>(.*?)</script>',
            html, re.DOTALL)
        for ld_text in ld_matches:
            try:
                data = json.loads(ld_text.replace('\n', ''))
                if isinstance(data, dict):
                    for key in ('criticsConsensus', 'reviewBody'):
                        val = data.get(key)
                        if val and not val.startswith('Discover reviews'):
                            return _clean_html(str(val).strip())
                    review = data.get('review', {})
                    if isinstance(review, dict) and review.get('reviewBody'):
                        body = review['reviewBody']
                        if not body.startswith('Discover reviews'):
                            return _clean_html(body.strip())
            except (json.JSONDecodeError, ValueError):
                continue
    except Exception:
        pass
    return ''


def _clean_html(text):
    """Remove HTML tags and decode entities."""
    text = re.sub(r'<[^>]+>', '', text)
    text = text.replace('&amp;', '&')
    text = text.replace('&lt;', '<')
    text = text.replace('&gt;', '>')
    text = text.replace('&quot;', '"')
    text = text.replace('&#39;', "'")
    text = text.replace('&apos;', "'")
    text = text.replace('&#x27;', "'")
    text = text.replace('&mdash;', '\u2014')
    text = text.replace('&ndash;', '\u2013')
    text = text.replace('\n', ' ')
    text = re.sub(r'\s+', ' ', text)
    return text.strip()
