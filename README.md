# Olympia's Kodi Repository

Custom Kodi addon repository. Home of the **Universal Movie Scraper**.

## Hosted addons

| Addon | ID |
|---|---|
| Universal Movie Scraper | `metadata.universal.python` |

## How to install in Kodi

1. Download the latest repo zip: [repository.olympia-1.0.0.zip](https://olympia.github.io/kodi-repo/repository.olympia/repository.olympia-1.0.0.zip)
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
│   └── repository.olympia-1.0.0.zip      ← generated
├── metadata.universal.python/
│   ├── addon.xml                          ← your addon's descriptor
│   ├── ... (addon source files)
│   └── metadata.universal.python-x.y.z.zip  ← generated
└── README.md
```
