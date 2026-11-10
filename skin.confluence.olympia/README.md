# Confluence Olympia

A Confluence 5.0.9 fork for **Kodi 21 Omega**. Add-on ID: `skin.confluence.olympia`.

Install from Olympia's Repository under Look and feel -> Skin. The original Confluence
remains installed; select Confluence Olympia in Settings -> Interface -> Skin.
Settings are independent and are not automatically copied from another skin.

Home window options contains library-node submenu slots and a Movies source filter.
The source filter preserves collections alongside standalone movies. No sources or
personal paths are bundled. Choose your own video sources in the skin settings.

Artwork and rating fields require the corresponding library metadata. RT AllCritics
reads the `rottentomatoes` rating source (used by UMS Python); absent values are hidden.
The helper reads library data through Kodi JSON-RPC and does not modify media metadata.

This release is served through the repository's Omega-only index (Kodi 21.x).
The required skin API is `xbmc.gui` 5.17.0; Python API 3.0.0 is also declared.
Kodi core / thumbloader fixes are not included in this skin package.

## Credits and license

Based on Confluence by Jezz_X and Team Kodi:
https://github.com/xbmc/skin.confluence

Olympia modifications by Olympia. Distributed under GPL-2.0-or-later; see LICENSE.txt.
Original font licenses are retained in fonts/LICENSE.txt and fonts/LICENSE_2.txt.
