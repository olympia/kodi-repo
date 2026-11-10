import json
import sys
from pathlib import Path
import xml.etree.ElementTree as ET
import xbmc
import xbmcgui
import xbmcvfs

PLAYLIST = 'special://profile/playlists/video/confluence_olympia_movie_sources.xsp'
CONFIG = 'special://profile/addon_data/skin.confluence.olympia/movie_sources.json'


def sources():
    root = ET.parse(xbmcvfs.translatePath('special://profile/sources.xml')).getroot()
    return [(s.findtext('name', ''), [p.text for p in s.findall('path') if p.text]) for s in root.findall('./video/source') if s.findtext('name') and any(p.text for p in s.findall('path'))]


def load_names():
    try:
        return json.loads(Path(xbmcvfs.translatePath(CONFIG)).read_text()).get('sources', [])
    except (OSError, ValueError):
        return []


def make_playlist(selected):
    root = ET.Element('smartplaylist', {'type': 'movies'})
    ET.SubElement(root, 'name').text = 'Titles'
    ET.SubElement(root, 'match').text = 'one'
    for name, paths in selected:
        for path in paths:
            rule = ET.SubElement(root, 'rule', {'field': 'path', 'operator': 'startswith'})
            ET.SubElement(rule, 'value').text = path
    ET.SubElement(root, 'group', {'mixed': 'true'}).text = 'sets'
    ET.SubElement(root, 'order', {'direction': 'ascending'}).text = 'sorttitle'
    return root


def apply_selection(selected):
    names = [name for name, paths in selected]
    config = Path(xbmcvfs.translatePath(CONFIG))
    config.parent.mkdir(parents=True, exist_ok=True)
    config.write_text(json.dumps({'sources': names}))
    label = ', '.join(names) if names else 'All sources'
    label = label.replace(chr(34), chr(39)).replace(chr(10), ' ').replace(chr(13), ' ')
    if selected:
        root = make_playlist(selected)
        ET.indent(root)
        file = Path(xbmcvfs.translatePath(PLAYLIST))
        file.parent.mkdir(parents=True, exist_ok=True)
        temp = file.with_suffix('.xsp.tmp')
        ET.ElementTree(root).write(temp, encoding='utf-8', xml_declaration=True)
        temp.replace(file)
        xbmc.executebuiltin('Skin.Reset(HomeMenuMovieUsePlaylist)', True)
        xbmc.executebuiltin('Skin.SetBool(HomeMenuMovieUseSources)', True)
    else:
        xbmc.executebuiltin('Skin.Reset(HomeMenuMovieUseSources)', True)
    xbmc.executebuiltin('Skin.SetString(HomeMenuMovieSourcesLabel,"' + label + '")', True)


def main():
    available = sources()
    if not available:
        xbmcgui.Dialog().ok('Movies sources', 'No video sources found.')
        return
    selected_names = load_names()
    if len(sys.argv) > 1 and sys.argv[1] == 'toggle':
        if xbmc.getCondVisibility('Skin.HasSetting(HomeMenuMovieUseSources)'):
            xbmc.executebuiltin('Skin.Reset(HomeMenuMovieUseSources)', True)
            return
        selected = [item for item in available if item[0] in selected_names]
        if selected:
            apply_selection(selected)
            return
    choices = xbmcgui.Dialog().multiselect('Movies: included sources (none = all)', [name for name, paths in available], preselect=[i for i, item in enumerate(available) if item[0] in selected_names])
    if choices is None:
        return
    apply_selection([available[i] for i in choices])


if __name__ == '__main__':
    main()
