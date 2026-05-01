def configure_scraped_details(details, settings):
    details = _configure_rating_prefix(details, settings)
    details = _configure_keeporiginaltitle(details, settings)
    details = _configure_trailer(details, settings)
    details = _configure_multiple_studios(details, settings)
    details = _configure_multiple_countries(details, settings)
    details = _configure_default_rating(details, settings)
    details = _configure_tags(details, settings)
    return details

def configure_tmdb_artwork(details, settings):
    """Remove TMDB artwork types that are disabled in settings."""
    if 'available_art' not in details:
        return details

    art = details['available_art']
    posters_enabled = settings.getSettingBool('tmdbthumbs')
    if not posters_enabled:
        art.pop('poster', None)
        art.pop('set.poster', None)

    fanart_enabled = settings.getSettingBool('fanart')
    if not fanart_enabled:
        art.pop('fanart', None)
        art.pop('set.fanart', None)

    if not settings.getSettingBool('tmdbmovielandscape'):
        if 'landscape' in art:
            if fanart_enabled:
                art['fanart'] = art.get('fanart', []) + art['landscape']
            del art['landscape']
        if 'set.landscape' in art:
            if fanart_enabled:
                art['set.fanart'] = art.get('set.fanart', []) + art['set.landscape']
            del art['set.landscape']

    if not posters_enabled:
        art.pop('keyart', None)
        art.pop('set.keyart', None)

    if not settings.getSettingBool('tmdbclearlogo'):
        art.pop('clearlogo', None)

    return details

def is_fanarttv_configured(settings):
    """Check if ANY fanart.tv artwork type is enabled."""
    fanarttv_settings = [
        'fanarttvposter', 'fanarttvfanart', 'fanarttvkeyart',
        'fanarttvclearlogo', 'fanarttvclearart',
        'fanarttvmoviebanner', 'fanarttvmovielandscape', 'fanarttvmoviediscart',
        'fanarttvsetposter', 'fanarttvsetfanart',
        'fanarttvsetclearlogo', 'fanarttvsetclearart',
        'fanarttvsetmoviebanner', 'fanarttvsetmovielandscape', 'fanarttvsetmoviediscart',
    ]
    return any(settings.getSettingBool(s) for s in fanarttv_settings)

def filter_fanarttv_artwork(artwork_dict, settings):
    """Filter fanart.tv artwork results based on per-type settings."""
    if not artwork_dict or 'available_art' not in artwork_dict:
        return artwork_dict

    type_to_setting = {
        'poster': 'fanarttvposter',
        'keyart': 'fanarttvkeyart',
        'fanart': 'fanarttvfanart',
        'clearlogo': 'fanarttvclearlogo',
        'clearart': 'fanarttvclearart',
        'banner': 'fanarttvmoviebanner',
        'landscape': 'fanarttvmovielandscape',
        'discart': 'fanarttvmoviediscart',
        'set.poster': 'fanarttvsetposter',
        'set.keyart': 'fanarttvsetposter',
        'set.fanart': 'fanarttvsetfanart',
        'set.clearlogo': 'fanarttvsetclearlogo',
        'set.clearart': 'fanarttvsetclearart',
        'set.banner': 'fanarttvsetmoviebanner',
        'set.landscape': 'fanarttvsetmovielandscape',
        'set.discart': 'fanarttvsetmoviediscart',
    }

    filtered = {}
    for arttype, artlist in artwork_dict['available_art'].items():
        setting_id = type_to_setting.get(arttype)
        if setting_id is None or settings.getSettingBool(setting_id):
            filtered[arttype] = artlist
    artwork_dict['available_art'] = filtered
    return artwork_dict


def _configure_rating_prefix(details, settings):
    if details['info'].get('mpaa'):
        details['info']['mpaa'] = settings.getSettingString('certprefix') + details['info']['mpaa']
    return details

def _configure_keeporiginaltitle(details, settings):
    if settings.getSettingBool('keeporiginaltitle'):
        details['info']['title'] = details['info']['originaltitle']
    return details

def _configure_trailer(details, settings):
    if details['info'].get('trailer') and not settings.getSettingBool('trailer'):
        del details['info']['trailer']
    return details

def _configure_multiple_studios(details, settings):
    if not settings.getSettingBool('multiple_studios'):
        details['info']['studio'] = details['info']['studio'][:1]
    return details

def _configure_multiple_countries(details, settings):
    if not settings.getSettingBool('multiple_countries'):
        if details['info'].get('country'):
            details['info']['country'] = details['info']['country'][:1]
    return details

def _configure_default_rating(details, settings):
    default_source = settings.getSettingString('mratingsource')
    source_to_key = {
        'IMDb': 'imdb',
        'themoviedb.org': 'themoviedb',
        'Trakt': 'trakt',
        'Rotten Tomatoes': 'rottentomatoes',
        'Top Critics': 'rottentomatoes_topcritics',
        'Popcornmeter': 'rottentomatoes_audience',
        'MetaCritic': 'metacritic',
    }
    default_rating = source_to_key.get(default_source, 'themoviedb')
    if default_rating not in details['ratings']:
        default_rating = list(details['ratings'].keys())[0] if details['ratings'] else None
    for rating_type in details['ratings'].keys():
        details['ratings'][rating_type]['default'] = rating_type == default_rating
    return details

def _configure_tags(details, settings):
    if not settings.getSettingBool('add_tags'):
        del details['info']['tag']
    elif settings.getSettingBool('enable_tag_whitelist'):
        whitelist = set(tag.strip().lower() for tag in settings.getStringList('tag_whitelist'))
        details['info']['tag'] = [tag for tag in details['info']['tag'] if tag.lower() in whitelist]
    return details


# pylint: disable=invalid-name
try:
    basestring
except NameError:  # py2 / py3
    basestring = str

#pylint: disable=redefined-builtin
class PathSpecificSettings(object):
    # read-only shim for typed `xbmcaddon.Addon().getSetting*` methods
    def __init__(self, settings_dict, log_fn):
        self.data = settings_dict
        self.log = log_fn

    def getSettingBool(self, id):
        return self._inner_get_setting(id, bool, False)

    def getSettingInt(self, id):
        return self._inner_get_setting(id, int, 0)

    def getSettingNumber(self, id):
        return self._inner_get_setting(id, float, 0.0)

    def getSettingString(self, id):
        return self._inner_get_setting(id, basestring, '')

    def getStringList(self, id):
        return self._inner_get_setting(id, list, [])

    def _inner_get_setting(self, setting_id, setting_type, default):
        value = self.data.get(setting_id)
        if isinstance(value, setting_type):
            return value
        self._log_bad_value(value, setting_id)
        return default

    def _log_bad_value(self, value, setting_id):
        if value is None:
            self.log("requested setting ({0}) was not found.".format(setting_id))
        else:
            self.log('failed to load value "{0}" for setting {1}'.format(value, setting_id))
