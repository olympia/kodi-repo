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
    re.compile(r'id="critics-consensus"[^>]*>.*?<p>(.*?)</p>', re.DOTALL),
    re.compile(r'data-qa="critics-consensus"[^>]*>([^<]+)<', re.DOTALL),
    re.compile(r'<span\s+data-qa="critics-consensus">([^<]+)</span>', re.DOTALL),
    re.compile(r'"criticsConsensus"\s*:\s*"([^"]+)"', re.DOTALL),
    re.compile(r'class="what-to-know__section-body"[^>]*>([^<]+)<', re.DOTALL),
    re.compile(r'class="mop-ratings-wrap__text--concensus"[^>]*>([^<]+)<', re.DOTALL),
    re.compile(r'class="critics-consensus[^"]*"[^>]*>([^<]+)<', re.DOTALL),
    re.compile(r'Critics Consensus:?\s*</span>\s*([^<]+)<', re.DOTALL | re.IGNORECASE),
]


def _log(msg, level=None):
    if xbmc:
        if level is None:
            level = xbmc.LOGDEBUG
        xbmc.log('[metadata.universal.python] RT: {}'.format(msg), level)


def get_rt_data(rt_url):
    """Fetch Critics' Consensus and all RT score variants from a Rotten Tomatoes movie page.

    Returns dict with keys:
        consensus, tomatometer, reviewcount,
        topcriticsscore, topcriticscount,
        audiencescore, audiencecount.
    """
    result = {'consensus': '', 'tomatometer': None, 'reviewcount': None,
              'topcriticsscore': None, 'topcriticscount': None,
              'audiencescore': None, 'audiencecount': None}
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

    tomatometer, reviewcount = _parse_jsonld_ratings(html)
    result['tomatometer'] = tomatometer
    result['reviewcount'] = reviewcount
    if tomatometer is not None:
        _log('Found Tomatometer: {}% ({} reviews)'.format(tomatometer, reviewcount),
             xbmc.LOGINFO if xbmc else None)

    scorecard = _parse_media_scorecard_json(html)
    audiencescore = _parse_audience_score(html, scorecard=scorecard)
    audiencecount = _parse_audience_count(html, scorecard=scorecard)
    result['audiencescore'] = audiencescore
    result['audiencecount'] = audiencecount
    if audiencescore is not None:
        _log('Found Popcornmeter: {}% ({} ratings)'.format(audiencescore, audiencecount),
             xbmc.LOGINFO if xbmc else None)

    topcriticsscore, topcriticscount = _parse_topcritics(scorecard)
    result['topcriticsscore'] = topcriticsscore
    result['topcriticscount'] = topcriticscount
    if topcriticsscore is not None:
        _log('Found Top Critics: {}% ({} reviews)'.format(topcriticsscore, topcriticscount),
             xbmc.LOGINFO if xbmc else None)

    consensus = _find_consensus(html)
    result['consensus'] = consensus

    return result


def _find_consensus(html):
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

    _log('No consensus found on page', xbmc.LOGWARNING if xbmc else None)
    return ''


def _parse_media_scorecard_json(html):
    """Extract and parse the media-scorecard JSON blob embedded in the RT page."""
    m = re.search(
        r'<script\b[^>]*id="media-scorecard-json"[^>]*>\s*(\{.*?\})\s*</script>',
        html, re.DOTALL | re.IGNORECASE)
    if not m:
        return None
    try:
        return json.loads(m.group(1))
    except (json.JSONDecodeError, ValueError):
        return None


def _parse_topcritics(scorecard):
    """Extract Top Critics score and count from scorecard['overlay']['criticsTop']."""
    if not scorecard:
        return None, None
    overlay = scorecard.get('overlay') or {}
    top = overlay.get('criticsTop') or {}

    score = None
    score_raw = top.get('score')
    if score_raw is not None:
        try:
            val = int(str(score_raw).replace('%', '').strip())
            if 0 <= val <= 100:
                score = val
        except (ValueError, TypeError):
            pass

    count = None
    count_raw = top.get('ratingCount') or top.get('reviewCount')
    if count_raw is not None:
        try:
            count = int(count_raw)
        except (ValueError, TypeError):
            pass

    return score, count


def _parse_audience_score(html, scorecard=None):
    """Extract Popcornmeter (audience) score. Returns int 0-100 or None."""
    if scorecard is None:
        scorecard = _parse_media_scorecard_json(html)
    if scorecard:
        audience = scorecard.get('audienceScore') or {}
        score = audience.get('score')
        if score is not None:
            try:
                val = int(str(score).replace('%', '').strip())
                if 0 <= val <= 100:
                    return val
            except (ValueError, TypeError):
                pass

    m = re.search(
        r'<rt-text\s+[^>]*slot="audienceScore"[^>]*>\s*(\d{1,3})\s*%?\s*</rt-text>',
        html, re.IGNORECASE | re.DOTALL)
    if m:
        try:
            score = int(m.group(1))
            if 0 <= score <= 100:
                return score
        except (ValueError, TypeError):
            pass

    m = re.search(r'<score-board\b[^>]*\baudiencescore="(\d{1,3})"',
                  html, re.IGNORECASE)
    if m:
        try:
            score = int(m.group(1))
            if 0 <= score <= 100:
                return score
        except (ValueError, TypeError):
            pass

    return None


def _parse_audience_count(html, scorecard=None):
    """Extract Popcornmeter audience rating count. Returns int or None."""
    if scorecard is None:
        scorecard = _parse_media_scorecard_json(html)
    if scorecard:
        audience = scorecard.get('audienceScore') or {}
        banded = audience.get('bandedRatingCount')
        if banded:
            digits = re.sub(r'[^\d]', '', str(banded))
            if digits:
                try:
                    return int(digits)
                except (ValueError, TypeError):
                    pass

    m = re.search(
        r'<rt-text\s+[^>]*slot="audienceCount"[^>]*>\s*([\d,]+)',
        html, re.IGNORECASE | re.DOTALL)
    if m:
        try:
            return int(m.group(1).replace(',', ''))
        except (ValueError, TypeError):
            pass

    m = re.search(r'([\d,]+)\s*(?:Verified\s+)?Ratings\b', html, re.IGNORECASE)
    if m:
        try:
            count = int(m.group(1).replace(',', ''))
            if count >= 5:
                return count
        except (ValueError, TypeError):
            pass

    return None


def _parse_jsonld_ratings(html):
    """Extract Tomatometer (All Critics) score and review count from JSON-LD aggregateRating."""
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
    text = re.sub(r'<[^>]+>', '', text)
    text = text.replace('&amp;', '&')
    text = text.replace('&lt;', '<')
    text = text.replace('&gt;', '>')
    text = text.replace('&quot;', '"')
    text = text.replace('&#39;', "'")
    text = text.replace('&apos;', "'")
    text = text.replace('&#x27;', "'")
    text = text.replace('&mdash;', '—')
    text = text.replace('&ndash;', '–')
    text = text.replace('\n', ' ')
    text = re.sub(r'\s+', ' ', text)
    return text.strip()
