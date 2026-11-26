#!/usr/bin/env python3
"""Builds epg.xml.gz: ONE small TV guide for the channels of the Live TV app, merged from many sources.

The big public guide files (some 40-80 MB unpacked) are too heavy for a TV to read, and each lacks some
channels or days. This downloads them all (epg_sources.json), shifts the ones that label their times wrongly,
matches their channel names to the channels the app shows (the same name rule as the app's channelKey),
merges per channel (the source with the most coverage of the next 48 hours first, the rest filling in
after it), and writes a compact XMLTV file with times in UTC. Standard library only.

    python3 build_epg.py [out.xml.gz]      (default: epg.xml.gz)

Exits with an error, and writes nothing, when fewer than min_channels channels have a guide: the published
file then stays the last good one.
"""
import gzip, html, json, re, struct, sys, time, urllib.request
from datetime import datetime, timedelta, timezone

UA = {"User-Agent": "Mozilla/5.0 (tv-epg-builder)"}
CFG = json.load(open("epg_sources.json", encoding="utf-8"))


def fetch(url, tries=3, timeout=240):
    for i in range(tries):
        try:
            return urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout).read()
        except Exception as e:
            if i == tries - 1:
                raise
            time.sleep(4 * (i + 1))


def ckey(name):
    """The app's channelKey: 'Aaj Tak HD (1080p) [Geo-blocked]' -> 'aajtak'."""
    n = re.sub(r"\(.*?\)|\[.*?\]", "", name.lower())
    return re.sub(r"[^a-z0-9]", "", re.sub(r"\bhd\b", "", n))


def clean_name(name):
    return re.sub(r"\s*\[.*?\]", "", re.sub(r"\s*\(\d+[pi]\)", "", name)).strip()


def base_id(tvg):
    return tvg.split("@")[0].lower()


# ------------------------------------------------------------------ which channels the app has
def wanted_channels():
    """key -> name, as the app builds its list: Indian channels in English, Hindi or Marathi."""
    lang_ids = set()
    for u in CFG["language_lists"]:
        for m in re.finditer(r'tvg-id="([^"]*)"', fetch(u).decode("utf-8", "ignore")):
            lang_ids.add(base_id(m.group(1)))
    out = {}
    for u in CFG["playlists"]:
        sports = "sport" in u
        for line in fetch(u).decode("utf-8", "ignore").splitlines():
            if not line.startswith("#EXTINF"):
                continue
            m = re.search(r'tvg-id="([^"]*)"', line)
            base = base_id(m.group(1)) if m else ""
            if base not in lang_ids or (sports and not base.endswith(".in")):
                continue
            name = clean_name(line.rsplit(",", 1)[-1])
            if ckey(name):
                out.setdefault(ckey(name), name)
    for name in CFG.get("extra_names", []):
        out.setdefault(ckey(name), name)
    # channels the overrides file adds or renames
    try:
        ov = json.load(open("overrides.json", encoding="utf-8"))
        extra = list(ov.get("rename", {}).values())
        for a in [ov] + list(ov.get("apps", {}).values()):
            extra += [x.get("name", "") for x in a.get("add", []) if isinstance(x, dict)]
        for name in extra:
            if isinstance(name, str) and ckey(name):
                out.setdefault(ckey(name), name)
    except Exception:
        pass
    return out


# ------------------------------------------------------------------ reading a guide file
_chan = re.compile(r'<channel id="([^"]*)">(.*?)</channel>', re.S)
_dn = re.compile(r"<display-name[^>]*>(.*?)</display-name>", re.S)
_prog = re.compile(r"<programme([^>]*)>(.*?)</programme>", re.S)
_start = re.compile(r'start="(\d{14}) ?([+-]\d{4})?"')
_stop = re.compile(r'stop="(\d{14}) ?([+-]\d{4})?"')
_cattr = re.compile(r'channel="([^"]*)"')
_title = re.compile(r"<title[^>]*>(.*?)</title>", re.S)
_desc = re.compile(r"<desc[^>]*>(.*?)</desc>", re.S)


def text(s):
    s = s.strip()
    if s.startswith("<![CDATA["):
        s = s[9:-3]
    return html.unescape(s).strip()


def to_ms(s, zone):
    d = datetime.strptime(s, "%Y%m%d%H%M%S").replace(tzinfo=timezone.utc)
    if zone:
        off = timedelta(hours=int(zone[1:3]), minutes=int(zone[3:5]))
        d = d - off if zone[0] == "+" else d + off
    return int(d.timestamp() * 1000)


def label_shift_ms(raw, xml):
    """Minutes the file's times are ahead of what they claim (the app's _labelShift): the <tv date> is in the same
    wrong labelling as the times, the gzip header holds the real UTC time the file was written."""
    mtime = struct.unpack("<I", raw[4:8])[0] * 1000 if len(raw) > 8 and raw[:2] == b"\x1f\x8b" else 0
    m = re.search(r'<tv[^>]*date="(\d{14}) ?([+-]\d{4})?"', xml)
    if not mtime or not m:
        return 0
    h = 3600 * 1000
    shift = round((to_ms(m.group(1), m.group(2)) - mtime) / h) * h
    return shift if abs(shift) <= 14 * h else 0


def read_source(src, wanted, aliases, w0, w1):
    """-> {our key: [[startMs, stopMs, title, desc], ...]} within the window, plus a stats line."""
    raw = fetch(src["url"])
    xml = (gzip.decompress(raw) if raw[:2] == b"\x1f\x8b" else raw).decode("utf-8", "ignore")
    shift = src["shift_minutes"] * 60000 if "shift_minutes" in src else label_shift_ms(raw, xml)
    strip = re.compile(src["strip_prefix"]) if src.get("strip_prefix") else None
    rename = src.get("rename", {})   # exact guide channel name -> the app's name (only these are read)
    id_keys = {}   # guide channel id -> our keys
    for m in _chan.finditer(xml):
        for n in _dn.finditer(m.group(2)):
            name = re.sub(r"\.in$", "", text(n.group(1)))
            if name in rename:
                name = rename[name]
            elif src.get("only_renamed"):
                continue   # a foreign guide: its other channels must not be matched to Indian ones of the same name
            elif strip:
                name = strip.sub("", name)
            k = ckey(name)
            if not k:
                continue
            ours = set()
            if k in wanted:
                ours.add(k)
            a = aliases.get(k, [])
            for x in ([a] if isinstance(a, str) else a):
                if x in wanted:
                    ours.add(x)
            m2 = re.match(r"^sonysportsten(\d)(hindi)?$", k)
            if m2 and ("sonyten" + m2.group(1)) in wanted:
                ours.add("sonyten" + m2.group(1))
            if ours:
                id_keys.setdefault(html.unescape(m.group(1)), set()).update(ours)
    by_id = {}
    for m in _prog.finditer(xml):
        attrs = m.group(1)
        a, b, c = _start.search(attrs), _stop.search(attrs), _cattr.search(attrs)
        if not (a and b and c):
            continue
        cid = html.unescape(c.group(1))
        if cid not in id_keys:
            continue
        st, sp = to_ms(a.group(1), a.group(2)) - shift, to_ms(b.group(1), b.group(2)) - shift
        if sp <= w0 or st >= w1:
            continue
        t = _title.search(m.group(2))
        if not t:
            continue
        title = text(t.group(1))
        if src.get("only_renamed") and title.lower() in ("no data", "no information"):
            continue
        d = _desc.search(m.group(2))
        desc = text(d.group(1)) if d else ""
        semi = desc.find(";")
        if semi >= 0 and title.startswith(desc[:semi].strip()):
            desc = desc[semi + 1:].strip()
        if len(desc) > 220:
            desc = desc[:219] + "…"
        by_id.setdefault(cid, []).append([st, sp, title, desc])
    out = {}
    for cid, progs in by_id.items():
        progs.sort()
        for k in id_keys[cid]:
            if k not in out or len(progs) > len(out[k]):
                out[k] = progs
    return out, f"shift {shift / 3600000:+.1f}h, {len(raw) / 1e6:.1f} MB, {len(out)} of our channels"


def coverage(progs, w0, w1):
    return sum(max(0, min(p[1], w1) - max(p[0], w0)) for p in progs)


def merge(cands, order, w0, w1):
    """The source with the most coverage first; later ones only add what starts after it ends."""
    best = max(cands, key=lambda s: (coverage(cands[s], w0, w1), -order[s]))
    merged = [list(p) for p in cands[best]]
    end = max((p[1] for p in merged), default=w0)
    for s in sorted((x for x in cands if x != best), key=lambda x: order[x]):
        for p in cands[s]:
            if p[0] >= end:
                merged.append(list(p))
                end = p[1]
    return merged, best


def esc(s):
    return html.escape(s, quote=False)


def main():
    out_path = sys.argv[1] if len(sys.argv) > 1 else "epg.xml.gz"
    now = int(time.time() * 1000)
    w0, w1 = now - CFG["hours_before"] * 3600000, now + CFG["hours_after"] * 3600000
    wanted = wanted_channels()
    print(f"channels the app has (by name key): {len(wanted)}")
    aliases = CFG.get("aliases", {})
    order = {s["name"]: i for i, s in enumerate(CFG["sources"])}
    per_channel = {}
    for src in CFG["sources"]:
        try:
            got, info = read_source(src, wanted, aliases, w0, w1)
        except Exception as e:
            print(f"  {src['name']:13} FAILED: {e}")
            continue
        print(f"  {src['name']:13} {info}")
        for k, progs in got.items():
            per_channel.setdefault(k, {})[src["name"]] = progs
    guide, used = {}, {}
    for k, cands in per_channel.items():
        merged, best = merge(cands, order, w0, w1)
        if merged:
            guide[k] = merged
            used[best] = used.get(best, 0) + 1
    covering_now = sum(1 for g in guide.values() if any(p[0] <= now < p[1] for p in g))
    print(f"channels with a guide: {len(guide)} of {len(wanted)}; on air now: {covering_now}; primary source: {used}")
    if len(guide) < CFG["min_channels"]:
        sys.exit(f"only {len(guide)} channels have a guide (< {CFG['min_channels']}): not writing {out_path}")
    fmt = lambda ms: datetime.fromtimestamp(ms / 1000, timezone.utc).strftime("%Y%m%d%H%M%S +0000")
    lines = ['<?xml version="1.0" encoding="UTF-8"?>',
             f'<tv generator-info-name="build_epg.py" date="{fmt(now)}">']
    for k in sorted(guide):
        lines.append(f'<channel id="{k}"><display-name>{esc(wanted[k])}</display-name></channel>')
    for k in sorted(guide):
        for st, sp, title, desc in guide[k]:
            d = f"<desc>{esc(desc)}</desc>" if desc else ""
            lines.append(f'<programme start="{fmt(st)}" stop="{fmt(sp)}" channel="{k}"><title>{esc(title)}</title>{d}</programme>')
    lines.append("</tv>")
    data = "\n".join(lines).encode("utf-8")
    with gzip.GzipFile(out_path, "wb", compresslevel=9, mtime=int(time.time())) as f:
        f.write(data)
    print(f"wrote {out_path}: {len(data) / 1e6:.2f} MB unpacked, {len(open(out_path, 'rb').read()) / 1e6:.2f} MB gzipped")


if __name__ == "__main__":
    main()
