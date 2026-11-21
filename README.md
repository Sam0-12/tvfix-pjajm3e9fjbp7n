# TV channel fixes

`overrides.json` is read by the Live TV app on the TV (set at build time with
`OVERRIDES_URL=https://raw.githubusercontent.com/<owner>/<repo>/main/overrides.json`). Edit it on
GitHub and the TV picks the change up the next time it reloads the playlist (on app start, or per its
"reload every" setting). No new APK needed. A file the app can't read, or whose `version` isn't 1,
is ignored and the last good copy is kept.

| Key | What it does |
|---|---|
| `backups` | `{"Channel name": [urls]}` streams added after the channel's own, as fallbacks |
| `streams` | `{"Channel name": [urls]}` streams tried first |
| `remove_streams` | `[urls]` dead links removed from every channel; a channel left with none disappears |
| `add` | `[{"name", "section", "logo", "streams": [...]}]` new channels (or extra streams for an existing one) |
| `rename` | `{"Old name": "New name"}` |
| `move` | `{"Channel name": "Section"}` (News, Entertainment, Movies, Music, Sports, Kids, ... as in the app) |
| `hide` | `["Channel name"]` remove a channel from the list |
| `logos` | `{"Channel name": "https://logo.png"}` |
| `epg` | `[{"url": "...xml.gz", "shift": minutes}]` TV guide files, replacing the built-in four |
| `catalog` | https address of a different playlist catalog CSV |

Channel names are matched ignoring case, `HD`, brackets and punctuation ("DD News" matches "DD News HD").

A weekly GitHub Action (`check_links.py`) opens an issue listing dead links and channels with nothing
working. It only reports: GitHub's servers are outside India, so a geo-blocked stream looks dead from
there. Put a link in `remove_streams` yourself once you know it is dead on the TV.
