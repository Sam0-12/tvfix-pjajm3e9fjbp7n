#!/usr/bin/env python3
"""Fails if overrides.json looks like it holds an IPTV subscription: this repo is public, and the
subscription (server, username, password) must only ever be typed into the app on the TV."""
import re, sys
t = open('overrides.json').read()
bad = [r'/live/[^/"\s]+/[^/"\s]+/\d+\.(ts|m3u8)', r'/(movie|series)/[^/"\s]+/[^/"\s]+/', r'get\.php\?', r'player_api\.php',
       r'[?&](username|password|user|pass|token)=', r'/\w+/\w+/\d+\.(ts|m3u8)\b']
hits = [p for p in bad if re.search(p, t, re.I)]
if hits:
    print('overrides.json looks like it contains subscription links or credentials:', hits)
    sys.exit(1)
print('ok: nothing that looks like a subscription link')
