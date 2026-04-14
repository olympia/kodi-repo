def get_imdb_id(uniqueids):
    """Extract IMDb ID from uniqueids dict."""
    imdb_id = uniqueids.get('imdb')
    if imdb_id and imdb_id.startswith('tt'):
        return imdb_id
    return None
