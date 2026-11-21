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
| `apps` | `{"live-tv": {...}, "iptv-live": {...}}` the same keys again, applied only to that app (Live TV and its parents' version are `live-tv`). Maps are merged, lists joined. Use it for what differs: `move` and `add` (the apps' sections differ) and `epg` |
| `catalog` | https address of a different playlist catalog CSV |

Channel names are matched ignoring case, `HD`, brackets and punctuation ("DD News" matches "DD News HD").

`check_links.py` tests every link and lists dead ones. It is not scheduled: GitHub's servers are in the
US, so it reports geo-blocked streams as dead. Run it by hand from the Actions tab if you want, or scan
from a home connection and edit this file by hand. Put a link in `remove_streams` once you know it is
dead on the TV. `scan.yml` runs on every push and fails if the file holds a subscription link.

## IPTV Live (paid subscription)

IPTV Live reads this same file, but **never put a subscription link in it**: the repo is public. The
subscription's server, username and password are typed into the app on the TV and stay there. The
file can only add free backup streams (`backups`, placed after the paid stream), rename, move, hide or
re-logo channels, and so on. The `scan.yml` action fails a push that contains something that looks like
an Xtream link (`/live/user/pass/id.ts`, `get.php`, `username=`...). `epg` there accepts plain
addresses only (a file with a `shift` is skipped), and `catalog` is ignored.
