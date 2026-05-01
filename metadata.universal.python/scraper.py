import json
import sys
import xbmc
import xbmcaddon
import xbmcgui
import xbmcplugin

from lib.scrapers.tmdb import TMDBMovieScraper
from lib.scrapers.fanarttv import get_details as get_fanarttv_artwork
from lib.scrapers.imdbratings import get_details as get_imdb_details
from lib.scrapers.imdb_graphql import get_details as get_imdb_graphql_details
from lib.scrapers.imdb_dataset import needs_update as imdb_dataset_needs_update
from lib.scrapers.imdb_dataset import update_database as imdb_dataset_update
from lib.scrapers.traktratings import get_trakt_ratinginfo
from lib.scrapers.omdbapi import get_details as get_omdb_details
from lib.scrapers.rottentomatoes import get_rt_data
from scraper_datahelper import combine_scraped_details_info_and_ratings, \
    combine_scraped_details_available_artwork, find_uniqueids_in_text, get_params
from scraper_config import configure_scraped_details, PathSpecificSettings, \
    configure_tmdb_artwork, is_fanarttv_configured, filter_fanarttv_artwork

ADDON_SETTINGS = xbmcaddon.Addon()
ID = ADDON_SETTINGS.getAddonInfo('id')

def log(msg, level=xbmc.LOGDEBUG):
    xbmc.log(msg='[{addon}]: {msg}'.format(addon=ID, msg=msg), level=level)

def _ensure_imdb_dataset(settings):
    """Check if the IMDb dataset needs updating, and trigger a background update if so."""
    max_age = settings.getSettingInt('imdb_dataset_update_days')
    if max_age < 1:
        max_age = 7
    if imdb_dataset_needs_update(max_age):
        log('IMDb ratings cache needs update, starting download...', xbmc.LOGINFO)
        dialog = xbmcgui.DialogProgressBG()
        dialog.create('Universal Movie Scraper', 'Caching IMDb ratings locally...')
        try:
            def progress_cb(pct, msg):
                dialog.update(pct, 'Universal Movie Scraper', msg)
            success = imdb_dataset_update(progress_callback=progress_cb)
            if success:
                log('IMDb dataset update completed successfully', xbmc.LOGINFO)
            else:
                log('IMDb dataset update failed', xbmc.LOGWARNING)
        finally:
            dialog.close()

def get_tmdb_scraper(settings):
    language = settings.getSettingString('language')
    certcountry = settings.getSettingString('tmdbcertcountry')
    search_language = settings.getSettingString('searchlanguage')
    plot_language = settings.getSettingString('plotlanguage') if settings.getSettingString('plotsource') == 'themoviedb.org' else language
    tagline_language = settings.getSettingString('taglinelanguage') if settings.getSettingString('taglinesource') == 'themoviedb.org' else language
    plot_language = plot_language or language
    tagline_language = tagline_language or language
    set_language = settings.getSettingString('tmdbsetlanguage') or language
    genres_language = settings.getSettingString('tmdbgenreslanguage') if settings.getSettingString('genressource') == 'themoviedb.org' else language
    genres_language = genres_language or language
    originaltitle_language = settings.getSettingString('originaltitlelanguage') or 'Original'
    artwork_language = settings.getSettingString('tmdbthumblanguage') or 'en'
    trailer_language = settings.getSettingString('trailerlanguage') or language
    fetch_sets = settings.getSettingBool('tmdbset')
    return TMDBMovieScraper(ADDON_SETTINGS, language, certcountry, search_language,
                            plot_language=plot_language, tagline_language=tagline_language,
                            set_language=set_language, genres_language=genres_language,
                            originaltitle_language=originaltitle_language,
                            artwork_language=artwork_language,
                            trailer_language=trailer_language,
                            fetch_sets=fetch_sets)

def _build_imdb_fallback_details(imdb_id, include_spoilers=False):
    log('TMDb lookup failed, attempting IMDb fallback for {}'.format(imdb_id), xbmc.LOGINFO)
    imdb_gql = get_imdb_graphql_details({'imdb': imdb_id}, include_spoilers=include_spoilers)
    if not imdb_gql or 'error' in imdb_gql:
        log('IMDb fallback failed: {}'.format(
            imdb_gql.get('error', 'no data') if imdb_gql else 'no response'), xbmc.LOGWARNING)
        return None

    gql_info = imdb_gql.get('info', {})
    title = gql_info.get('title', '')
    if not title:
        log('IMDb fallback: no title found for {}'.format(imdb_id), xbmc.LOGWARNING)
        return None

    info = {
        'title': title,
        'originaltitle': title,
        'plot': gql_info.get('plot', ''),
        'tagline': gql_info.get('tagline', ''),
        'studio': [],
        'genre': gql_info.get('genres', []),
        'country': gql_info.get('countries', []),
        'credits': imdb_gql.get('writers', []),
        'director': imdb_gql.get('directors', []),
        'premiered': gql_info.get('premiered', ''),
        'tag': [],
    }

    if gql_info.get('outline'):
        info['plotoutline'] = gql_info['outline']

    if gql_info.get('top250'):
        info['top250'] = gql_info['top250']

    certs = imdb_gql.get('certifications', {})
    if certs:
        info['_imdb_certifications'] = certs

    ratings = {}
    if imdb_gql.get('ratings', {}).get('imdb'):
        ratings['imdb'] = imdb_gql['ratings']['imdb']

    available_art = {}
    poster_url = gql_info.get('poster_url')
    if poster_url:
        available_art['poster'] = [{'url': poster_url, 'preview': poster_url, 'lang': None}]

    return {
        'info': info,
        'ratings': ratings,
        'uniqueids': {'imdb': imdb_id},
        'cast': imdb_gql.get('cast', []),
        'available_art': available_art,
        '_info': {'set_tmdbid': None},
    }

def search_for_movie(title, year, handle, settings):
    log("Find movie with title '{title}' from year '{year}'".format(title=title, year=year), xbmc.LOGINFO)
    title = _strip_trailing_article(title)
    scraper = get_tmdb_scraper(settings)

    search_results = scraper.search(title, year)
    if year is not None:
        if not search_results:
            search_results = scraper.search(title, str(int(year) - 1))
        if not search_results:
            search_results = scraper.search(title, str(int(year) + 1))
        if not search_results:
            search_results = scraper.search(title)
    if not search_results:
        return

    if 'error' in search_results:
        header = "Universal Movie Scraper error searching with TMDB"
        xbmcgui.Dialog().notification(header, search_results['error'], xbmcgui.NOTIFICATION_WARNING)
        log(header + ': ' + search_results['error'], xbmc.LOGWARNING)
        return

    for movie in search_results:
        listitem = _searchresult_to_listitem(movie)
        uniqueids = {'tmdb': str(movie['id'])}
        xbmcplugin.addDirectoryItem(handle=handle, url=build_lookup_string(uniqueids),
            listitem=listitem, isFolder=True)

_articles = [prefix + article for prefix in (', ', ' ') for article in ("the", "a", "an")]
def _strip_trailing_article(title):
    title = title.lower()
    for article in _articles:
        if title.endswith(article):
            return title[:-len(article)]
    return title

def _searchresult_to_listitem(movie):
    movie_label = movie['title']
    movie_year = movie['release_date'].split('-')[0] if movie.get('release_date') else None
    if movie_year:
        movie_label += ' ({})'.format(movie_year)

    listitem = xbmcgui.ListItem(movie_label, offscreen=True)
    infotag = listitem.getVideoInfoTag()
    infotag.setTitle(movie['title'])
    if movie_year:
        infotag.setYear(int(movie_year))
    if movie['poster_path']:
        listitem.setArt({'thumb': movie['poster_path']})
    return listitem

def add_artworks(listitem, artworks, IMAGE_LIMIT):
    infotag = listitem.getVideoInfoTag()
    for arttype, artlist in artworks.items():
        if arttype == 'fanart':
            continue
        for image in artlist[:IMAGE_LIMIT]:
            infotag.addAvailableArtwork(image['url'], arttype)

    fanart_to_set = [{'image': image['url'], 'preview': image['preview']}
        for image in artworks.get('fanart', ())[:IMAGE_LIMIT]]
    if fanart_to_set:
        listitem.setAvailableFanart(fanart_to_set)

def get_details(input_uniqueids, handle, settings, fail_silently=False):
    if not input_uniqueids:
        return False

    _default_rating = settings.getSettingString('mratingsource')
    _need_imdb_rating = (_default_rating == 'IMDb' or settings.getSettingBool('alsoimdb'))
    if _need_imdb_rating:
        _ensure_imdb_dataset(settings)

    details = get_tmdb_scraper(settings).get_details(input_uniqueids)
    _imdb_fallback = False
    if not details:
        imdb_id = input_uniqueids.get('imdb')
        if imdb_id and settings.getSettingBool('imdb_fallback'):
            _include_spoilers_fb = settings.getSettingBool('imdb_plot_include_spoilers')
            details = _build_imdb_fallback_details(imdb_id, include_spoilers=_include_spoilers_fb)
            if details:
                _imdb_fallback = True
                log('IMDb fallback succeeded for {}'.format(imdb_id), xbmc.LOGINFO)
                certs = details['info'].pop('_imdb_certifications', {})
                if certs:
                    cert_country = settings.getSettingString('tmdbcertcountry').upper()
                    cert_value = certs.get(cert_country, '')
                    if cert_value:
                        details['info']['mpaa'] = cert_value
                if not settings.getSettingBool('imdbtop250'):
                    details['info'].pop('top250', None)
        if not details:
            return False
    if 'error' in details:
        if fail_silently:
            return False
        header = "Universal Movie Scraper error with TMDB"
        xbmcgui.Dialog().notification(header, details['error'], xbmcgui.NOTIFICATION_WARNING)
        log(header + ': ' + details['error'], xbmc.LOGWARNING)
        return False

    details = configure_tmdb_artwork(details, settings)

    _default_rating = settings.getSettingString('mratingsource')

    if _default_rating == 'IMDb' or settings.getSettingBool('alsoimdb'):
        imdbinfo = get_imdb_details(details['uniqueids'])
        if imdbinfo:
            details = combine_scraped_details_info_and_ratings(details, imdbinfo)

    if _default_rating != 'themoviedb.org' and not settings.getSettingBool('alsotmdb'):
        details['ratings'].pop('themoviedb', None)

    if _default_rating == 'Trakt' or settings.getSettingBool('alsotrakt'):
        traktinfo = get_trakt_ratinginfo(details['uniqueids'])
        details = combine_scraped_details_info_and_ratings(details, traktinfo)

    _need_rt = (_default_rating == 'Rotten Tomatoes' or settings.getSettingBool('alsorotten'))
    _need_topcritics = (_default_rating == 'Top Critics' or
                        settings.getSettingBool('alsotopcritics'))
    _need_popcornmeter = (_default_rating == 'Popcornmeter' or
                          settings.getSettingBool('alsopopcornmeter'))
    _need_meta = (_default_rating == 'MetaCritic' or settings.getSettingBool('alsometa'))
    _outline_source = settings.getSettingString('outlinesource')
    _plot_source = settings.getSettingString('plotsource')
    _need_rt_consensus = (_outline_source == 'RottenTomatoes' or _plot_source == 'RottenTomatoes')
    _need_omdb = (_need_rt or _need_topcritics or _need_popcornmeter or
                  _need_meta or _need_rt_consensus)
    _omdb_result = None
    if _need_omdb:
        omdb_key = settings.getSettingString('omdbapikey') or settings.getSettingString('omdbapikey_outline')
        if omdb_key:
            _omdb_result = get_omdb_details(details['uniqueids'], omdb_key)
            if _omdb_result and 'error' not in _omdb_result:
                if _omdb_result.get('ratings'):
                    if _need_rt and 'rottentomatoes' in _omdb_result['ratings']:
                        details['ratings']['rottentomatoes'] = _omdb_result['ratings']['rottentomatoes']
                    if _need_meta and 'metacritic' in _omdb_result['ratings']:
                        details['ratings']['metacritic'] = _omdb_result['ratings']['metacritic']
            elif _omdb_result and 'error' in _omdb_result:
                log('OMDb error: ' + _omdb_result['error'], xbmc.LOGWARNING)
        else:
            if _need_rt or _need_topcritics or _need_popcornmeter or _need_meta:
                log('OMDb API key not set, cannot fetch RT/MetaCritic ratings',
                    xbmc.LOGWARNING)

    _need_rt_page = (_need_rt_consensus or _need_rt or _need_topcritics or _need_popcornmeter)
    _rt_data = None
    if _need_rt_page:
        rt_url = ''
        if _omdb_result and 'error' not in _omdb_result:
            omdb_info = _omdb_result.get('info', {})
            rt_url = omdb_info.get('rt_url', '')
        if rt_url:
            log('Scraping RT page: {}'.format(rt_url), xbmc.LOGINFO)
            _rt_data = get_rt_data(rt_url)

            if _need_rt and _rt_data and _rt_data.get('tomatometer') is not None:
                if 'rottentomatoes' not in details['ratings']:
                    details['ratings']['rottentomatoes'] = {'rating': 0.0, 'votes': 0}
                details['ratings']['rottentomatoes']['rating'] = \
                    float(_rt_data['tomatometer']) / 10.0
                if _rt_data.get('reviewcount'):
                    details['ratings']['rottentomatoes']['votes'] = _rt_data['reviewcount']
                log('Updated Tomatometer to {}% ({} reviews) from RT page'.format(
                    _rt_data['tomatometer'], _rt_data.get('reviewcount') or 0),
                    xbmc.LOGINFO)
            elif _need_rt and _rt_data and _rt_data.get('reviewcount'):
                if 'rottentomatoes' in details['ratings']:
                    details['ratings']['rottentomatoes']['votes'] = _rt_data['reviewcount']
                    log('Updated RT votes to {} (score from OMDb retained)'.format(
                        _rt_data['reviewcount']), xbmc.LOGINFO)

            if _need_topcritics and _rt_data and _rt_data.get('topcriticsscore') is not None:
                details['ratings']['rottentomatoes_topcritics'] = {
                    'rating': float(_rt_data['topcriticsscore']) / 10.0,
                    'votes': _rt_data.get('topcriticscount') or 0,
                }
                log('Set Top Critics to {}% ({} reviews) from RT page'.format(
                    _rt_data['topcriticsscore'], _rt_data.get('topcriticscount') or 0),
                    xbmc.LOGINFO)
            elif _need_topcritics:
                log('Top Critics requested but not found on RT page', xbmc.LOGWARNING)

            if _need_popcornmeter and _rt_data and _rt_data.get('audiencescore') is not None:
                details['ratings']['rottentomatoes_audience'] = {
                    'rating': float(_rt_data['audiencescore']) / 10.0,
                    'votes': _rt_data.get('audiencecount') or 0,
                }
                log('Set Popcornmeter to {}% ({} ratings) from RT page'.format(
                    _rt_data['audiencescore'], _rt_data.get('audiencecount') or 0),
                    xbmc.LOGINFO)
            elif _need_popcornmeter:
                log('Popcornmeter requested but not found on RT page', xbmc.LOGWARNING)

    if is_fanarttv_configured(settings):
        fanarttv_info = get_fanarttv_artwork(
            details['uniqueids'],
            settings.getSettingString('fanarttv_clientkey'),
            settings.getSettingString('fanarttvposterlanguage'),
            details['_info']['set_tmdbid'])
        fanarttv_info = filter_fanarttv_artwork(fanarttv_info, settings)
        ftv_lang = settings.getSettingString('fanarttvposterlanguage')
        tmdb_art_lang = settings.getSettingString('tmdbthumblanguage')
        details = combine_scraped_details_available_artwork(
            details, fanarttv_info,
            tmdb_art_lang,
            settings,
            fanarttv_language=ftv_lang)

    if not _imdb_fallback:
        _imdb_plot = _plot_source == 'IMDb'
        _imdb_tagline = settings.getSettingString('taglinesource') == 'IMDb'
        _imdb_outline = _outline_source == 'IMDb'
        _imdb_credits = settings.getSettingString('creditssource') == 'IMDb'
        _imdb_cert = settings.getSettingString('certsource') == 'IMDb'
        _imdb_genres = settings.getSettingString('genressource') == 'IMDb'
        _imdb_top250 = settings.getSettingBool('imdbtop250')
        _needs_imdb_graphql = (_imdb_plot or _imdb_tagline or _imdb_outline or
                               _imdb_credits or _imdb_cert or _imdb_genres or
                               _imdb_top250)

        imdb_gql = None
        if _needs_imdb_graphql:
            _include_spoilers = settings.getSettingBool('imdb_plot_include_spoilers')
            imdb_gql = get_imdb_graphql_details(details['uniqueids'],
                                                include_spoilers=_include_spoilers)
            if imdb_gql and 'error' not in imdb_gql:
                gql_info = imdb_gql.get('info', {})
                if _imdb_plot and gql_info.get('plot'):
                    details['info']['plot'] = gql_info['plot']
                if _imdb_tagline and gql_info.get('tagline'):
                    details['info']['tagline'] = gql_info['tagline']
                if _imdb_outline and gql_info.get('outline'):
                    details['info']['plotoutline'] = gql_info['outline']
                if _imdb_credits and imdb_gql.get('cast'):
                    details['cast'] = imdb_gql['cast']
                if _imdb_credits and imdb_gql.get('directors'):
                    details['info']['director'] = imdb_gql['directors']
                if _imdb_credits and imdb_gql.get('writers'):
                    details['info']['credits'] = imdb_gql['writers']
                if _imdb_cert and imdb_gql.get('certifications'):
                    cert_country = settings.getSettingString('tmdbcertcountry').upper()
                    cert_value = imdb_gql['certifications'].get(cert_country, '')
                    if cert_value:
                        details['info']['mpaa'] = cert_value
                if _imdb_genres and gql_info.get('genres'):
                    details['info']['genre'] = gql_info['genres']
                if _imdb_top250 and gql_info.get('top250'):
                    details['info']['top250'] = gql_info['top250']
            elif imdb_gql and 'error' in imdb_gql:
                log('IMDb GraphQL error: ' + imdb_gql['error'], xbmc.LOGWARNING)

    if _need_rt_consensus:
        consensus = ''
        if _rt_data:
            consensus = _rt_data.get('consensus', '')
        if not consensus and _omdb_result and 'error' not in _omdb_result:
            omdb_info = _omdb_result.get('info', {})
            consensus = omdb_info.get('rt_consensus', '')
            if not consensus:
                consensus = omdb_info.get('outline', '')
                if consensus:
                    log('Using OMDb short plot as RT consensus fallback', xbmc.LOGINFO)
        if consensus:
            if _outline_source == 'RottenTomatoes':
                details['info']['plotoutline'] = consensus
            if _plot_source == 'RottenTomatoes':
                details['info']['plot'] = consensus

    if settings.getSettingString('taglinesource') == 'None':
        details['info']['tagline'] = ''

    details = configure_scraped_details(details, settings)

    listitem = xbmcgui.ListItem(details['info']['title'], offscreen=True)
    infotag = listitem.getVideoInfoTag()
    set_info(infotag, details['info'])
    infotag.setCast(build_cast(details['cast']))
    infotag.setUniqueIDs(details['uniqueids'], 'tmdb')
    infotag.setRatings(build_ratings(details['ratings']), find_defaultrating(details['ratings']))
    IMAGE_LIMIT = settings.getSettingInt('maxartwork')
    add_artworks(listitem, details['available_art'], IMAGE_LIMIT)

    xbmcplugin.setResolvedUrl(handle=handle, succeeded=True, listitem=listitem)
    return True

def set_info(infotag, info_dict):
    infotag.setTitle(info_dict['title'])
    infotag.setOriginalTitle(info_dict['originaltitle'])
    infotag.setPlot(info_dict['plot'])
    infotag.setTagLine(info_dict['tagline'])
    if 'plotoutline' in info_dict:
        infotag.setPlotOutline(info_dict['plotoutline'])
    infotag.setStudios(info_dict['studio'])
    infotag.setGenres(info_dict['genre'])
    infotag.setCountries(info_dict['country'])
    infotag.setWriters(info_dict['credits'])
    infotag.setDirectors(info_dict['director'])
    infotag.setPremiered(info_dict['premiered'])
    if 'tag' in info_dict:
        infotag.setTags(info_dict['tag'])
    if 'mpaa' in info_dict:
        infotag.setMpaa(info_dict['mpaa'])
    if 'trailer' in info_dict:
        infotag.setTrailer(info_dict['trailer'])
    if 'set' in info_dict:
        infotag.setSet(info_dict['set'])
        infotag.setSetOverview(info_dict['setoverview'])
    if 'duration' in info_dict:
        infotag.setDuration(info_dict['duration'])
    if 'top250' in info_dict:
        infotag.setTop250(info_dict['top250'])

def build_cast(cast_list):
    return [xbmc.Actor(cast['name'], cast['role'], cast['order'], cast['thumbnail']) for cast in cast_list]

def build_ratings(rating_dict):
    return {key: (value['rating'], value.get('votes', 0)) for key, value in rating_dict.items()}

def find_defaultrating(rating_dict):
    return next((key for key, value in rating_dict.items() if value['default']), None)

def find_uniqueids_in_nfo(nfo, handle):
    uniqueids = find_uniqueids_in_text(nfo)
    if uniqueids:
        listitem = xbmcgui.ListItem(offscreen=True)
        xbmcplugin.addDirectoryItem(
            handle=handle, url=build_lookup_string(uniqueids), listitem=listitem, isFolder=True)

def build_lookup_string(uniqueids):
    return json.dumps(uniqueids)

def parse_lookup_string(uniqueids):
    try:
        return json.loads(uniqueids)
    except ValueError:
        log("Can't parse this lookup string, is it from another add-on?\n" + uniqueids, xbmc.LOGWARNING)
        return None

def run():
    params = get_params(sys.argv[1:])
    enddir = True
    getdetails_failed = False
    if 'action' in params:
        settings = ADDON_SETTINGS if not params.get('pathSettings') else \
            PathSpecificSettings(json.loads(params['pathSettings']), lambda msg: log(msg, xbmc.LOGWARNING))
        action = params["action"]
        if action == 'find' and 'title' in params:
            search_for_movie(params["title"], params.get("year"), params['handle'], settings)
        elif action == 'getdetails' and ('url' in params or 'uniqueIDs' in params):
            unique_ids = parse_lookup_string(params.get('uniqueIDs') or params.get('url'))
            result = get_details(unique_ids, params['handle'], settings, fail_silently='uniqueIDs' in params)
            enddir = not result
            if not result:
                getdetails_failed = True
        elif action == 'NfoUrl' and 'nfo' in params:
            find_uniqueids_in_nfo(params["nfo"], params['handle'])
        else:
            log("unhandled action: " + action, xbmc.LOGWARNING)
    else:
        log("No action in 'params' to act on", xbmc.LOGWARNING)
    if enddir:
        xbmcplugin.endOfDirectory(params['handle'], succeeded=not getdetails_failed)

if __name__ == '__main__':
    run()
