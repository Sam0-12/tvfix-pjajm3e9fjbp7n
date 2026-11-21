#!/usr/bin/env python3
"""Reports dead stream links: every link in overrides.json, plus every Indian English/Hindi/Marathi
link in the iptv-org playlists the app reads. Writes dead_links.md (empty file when all is well).
Report only: GitHub's servers are outside India, so a geo-blocked stream looks dead from here but may
play on the TV. Remove a link by hand: add it to "remove_streams" in overrides.json."""
import json, re, sys, time, urllib.request, concurrent.futures as cf

UA = {'User-Agent': 'Mozilla/5.0'}
def fetch(u, n=None, t=15):
    r = urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=t)
    return r.read(n) if n else r.read()
def fetch_retry(u, tries=4):
    for i in range(tries):
        try: return fetch(u, t=120)
        except Exception:
            if i == tries - 1: raise
            time.sleep(5 * (i + 1))
def alive(u):
    try: return '#EXT' in fetch(u, 4096, 12).decode('utf-8', 'ignore')
    except Exception: return False

ov = json.load(open('overrides.json'))
mine = {}  # url -> where it is listed
for k, v in ov.get('backups', {}).items():
    for u in v: mine[u] = f'backups / {k}'
for k, v in ov.get('streams', {}).items():
    for u in v: mine[u] = f'streams / {k}'
for a in ov.get('add', []):
    for u in a.get('streams', []): mine[u] = f"add / {a.get('name')}"

lists = {'in': 'https://raw.githubusercontent.com/iptv-org/iptv/HEAD/streams/in.m3u',
         'sports': 'https://iptv-org.github.io/iptv/categories/sports.m3u'}
langs = {c: f'https://iptv-org.github.io/iptv/languages/{c}.m3u' for c in ('eng', 'hin', 'mar')}
ids = set()
for u in langs.values():
    for l in fetch_retry(u).decode('utf-8', 'ignore').splitlines():
        m = re.search(r'tvg-id="([^"]*)"', l)
        if m: ids.add(m.group(1).split('@')[0].lower())
playlist = {}
for name, u in lists.items():
    gid = nm = ''
    for l in fetch_retry(u).decode('utf-8', 'ignore').splitlines():
        l = l.strip()
        if l.startswith('#EXTINF'):
            m = re.search(r'tvg-id="([^"]*)"', l); gid = (m.group(1) if m else '').split('@')[0].lower()
            nm = re.sub(r'\s*\(\d+[pi]\)|\s*\[.*?\]', '', l.rsplit(',', 1)[-1]).strip()
        elif l.startswith('http') and gid in ids and gid.endswith('.in'):
            playlist[l] = f'playlist / {nm}'

urls = list({**playlist, **mine})
with cf.ThreadPoolExecutor(60) as ex: ok = dict(zip(urls, ex.map(alive, urls)))
dead_mine = sorted((w, u) for u, w in mine.items() if not ok[u])
by_ch = {}
def key(n): return re.sub(r'[^a-z0-9]', '', re.sub(r'\bhd\b', '', re.sub(r'\(.*?\)|\[.*?\]', '', n.lower())))
names = {}
for u, w in playlist.items():
    n = w.split(' / ', 1)[1]; names.setdefault(key(n), n); by_ch.setdefault(key(n), []).append(u)
nolive = sorted(names[c] for c, us in by_ch.items() if not any(ok[u] for u in us))
out = []
if dead_mine:
    out.append('## Dead links in overrides.json\n' + '\n'.join(f'- {w}: {u}' for w, u in dead_mine))
if nolive:
    out.append('## Channels with no working link in the iptv-org playlists (add a backup)\n' + '\n'.join(f'- {c}' for c in nolive))
open('dead_links.md', 'w').write('\n\n'.join(out) + ('\n' if out else ''))
print(f'{len(urls)} links checked; {len(dead_mine)} dead in overrides.json; {len(nolive)} channels with nothing working')
