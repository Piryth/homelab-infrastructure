#!/usr/bin/env python3
"""Pause qBittorrent downloads when the local disk is nearly full.

Managed by Ansible — do not edit manually.
qBittorrent writes to /data/local directly (not through mergerfs), so
minfreespace does not protect it. Below GUARD_LOW_GB free, downloading
torrents are tagged and paused; above GUARD_HIGH_GB they are resumed.
Seeding torrents are never touched.
"""
import http.cookiejar
import json
import os
import shutil
import sys
import urllib.error
import urllib.parse
import urllib.request

QB = os.environ["QB_URL"].rstrip("/")
PATH = os.environ["GUARD_PATH"]
LOW = int(os.environ["GUARD_LOW_GB"]) * 1024 ** 3
HIGH = int(os.environ["GUARD_HIGH_GB"]) * 1024 ** 3
TAG = "diskguard"

opener = urllib.request.build_opener(
    urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))


def api(endpoint, data=None, params=None):
    url = f"{QB}/api/v2/{endpoint}"
    if params:
        url += "?" + urllib.parse.urlencode(params)
    body = urllib.parse.urlencode(data).encode() if data is not None else None
    # qBittorrent rejects requests without a matching Referer (CSRF protection)
    req = urllib.request.Request(url, data=body, headers={"Referer": QB})
    with opener.open(req, timeout=15) as r:
        return r.read().decode()


def control(action, hashes):
    # qBittorrent >= 5 renamed pause/resume to stop/start
    new, old = {"pause": ("stop", "pause"), "resume": ("start", "resume")}[action]
    try:
        api(f"torrents/{new}", {"hashes": hashes})
    except urllib.error.HTTPError as e:
        if e.code != 404:
            raise
        api(f"torrents/{old}", {"hashes": hashes})


free = shutil.disk_usage(PATH).free
if LOW <= free <= HIGH:
    sys.exit(0)

if api("auth/login", {"username": os.environ["QB_USER"],
                      "password": os.environ["QB_PASS"]}).strip() != "Ok.":
    sys.exit("qBittorrent login failed")

gib = free / 1024 ** 3
if free < LOW:
    torrents = json.loads(api("torrents/info", params={"filter": "downloading"}))
    hashes = "|".join(t["hash"] for t in torrents)
    if hashes:
        api("torrents/addTags", {"hashes": hashes, "tags": TAG})
        control("pause", hashes)
        print(f"{gib:.1f} GiB free: paused {len(torrents)} download(s)")
else:
    torrents = json.loads(api("torrents/info", params={"tag": TAG}))
    hashes = "|".join(t["hash"] for t in torrents)
    if hashes:
        control("resume", hashes)
        api("torrents/removeTags", {"hashes": hashes, "tags": TAG})
        print(f"{gib:.1f} GiB free: resumed {len(torrents)} download(s)")
