import sys
from pathlib import Path
from urllib.parse import quote
import xml.etree.ElementTree as ET
import xbmc
import xbmcgui
import xbmcvfs


def discover_nodes(media):
    files = {}
    for special in ('special://xbmc/system/library/video/', 'special://profile/library/video/'):
        root = Path(xbmcvfs.translatePath(special))
        if root.is_dir():
            for file in root.rglob('*.xml'):
                files[file.relative_to(root).as_posix()] = file
    nodes = []
    for relative, file in files.items():
        try:
            node = ET.parse(file).getroot()
            if node.tag != 'node':
                continue
            is_filter = node.get('type') == 'filter' and node.findtext('content') == media
            is_folder = node.get('type') == 'folder' and relative.startswith(media + '/')
            if not (is_filter or is_folder):
                continue
            label = (node.findtext('label') or file.stem).strip()
            if label.isdigit():
                label = xbmc.getLocalizedString(int(label)) or label
            elif '$LOCALIZE[' in label:
                label = xbmc.getInfoLabel(label)
            path = 'library://video/' + quote(relative, safe='/')
            nodes.append((label, path, relative))
        except (ET.ParseError, OSError) as error:
            xbmc.log('Confluence node picker: ' + str(error), xbmc.LOGWARNING)
    return sorted(nodes, key=lambda item: (item[0].casefold(), item[2]))


def main():
    media = sys.argv[1] if len(sys.argv) > 1 else ''
    slot = sys.argv[2] if len(sys.argv) > 2 else ''
    if media not in ('movies', 'tvshows') or slot not in tuple(str(i) for i in range(1, 7)):
        return
    prefix = 'HomeMenuMovie' if media == 'movies' else 'HomeMenuTVShow'
    key = prefix + 'SubmenuNode' + slot
    nodes = discover_nodes(media)
    current = xbmc.getInfoLabel('Skin.String(' + key + ')')
    preselect = next((i + 1 for i, item in enumerate(nodes) if item[1] == current), 0)
    rows = [xbmcgui.ListItem(label='Default submenu item', label2='Restore the original entry')]
    rows += [xbmcgui.ListItem(label=label, label2=relative) for label, path, relative in nodes]
    choice = xbmcgui.Dialog().select(('Movies' if media == 'movies' else 'TV Shows') + ' submenu ' + slot, rows, preselect=preselect, useDetails=True)
    if choice < 0:
        return
    if choice == 0:
        xbmc.executebuiltin('Skin.Reset(' + key + ')')
        xbmc.executebuiltin('Skin.Reset(' + key + 'Label)')
        return
    label, path, relative = nodes[choice - 1]
    label = label.replace(chr(34), chr(39)).replace(chr(10), ' ').replace(chr(13), ' ')
    xbmc.executebuiltin('Skin.SetString(' + key + ',"' + path + '")')
    xbmc.executebuiltin('Skin.SetString(' + key + 'Label,"' + label + '")')


if __name__ == '__main__':
    main()
