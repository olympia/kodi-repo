import re
try:
    from urlparse import parse_qsl
except ImportError: # py2 / py3
    from urllib.parse import parse_qsl

# get addon params from the plugin path querystring
def get_params(argv):
    result = {'handle': int(argv[0])}
    if len(argv) < 2 or not argv[1]:
        return result

    result.update(parse_qsl(argv[1].lstrip('?')))
    return result

def combine_scraped_details_info_and_ratings(original_details, additional_details):
    def update_or_set(details, key, value):
        if key in details:
            details[key].update(value)
        else:
            details[key] = value

    if additional_details:
        if additional_details.get('info'):
            update_or_set(original_details, 'info', additional_details['info'])
        if additional_details.get('ratings'):
            update_or_set(original_details, 'ratings', additional_details['ratings'])
    return original_details

def combine_scraped_details_available_artwork(original_details, additional_details, language,
                                               settings, fanarttv_language=None):
    """Combine fanart.tv artwork with TMDB artwork.

    Priority rules:
    - fanart.tv artwork goes FIRST (higher priority than TMDB) by default
    - EXCEPTION: if the fanart.tv language and TMDB language match, AND
      fanart.tv has NO artwork in that language for a given type, BUT TMDB does,
      then TMDB takes priority for that type
    """
    if language:
        # Image languages don't have regional variants
        language = language.split('-')[0]
    if not additional_details or not additional_details.get('available_art'):
        return original_details

    available_art = additional_details['available_art']
    if not original_details.get('available_art'):
        original_details['available_art'] = {}

    # Determine TMDB artwork language (same as main language stripped to 2-char)
    tmdb_lang = language  # e.g. "hu", "en"
    ftv_lang = fanarttv_language  # e.g. "hu", "en", or None

    for arttype, artlist in available_art.items():
        tmdb_list = original_details['available_art'].get(arttype, [])

        # Sort fanart.tv items: preferred language first
        artlist_sorted = sorted(artlist, key=lambda x: x.get('lang') == ftv_lang, reverse=True)

        if ftv_lang and tmdb_lang and ftv_lang == tmdb_lang:
            # Same language configured for both sources
            # Check if fanart.tv has ANY artwork in that language
            ftv_has_lang = any(img.get('lang') == ftv_lang for img in artlist)
            tmdb_has_lang = any(img.get('lang') == tmdb_lang for img in tmdb_list)

            if not ftv_has_lang and tmdb_has_lang:
                # fanart.tv has nothing in this language, TMDB does → TMDB first
                combinlist = tmdb_list + artlist_sorted
            else:
                # Default: fanart.tv first
                combinlist = artlist_sorted + tmdb_list
        else:
            # Different languages configured → fanart.tv always first
            combinlist = artlist_sorted + tmdb_list

        original_details['available_art'][arttype] = combinlist

    return original_details

def find_uniqueids_in_text(input_text):
    result = {}
    res = re.search(r'(themoviedb.org/movie/)([0-9]+)', input_text)
    if (res):
        result['tmdb'] = res.group(2)
    res = re.search(r'imdb....?/title/tt([0-9]+)', input_text)
    if (res):
        result['imdb'] = 'tt' + res.group(1)
    else:
        res = re.search(r'imdb....?/Title\?t{0,2}([0-9]+)', input_text)
        if (res):
            result['imdb'] = 'tt' + res.group(1)
    return result
