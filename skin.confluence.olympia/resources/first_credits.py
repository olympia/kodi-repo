import json
import uuid
import xbmc
import xbmcgui

window = xbmcgui.Window(10025)
token = str(uuid.uuid4())
window.setProperty('ConfluenceOlympia.CreditsOwner', token)
monitor = xbmc.Monitor()
last = None
cache = {}
try:
    while not monitor.abortRequested() and window.getProperty('ConfluenceOlympia.CreditsOwner') == token:
        if xbmcgui.getCurrentWindowId() != 10025:
            break
        movie_id, kind = xbmc.getInfoLabel('ListItem.DBID'), xbmc.getInfoLabel('ListItem.DBTYPE')
        key = (movie_id, kind)
        if key != last:
            for field in ('Director', 'Writer'):
                window.clearProperty('ConfluenceOlympia.First' + field)
            window.clearProperty('ConfluenceOlympia.Genres')
            window.setProperty('ConfluenceOlympia.IMDbRating', '-')
            window.setProperty('ConfluenceOlympia.RTAllCriticsRating', '')
            if kind == 'movie' and movie_id.isdigit():
                if movie_id not in cache:
                    reply = json.loads(xbmc.executeJSONRPC(json.dumps({'jsonrpc': '2.0', 'id': 1, 'method': 'VideoLibrary.GetMovieDetails', 'params': {'movieid': int(movie_id), 'properties': ['director', 'writer', 'ratings', 'genre']}})))
                    if 'error' in reply:
                        xbmc.log('Confluence first credits: ' + str(reply['error']), xbmc.LOGWARNING)
                        if monitor.waitForAbort(0.25):
                            break
                        continue
                    cache[movie_id] = reply.get('result', {}).get('moviedetails', {})
                details = cache[movie_id]
                window.setProperty('ConfluenceOlympia.Genres', ' / '.join(details.get('genre', [])[:3]))
                ratings = details.get('ratings', {})
                imdb = ratings.get('imdb', {}).get('rating')
                rt = ratings.get('rottentomatoes', {}).get('rating')
                window.setProperty('ConfluenceOlympia.IMDbRating', '{:.1f} ({:,})'.format(imdb, int(ratings.get('imdb', {}).get('votes', 0))) if imdb is not None else '-')
                window.setProperty('ConfluenceOlympia.RTAllCriticsRating', '{:.0f}%'.format(rt * 10) if rt is not None else '')
                for field in ('Director', 'Writer'):
                    names = details.get(field.lower(), [])
                    window.setProperty('ConfluenceOlympia.First' + field, names[0] if names else '')
            last = key
        if monitor.waitForAbort(0.1):
            break
finally:
    if window.getProperty('ConfluenceOlympia.CreditsOwner') == token:
        window.clearProperty('ConfluenceOlympia.CreditsOwner')
        for field in ('Director', 'Writer'):
            window.clearProperty('ConfluenceOlympia.First' + field)
