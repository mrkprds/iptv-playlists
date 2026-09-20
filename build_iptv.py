#!/usr/bin/env python3
"""
Build merged IPTV playlists from iptv-org, in several sorting variants.

Produces (in OUT_DIR):
    iptv-flat.m3u            no groups at all - one long alphabetical list
    iptv-by-country.m3u      grouped by country     (PH, UK, US, ...)
    iptv-by-genre.m3u        grouped by genre       (News, Movies, ...)  [iptv-org's own tags]
    iptv-country-genre.m3u   grouped "PH - News"    country first, genre within
    iptv-genre-country.m3u   grouped "News - PH"    genre first, country within

Point UHF at whichever one you like; you can add more than one.

Requires: python3 only (stdlib).
Run:      python3 build_iptv.py
"""

import os
import re
import sys
import urllib.request

BASE = "https://iptv-org.github.io/iptv/"
OUT_DIR = os.path.dirname(os.path.abspath(__file__))
TIMEOUT = 45

# ---------------------------------------------------------------- sources ---
# label -> path (relative to BASE) or a full http(s) URL.  Label is what shows
# up as the group name.
# Comment out anything you don't want.

COUNTRIES = {
    "PH": "https://raw.githubusercontent.com/Harleythetech/IPHTV/refs/heads/main/ph.m3u",
    "UK": "countries/uk.m3u",       # note: "uk", NOT "gb"
    "US": "countries/us.m3u",
    "FR": "countries/fr.m3u",
    "DE": "countries/de.m3u",
    "NO": "countries/no.m3u",
    "ES": "countries/es.m3u",
    "IT": "countries/it.m3u",
    "PT": "countries/pt.m3u",
    "GR": "countries/gr.m3u",
    "TR": "countries/tr.m3u",
    "SG": "countries/sg.m3u",
    "MY": "countries/my.m3u",
    "TH": "countries/th.m3u",
    "ID": "countries/id.m3u",
    "VN": "countries/vn.m3u",
    "KR": "countries/kr.m3u",
    "JP": "countries/jp.m3u",
}

CATEGORIES = {
    "News": "categories/news.m3u",
    "Documentary": "categories/documentary.m3u",
    "Sports": "categories/sports.m3u",
}

# ---------------------------------------------------------------- options ---

# Drop entries tagged [Geo-blocked], except from the countries listed in
# GEO_KEEP. Geo-blocking is outward: a PH channel marked geo-blocked works
# fine from inside PH, but a UK one will not.
DROP_GEOBLOCKED = True
GEO_KEEP = {"PH"}

# Drop entries tagged [Not 24/7] (part-time regional stations).
DROP_PART_TIME = False

# Channels whose name matches any of these are dropped entirely.
# Shopping channels are the main offender in most country lists.
NAME_BLOCKLIST = [
    r"\bshop(ping)?\b",
    r"\bQVC\b",
    r"\bteleshop",
]

# ------------------------------------------------------------------ guts ---

# attrs are key="value" pairs; match them explicitly so a comma inside a quoted
# value (e.g. http-user-agent="... (KHTML, like Gecko) ...") does not end the attrs.
EXTINF_RE = re.compile(r'^#EXTINF:(?P<dur>-?\d+)(?P<attrs>(?:\s+[\w-]+="[^"]*")*)\s*,(?P<name>.*)$')
GROUP_RE = re.compile(r'group-title="(?P<g>[^"]*)"')
BLOCK_RE = [re.compile(p, re.I) for p in NAME_BLOCKLIST]


class Channel:
    __slots__ = ("name", "attrs", "genre", "origin", "extras", "url")

    def __init__(self, name, attrs, genre, origin, extras, url):
        self.name = name
        self.attrs = attrs        # attribute string, group-title stripped out
        self.genre = genre or "Other"
        self.origin = origin      # the label of the list it came from
        self.extras = extras      # #EXTVLCOPT / #EXTGRP lines - do not drop these
        self.url = url

    def render(self, group):
        head = f"#EXTINF:-1{self.attrs}"
        if group:
            head += f' group-title="{group}"'
        head += f",{self.name}"
        return "\n".join([head] + self.extras + [self.url])

    def sort_key(self):
        return self.name.lower()


def fetch(path):
    url = path if path.startswith(("http://", "https://")) else BASE + path
    req = urllib.request.Request(url, headers={"User-Agent": "playlist-builder/1.0"})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        return r.read().decode("utf-8", "replace")


def blocked(name):
    return any(rx.search(name) for rx in BLOCK_RE)


def parse(body, origin, is_country):
    """Yield Channel objects. Keeps #EXTVLCOPT lines, which carry the
    user-agent / referer some streams require."""
    lines = body.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        i += 1
        m = EXTINF_RE.match(line)
        if not m:
            continue

        name = m.group("name").strip()
        attrs = m.group("attrs")
        genre_m = GROUP_RE.search(attrs)
        genre = genre_m.group("g").strip() if genre_m else ""
        attrs = GROUP_RE.sub("", attrs).rstrip()
        if attrs and not attrs.startswith(" "):
            attrs = " " + attrs

        # gather any directive lines, then the URL
        extras, url = [], None
        while i < len(lines):
            nxt = lines[i].strip()
            i += 1
            if not nxt:
                continue
            if nxt.startswith("#EXTINF"):
                i -= 1
                break
            if nxt.startswith("#"):
                extras.append(nxt)
                continue
            url = nxt
            break

        if not url:
            continue
        if blocked(name):
            continue
        if DROP_GEOBLOCKED and "[Geo-blocked]" in name:
            if not (is_country and origin in GEO_KEEP):
                continue
        if DROP_PART_TIME and "[Not 24/7]" in name:
            continue

        yield Channel(name, attrs, genre, origin, extras, url)


def collect():
    by_url = {}
    order = list(COUNTRIES.items()) + list(CATEGORIES.items())
    for label, path in order:
        is_country = label in COUNTRIES
        try:
            body = fetch(path)
        except Exception as e:
            print(f"  !! {label:<12} failed: {e}", file=sys.stderr)
            continue
        added = 0
        for ch in parse(body, label, is_country):
            if ch.url in by_url:
                continue          # first list wins; countries are fetched first
            by_url[ch.url] = ch
            added += 1
        print(f"  {label:<12} +{added}")
    return list(by_url.values())


def write(fname, channels, group_fn):
    rows = sorted(channels, key=lambda c: ((group_fn(c) or ""), c.sort_key()))
    out = ["#EXTM3U"]
    for c in rows:
        out.append(c.render(group_fn(c)))
    path = os.path.join(OUT_DIR, fname)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(out) + "\n")
    groups = len({group_fn(c) for c in rows if group_fn(c)})
    print(f"  {fname:<26} {len(rows):>5} channels, {groups:>3} groups")


def main():
    print("fetching:")
    channels = collect()
    if not channels:
        print("nothing fetched - check your connection", file=sys.stderr)
        return 1

    print(f"\n{len(channels)} unique channels after dedupe\n")
    print("writing:")
    write("iptv-flat.m3u", channels, lambda c: None)
    write("iptv-by-country.m3u", channels, lambda c: c.origin)
    write("iptv-by-genre.m3u", channels, lambda c: c.genre)
    write("iptv-country-genre.m3u", channels, lambda c: f"{c.origin} - {c.genre}")
    write("iptv-genre-country.m3u", channels, lambda c: f"{c.genre} - {c.origin}")
    print(f"\nwritten to {OUT_DIR}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
