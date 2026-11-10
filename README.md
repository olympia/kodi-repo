# Olympia's Kodi Repository

Custom Kodi addon repository. Home of the **Universal Movie Scraper** and **Confluence Olympia** for Kodi 21 Omega.

## Hosted addons

| Addon | ID |
|---|---|
| Universal Movie Scraper | `metadata.universal.python` |
| Confluence Olympia (Kodi 21 Omega) | `skin.confluence.olympia` |

## How to install in Kodi

1. Download the latest repo zip: [repository.olympia-1.1.0.zip](https://olympia.github.io/kodi-repo/repository.olympia/repository.olympia-1.1.0.zip)
2. In Kodi: **Settings → Add-ons → Install from zip file** → select the downloaded zip
3. Then: **Install from repository → Olympia's Repository** → browse and install addons

## How to update the repo (for maintainers)

### Adding / updating an addon

1. Place the addon source in a directory named after its addon ID (e.g. `metadata.universal.python/`)
2. Make sure the directory contains a valid `addon.xml`
3. Run the generator:
   ```bash
   python _generator.py
   ```
4. Commit and push:
   ```bash
   git add -A
   git commit -m "Update metadata.universal.python to x.y.z"
   git push
   ```

### First-time GitHub Pages setup

1. Go to the repo **Settings → Pages**
2. Set source to **Deploy from a branch**
3. Select the `main` branch and `/ (root)` folder
4. Save — the repo will be live at `https://olympia.github.io/kodi-repo/`

## Structure

```
kodi-repo/
├── _generator.py                          ← run this to rebuild
├── addons.xml                             ← generated: combined addon metadata
├── addons.xml.md5                         ← generated: checksum
├── repository.olympia/
│   ├── addon.xml
│   └── repository.olympia-1.1.0.zip      ← generated
├── metadata.universal.python/
│   ├── addon.xml                          ← your addon's descriptor
│   ├── ... (addon source files)
│   └── metadata.universal.python-x.y.z.zip  ← generated
└── README.md
```

## Confluence Olympia (Omega only)

The skin is published in `omega/addons.xml`, served only when Kodi's repository API
version is between 21.0.0 and 21.9.999. The general index continues serving the scraper
and repository addon to their supported Kodi versions. Update Olympia's Repository
to **1.1.0** to discover the additional Omega channel.

In Kodi 21: Install from repository -> Olympia's Repository -> Look and feel -> Skin
-> Confluence Olympia. Select it in Settings -> Interface -> Skin. It has independent
settings and can coexist with the original Confluence.

Skin sources: `skin.confluence.olympia/`. The generator packages these sources and
updates both index/checksum pairs; CI commits the generated artifacts. Bump the skin
version in addon.xml for each release. Existing release archives remain available.
See the skin README and CHANGELOG.txt for features and upstream license credits.
