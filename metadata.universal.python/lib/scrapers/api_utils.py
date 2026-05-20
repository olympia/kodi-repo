# coding: utf-8
#
# Copyright (C) 2020, Team Kodi
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

"""Functions to interact with various web site APIs."""

from __future__ import absolute_import, unicode_literals

import gzip
import io
import json
import zlib

try:
    import xbmc
except ModuleNotFoundError:
    # only used for logging HTTP calls, not available nor needed for testing
    xbmc = None

# from pprint import pformat
try: #PY2 / PY3
    from urllib2 import Request, urlopen
    from urllib2 import URLError
    from urllib import urlencode
except ImportError:
    from urllib.request import Request, urlopen
    from urllib.error import URLError
    from urllib.parse import urlencode
try:
    from typing import Text, Optional, Union, List, Dict, Any  # pylint: disable=unused-import
    InfoType = Dict[Text, Any]  # pylint: disable=invalid-name
except ImportError:
    pass

HEADERS = {}


def set_headers(headers):
    HEADERS.clear()
    HEADERS.update(headers)


def _get_content_encoding(response):
    """Return Content-Encoding header value (lowercased) or empty string."""
    encoding = ''
    try:
        encoding = response.headers.get('Content-Encoding', '') or ''
    except AttributeError:
        try:
            encoding = response.info().get('Content-Encoding', '') or ''
        except Exception:
            encoding = ''
    return encoding.lower().strip()


def _maybe_decompress(data, content_encoding):
    """Decompress bytes if Content-Encoding indicates gzip/deflate, or if
    the body itself starts with the gzip magic number even though no header
    advertised it. The latter handles a known CloudFront edge case where
    cached gzipped responses are sometimes served even to clients that did
    not send Accept-Encoding: gzip.

    Reference: https://www.themoviedb.org/talk/6a0cf9a5dd8f54b8836a3750
    """
    if not isinstance(data, (bytes, bytearray)):
        return data
    is_gzip_header = content_encoding == 'gzip'
    is_deflate_header = content_encoding == 'deflate'
    is_gzip_magic = len(data) >= 2 and bytes(data[:2]) == b'\x1f\x8b'
    if is_gzip_header or is_gzip_magic:
        try:
            return gzip.GzipFile(fileobj=io.BytesIO(bytes(data))).read()
        except (IOError, OSError, EOFError) as e:
            if xbmc:
                xbmc.log('[metadata.universal.python] gzip decompress failed: {}'.format(e),
                         xbmc.LOGWARNING)
            return data
    if is_deflate_header:
        try:
            return zlib.decompress(data)
        except zlib.error:
            # Some servers send raw deflate (no zlib header)
            try:
                return zlib.decompress(data, -zlib.MAX_WBITS)
            except zlib.error as e:
                if xbmc:
                    xbmc.log('[metadata.universal.python] deflate decompress failed: {}'.format(e),
                             xbmc.LOGWARNING)
                return data
    return data


def read_response_body(response):
    """Read a urlopen() response and return the body as a decoded UTF-8 string.

    Transparently decompresses gzip/deflate-encoded responses, including
    responses where the Content-Encoding header is missing but the body is
    in fact gzipped (CloudFront caching anomaly).
    """
    raw = response.read()
    encoding = _get_content_encoding(response)
    decompressed = _maybe_decompress(raw, encoding)
    if isinstance(decompressed, (bytes, bytearray)):
        return bytes(decompressed).decode('utf-8', errors='replace')
    return decompressed


def load_info(url, params=None, default=None, resp_type = 'json'):
    # type: (Text, Optional[Dict[Text, Union[Text, List[Text]]]]) -> Union[dict, list]
    """
    Load info from external api

    :param url: API endpoint URL
    :param params: URL query params
    :default: object to return if there is an error
    :resp_type: what to return to the calling function
    :return: API response or default on error
    """
    theerror = ''
    if params:
        url = url + '?' + urlencode(params)
    if xbmc:
        xbmc.log('Calling URL "{}"'.format(url), xbmc.LOGDEBUG)
        if HEADERS:
            xbmc.log(str(HEADERS), xbmc.LOGDEBUG)
    # Request uncompressed content where supported; we still gunzip defensively
    # in case the server (e.g. CloudFront) ignores this and ships gzip anyway.
    request_headers = dict(HEADERS)
    if 'Accept-Encoding' not in request_headers and 'accept-encoding' not in request_headers:
        request_headers['Accept-Encoding'] = 'identity'
    req = Request(url, headers=request_headers)
    try:
        response = urlopen(req)
    except URLError as e:
        if hasattr(e, 'reason'):
            theerror = {'error': 'failed to reach the remote site\nReason: {}'.format(e.reason)}
        elif hasattr(e, 'code'):
            theerror = {'error': 'remote site unable to fulfill the request\nError code: {}'.format(e.code)}
        if default is not None:
            return default
        else:
            return theerror
    body = read_response_body(response)
    if resp_type.lower() == 'json':
        resp = json.loads(body)
    else:
        resp = body
    # xbmc.log('the api response:\n{}'.format(pformat(resp)), xbmc.LOGDEBUG)
    return resp
