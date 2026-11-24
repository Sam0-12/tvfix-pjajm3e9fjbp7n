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
| `epg` | `[{"url": "...xml.gz", "shift": minutes}]` TV guide files, replacing the built-in four. Live TV's list starts with this repo's merged guide (see below), then JioTV, epg.pw, open-epg and the dead-but-kept Tata Play as fallbacks |
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

## Merged TV guide (`epg.xml.gz`)

No single free guide covers the channels or the days, and the big ones (40-80 MB unpacked) are too heavy for a
TV. `build_epg.py` downloads them all (the list is `epg_sources.json`), shifts the ones that label their times
wrongly, matches their channel names to the channels the app shows, merges per channel (the source with the
most coverage of the next 48 hours first, the others filling in after it) and writes one small file with times
in UTC: about 0.4 MB gzipped, 260 of the 397 channels. The `epg.yml` Action rebuilds it four times a day and
publishes it, as a single replaced commit, on the `epg-data` branch:
`https://raw.githubusercontent.com/Sam0-12/tvfix-pjajm3e9fjbp7n/epg-data/epg.xml.gz`. It is the first entry of
`apps.live-tv.epg` in `overrides.json`. The app reads the first guide that has upcoming programmes for a
channel, so if the Action ever stops the file goes stale and the app falls back to the next entry by itself.
A run that finds fewer than `min_channels` channels fails and leaves the last good file in place.

- **Add a provider:** one more entry in `epg_sources.json` (`url`; `shift_minutes` if it labels its times wrongly;
  `strip_prefix` for a name prefix such as "IN - "). Before adding one, check its times against JioTV: two
  open-epg files (india3, india5) were rejected because their times are off by 1.5 and 3.5 hours.
- **A channel the guide spells differently** ("Aradhana TV" vs "Aradana TV"): add it to `aliases` (guide name
  key -> the app's name key). No rename, no app change.
- **Run it by hand:** `python3 build_epg.py out.xml.gz`, or "Run workflow" on the Actions tab.
- Times are absolute, so the TV's own time zone only decides how they are displayed: set the parents' TV to India
  (Kolkata, GMT+5:30).
