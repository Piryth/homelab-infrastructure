#!/usr/bin/env python3
"""homelab-offload: move finished media from the local disk to the encrypted remote.

Managed by Ansible (storage role). Configuration comes from /etc/homelab-offload.env.

Two ways to run it:

  homelab-offload [--run]            automatic mode (systemd timer): decide what to
                                     offload from free space, seeding goals and popularity
  homelab-offload --path DIR [--run] offload one library folder by hand (a movie,
                                     a season, an album), refusing if it is still seeded

Without --run (or OFFLOAD_DRY_RUN=false) nothing is uploaded or deleted: the plan is
only printed.

What gets offloaded is an "item": a movie folder (movies/Title (Year)), a season
(tv/Show/Season 01) or an album (music/Artist/Album). Items that share torrents are
grouped, so a season pack and its episodes always move together.

Order of operations for a group: upload every item -> verify -> delete the torrents
(with their files) in qBittorrent -> delete the local library copy -> refresh the
rclone mount. Nothing local is deleted unless the verification passed.

Popularity, measured per torrent:
  - recent upload: bytes uploaded over the last OFFLOAD_POP_WINDOW_DAYS, from samples
    of qBittorrent's "uploaded" counter kept in OFFLOAD_STATE (needs >= OFFLOAD_POP_MIN_HISTORY_H
    of history, otherwise unknown)
  - swarm demand: leechers (num_incomplete) and seeders (num_complete) from the tracker

  popular  recent upload >= POP_FACTOR x size, or leechers >= POP_LEECHERS,
           or the swarm needs us (leechers > 0 and seeders <= RARE_SEEDERS)
  cold     history known, recent upload < COLD_FACTOR x size, no leechers,
           and seeded at least MIN_SEED_H

Modes, from the free space on the local disk:
  normal    offload orphans (library folders no torrent uses anymore), cold items,
            items past their maximum seeding time (longer when popular), and
            ratio-satisfied items unless SEED_WHILE_SPACE
  pressure  free < LOW_GB: also offload, in this order, until free >= HIGH_GB:
            satisfied, then neutral, then popular items (never younger than HARD_MIN_SEED_H)
Pausing downloads when the disk is nearly full stays the job of qbit-diskguard.
"""
import argparse
import fcntl
import http.cookiejar
import json
import logging
import os
import shutil
import subprocess
import sys
import time
import urllib.parse
import urllib.request

GiB = 1024 ** 3
log = logging.getLogger("homelab-offload")


# ------------------------------------------------------------------ configuration
ENV_FILE = "/etc/homelab-offload.env"


def load_env_file(path=ENV_FILE):
    """Read the Ansible-written settings when run by hand (systemd already loads them).

    Values already in the environment win, so systemd and explicit overrides are kept.
    """
    try:
        lines = open(path).read().splitlines()
    except (FileNotFoundError, PermissionError):
        return
    for line in lines:
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] == '"':
            value = value[1:-1].replace('\\"', '"').replace("\\\\", "\\")
        os.environ.setdefault(key.strip(), value)


def env(name, default, cast=str):
    raw = os.environ.get(name)
    if raw is None or raw == "":
        return default
    if cast is bool:
        return raw.strip().lower() in ("1", "true", "yes", "on")
    return cast(raw)


def load_config():
    c = {
        "qb_url": env("QB_URL", "http://127.0.0.1:9090").rstrip("/"),
        "qb_user": env("QB_USER", ""),
        "qb_pass": env("QB_PASS", ""),
        "local_root": env("OFFLOAD_LOCAL_ROOT", "/data/local"),
        "container_root": env("OFFLOAD_CONTAINER_ROOT", "/data"),
        "library": env("OFFLOAD_LIBRARY", "/data/local/media"),
        "remote": env("OFFLOAD_REMOTE", "media-crypt:media"),
        "rc_addr": env("OFFLOAD_RC_ADDR", "127.0.0.1:5572"),
        "rc_prefix": env("OFFLOAD_RC_PREFIX", "media"),
        "state": env("OFFLOAD_STATE", "/var/lib/homelab-offload/state.json"),
        "lock": env("OFFLOAD_LOCK", "/run/homelab-offload.lock"),
        "dry_run": env("OFFLOAD_DRY_RUN", True, bool),
        # category -> item depth under the library (movies/Title = 1, tv/Show/Season = 2)
        "depths": {k: int(v) for k, v in
                   (p.split(":") for p in env("OFFLOAD_CATEGORIES", "movies:1,tv:2").split(",") if p)},
        "low": env("OFFLOAD_LOW_GB", 150, float) * GiB,
        "high": env("OFFLOAD_HIGH_GB", 220, float) * GiB,
        "min_ratio": env("OFFLOAD_MIN_RATIO", 2.0, float),
        "min_seed_h": env("OFFLOAD_MIN_SEED_H", 72, float),
        "hard_min_seed_h": env("OFFLOAD_HARD_MIN_SEED_H", 24, float),
        "max_seed_h": env("OFFLOAD_MAX_SEED_DAYS", 30, float) * 24,
        "max_seed_popular_h": env("OFFLOAD_MAX_SEED_POPULAR_DAYS", 90, float) * 24,
        "seed_while_space": env("OFFLOAD_SEED_WHILE_SPACE", True, bool),
        "orphans_always": env("OFFLOAD_ORPHANS_ALWAYS", True, bool),
        "orphan_min_age_h": env("OFFLOAD_ORPHAN_MIN_AGE_H", 24, float),
        "pop_window_h": env("OFFLOAD_POP_WINDOW_DAYS", 7, float) * 24,
        "pop_min_history_h": env("OFFLOAD_POP_MIN_HISTORY_H", 24, float),
        "pop_factor": env("OFFLOAD_POP_FACTOR", 0.25, float),
        "pop_leechers": env("OFFLOAD_POP_LEECHERS", 3, int),
        "rare_seeders": env("OFFLOAD_RARE_SEEDERS", 1, int),
        "cold_factor": env("OFFLOAD_COLD_FACTOR", 0.01, float),
        "keep_tag": env("OFFLOAD_KEEP_TAG", "keep"),
        "max_bytes": env("OFFLOAD_MAX_GB_PER_RUN", 200, float) * GiB,
        "verify": env("OFFLOAD_VERIFY", "cryptcheck"),          # cryptcheck | size | download
        "transfers": env("OFFLOAD_TRANSFERS", 4, int),
        # node-exporter textfile collector output (empty = no metrics)
        "metrics_file": env("OFFLOAD_METRICS_FILE", ""),
    }
    if not c["low"] < c["high"]:
        sys.exit("OFFLOAD_LOW_GB must be lower than OFFLOAD_HIGH_GB")
    return c


# ------------------------------------------------------------------ qBittorrent
class QB:
    def __init__(self, url, user, password):
        self.url = url
        self.opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
        body = self._call("auth/login", {"username": user, "password": password})
        if body.strip() != "Ok.":
            raise SystemExit("qBittorrent login failed")

    def _call(self, path, data=None, params=None):
        url = f"{self.url}/api/v2/{path}"
        if params:
            url += "?" + urllib.parse.urlencode(params)
        req = urllib.request.Request(url, headers={"Referer": self.url})
        if data is not None:
            req.data = urllib.parse.urlencode(data).encode()
        with self.opener.open(req, timeout=30) as resp:
            return resp.read().decode()

    def get(self, path, **params):
        return json.loads(self._call(path, params=params))

    def delete(self, hashes):
        self._call("torrents/delete", {"hashes": "|".join(hashes), "deleteFiles": "true"})


# ------------------------------------------------------------------ helpers
def run(cmd, cfg, check=True):
    log.debug("$ %s", " ".join(cmd))
    r = subprocess.run(cmd, capture_output=True, text=True)
    if check and r.returncode != 0:
        log.error("command failed (%s): %s\n%s", r.returncode, " ".join(cmd), r.stderr.strip()[-2000:])
    return r.returncode == 0


def du(path):
    total = 0
    for root, _, files in os.walk(path):
        for f in files:
            try:
                total += os.lstat(os.path.join(root, f)).st_size
            except FileNotFoundError:
                pass
    return total


def files_in(path):
    for root, _, files in os.walk(path):
        for f in files:
            yield os.path.join(root, f)


def item_of(path, cfg):
    """Library item folder (relative to the library) containing path, or None."""
    rel = os.path.relpath(path, cfg["library"])
    parts = rel.split(os.sep)
    depth = cfg["depths"].get(parts[0])
    # files above the item level (e.g. tvshow.nfo in a show folder) are never
    # offloaded automatically: items must not contain other items
    if depth is None or len(parts) < depth + 2:
        return None
    return os.sep.join(parts[:depth + 1])


def fmt(n):
    return f"{n / GiB:.1f} GiB"


# ------------------------------------------------------------------ metrics
def write_metrics(cfg, ok, stats):
    """Publish the run's outcome for node-exporter's textfile collector (atomic write)."""
    path = cfg.get("metrics_file")
    if not path:
        return
    lines = [
        "# HELP homelab_offload_last_run_timestamp_seconds End of the last automatic run.",
        "# TYPE homelab_offload_last_run_timestamp_seconds gauge",
        f"homelab_offload_last_run_timestamp_seconds {time.time():.0f}",
        "# HELP homelab_offload_last_run_success 1 if the last run finished without any failed group.",
        "# TYPE homelab_offload_last_run_success gauge",
        f"homelab_offload_last_run_success {1 if ok else 0}",
        "# TYPE homelab_offload_dry_run gauge",
        f"homelab_offload_dry_run {1 if cfg['dry_run'] else 0}",
        "# TYPE homelab_offload_low_bytes gauge",
        f"homelab_offload_low_bytes {cfg['low']:.0f}",
        "# TYPE homelab_offload_high_bytes gauge",
        f"homelab_offload_high_bytes {cfg['high']:.0f}",
    ]
    if stats:
        lines += [
            "# HELP homelab_offload_pressure 1 if the last run was in pressure mode.",
            "# TYPE homelab_offload_pressure gauge",
            f"homelab_offload_pressure {1 if stats['mode'] == 'pressure' else 0}",
            "# TYPE homelab_offload_free_bytes gauge",
            f"homelab_offload_free_bytes {stats['free']:.0f}",
            "# HELP homelab_offload_uploaded_bytes Bytes uploaded by the last run (planned, in dry run).",
            "# TYPE homelab_offload_uploaded_bytes gauge",
            f"homelab_offload_uploaded_bytes {stats['uploaded']:.0f}",
            "# TYPE homelab_offload_freed_bytes gauge",
            f"homelab_offload_freed_bytes {stats['freed']:.0f}",
            "# HELP homelab_offload_groups Library item groups seen by the last run, by state.",
            "# TYPE homelab_offload_groups gauge",
        ]
        lines += [f'homelab_offload_groups{{state="{k}"}} {v}' for k, v in sorted(stats["groups"].items())]
        lines += ["# HELP homelab_offload_torrents Managed torrents by class.",
                  "# TYPE homelab_offload_torrents gauge"]
        lines += [f'homelab_offload_torrents{{class="{c}",popular="{str(p).lower()}"}} {n}'
                  for (c, p), n in sorted(stats["torrents"].items())]
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        tmp = path + ".tmp"
        with open(tmp, "w") as f:
            f.write("\n".join(lines) + "\n")
        os.chmod(tmp, 0o644)
        os.replace(tmp, path)
    except OSError as e:
        log.warning("could not write metrics to %s: %s", path, e)


# ------------------------------------------------------------------ popularity state
def load_state(path):
    try:
        with open(path) as f:
            return json.load(f)
    except (FileNotFoundError, ValueError):
        return {}


def save_state(path, state):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(state, f)
    os.replace(tmp, path)


def record_samples(state, torrents, cfg, now):
    keep_s = cfg["pop_window_h"] * 3600 + 86400
    seen = set()
    for t in torrents:
        h = t["hash"]
        seen.add(h)
        samples = [s for s in state.get(h, []) if now - s[0] <= keep_s]
        if not samples or now - samples[-1][0] >= 3000:   # at most one sample per ~hour
            samples.append([now, t.get("uploaded", 0)])
        state[h] = samples
    for h in list(state):
        if h not in seen:
            del state[h]


def recent_upload(samples, cfg, now):
    """Bytes uploaded over the popularity window (extrapolated), or None if history is too short."""
    window = cfg["pop_window_h"] * 3600
    inside = [s for s in samples if now - s[0] <= window]
    if len(inside) < 2:
        return None
    span = inside[-1][0] - inside[0][0]
    if span < cfg["pop_min_history_h"] * 3600:
        return None
    delta = max(0, inside[-1][1] - inside[0][1])
    return delta * window / span


def classify(t, up_week, cfg):
    """Return (class, popular). class: young | cold | satisfied | expired | neutral."""
    seed_h = t.get("seeding_time", 0) / 3600
    size = max(t.get("size", 1), 1)
    leechers = max(t.get("num_incomplete", 0), 0)
    seeders = max(t.get("num_complete", 0), 0)
    popular = ((up_week is not None and up_week >= cfg["pop_factor"] * size)
               or leechers >= cfg["pop_leechers"]
               or (leechers > 0 and seeders <= cfg["rare_seeders"]))
    if seed_h < cfg["hard_min_seed_h"]:
        return "young", popular
    max_h = cfg["max_seed_popular_h"] if popular else cfg["max_seed_h"]
    if seed_h >= max_h:
        return "expired", popular
    if (not popular and up_week is not None and up_week < cfg["cold_factor"] * size
            and leechers == 0 and seed_h >= cfg["min_seed_h"]):
        return "cold", popular
    if t.get("ratio", 0) >= cfg["min_ratio"] and seed_h >= cfg["min_seed_h"]:
        return "satisfied", popular
    return "neutral", popular


# ------------------------------------------------------------------ planning
def build_groups(cfg, torrents, pops):
    """Group library items with the torrents linked to them.

    Returns a list of dicts: items (set of rel paths), torrents (list), blocked (reason or None).
    """
    lib = cfg["library"]
    # library files by inode, and their item
    by_inode, item_files = {}, {}
    for cat in cfg["depths"]:
        for path in files_in(os.path.join(lib, cat)):
            try:
                st = os.lstat(path)
            except FileNotFoundError:
                continue
            item = item_of(path, cfg)
            if item is None:
                continue
            item_files.setdefault(item, []).append((path, st))
            if st.st_nlink > 1:
                by_inode[(st.st_dev, st.st_ino)] = item

    # torrents -> items they are linked to (union-find over items)
    parent = {i: i for i in item_files}

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    explained = {}           # inode -> number of eligible torrent links
    torrent_items = {}
    for t in torrents:
        base = t["save_path"]
        if base == cfg["container_root"] or base.startswith(cfg["container_root"] + "/"):
            base = cfg["local_root"] + base[len(cfg["container_root"]):]
        items = set()
        for f in t["_files"]:
            try:
                st = os.lstat(os.path.join(base, f["name"]))
            except FileNotFoundError:
                continue
            key = (st.st_dev, st.st_ino)
            if key in by_inode:
                items.add(by_inode[key])
                explained[key] = explained.get(key, 0) + 1
        if items:
            torrent_items[t["hash"]] = items
            first = next(iter(items))
            for i in items:
                parent[find(i)] = find(first)

    groups = {}
    for item in item_files:
        g = groups.setdefault(find(item), {"items": set(), "torrents": {}, "blocked": None})
        g["items"].add(item)
    by_hash = {t["hash"]: t for t in torrents}
    for h, items in torrent_items.items():
        groups[find(next(iter(items)))]["torrents"][h] = by_hash[h]

    # block items holding links nobody explains (keep tag, other category, cross-seed...)
    for g in groups.values():
        for item in g["items"]:
            for path, st in item_files[item]:
                extra = st.st_nlink - 1 - explained.get((st.st_dev, st.st_ino), 0)
                if extra > 0:
                    g["blocked"] = f"{path} has {extra} link(s) not owned by an eligible torrent"
                    break
            if g["blocked"]:
                break
        g["files"] = [p for i in g["items"] for p, _ in item_files[i]]
        g["ctime"] = max((st.st_ctime for i in g["items"] for _, st in item_files[i]), default=0)
        g["size"] = sum(st.st_size for i in g["items"] for _, st in item_files[i])
        linked = sum(st.st_size for i in g["items"] for _, st in item_files[i] if st.st_nlink > 1)
        g["frees"] = g["size"] + max(0, sum(t["size"] for t in g["torrents"].values()) - linked)
        g["upload"] = g["size"]
        classes = [pops[h] for h in g["torrents"]]
        g["classes"] = classes
        g["popular"] = any(p for _, p in classes)
        g["young"] = any(c == "young" for c, _ in classes)
        g["up_rate"] = sum(t.get("_up_week") or 0 for t in g["torrents"].values())
    return list(groups.values())


RANK = {"cold": 1, "expired": 1, "satisfied": 2, "neutral": 3}


def plan(cfg, groups, free, now):
    """Choose groups to offload. Returns (mode, [(group, reason)])."""
    chosen, seen = [], set()

    def take(g, reason):
        if id(g) not in seen:
            seen.add(id(g))
            chosen.append((g, reason))

    eligible = [g for g in groups if not g["blocked"] and not g["young"]]
    # normal pass
    for g in eligible:
        cls = [c for c, _ in g["classes"]]
        if not g["torrents"]:
            if cfg["orphans_always"] and now - g["ctime"] >= cfg["orphan_min_age_h"] * 3600:
                take(g, "orphan (no torrent left)")
        elif all(c in ("cold", "expired") for c in cls):
            take(g, "cold or past max seeding time")
        elif not cfg["seed_while_space"] and not g["popular"] and all(
                c in ("cold", "expired", "satisfied") for c in cls):
            take(g, "seeding goals met")

    mode = "normal"
    projected = free + sum(g["frees"] for g, _ in chosen)
    if projected < cfg["low"]:
        mode = "pressure"

        def rank(g):
            if not g["torrents"]:
                return 0
            r = max(RANK[c] for c, _ in g["classes"])
            return r + (2 if g["popular"] else 0)

        rest = sorted((g for g in eligible if id(g) not in seen),
                      key=lambda g: (rank(g), g["up_rate"], -g["frees"]))
        for g in rest:
            if projected >= cfg["high"]:
                break
            if not g["torrents"] and now - g["ctime"] < cfg["orphan_min_age_h"] * 3600:
                continue
            take(g, "disk pressure" + (" (popular!)" if g["popular"] else ""))
            projected += g["frees"]
    return mode, chosen


# ------------------------------------------------------------------ execution
def verify(local, remote, cfg):
    if cfg["verify"] == "size":
        cmd = ["rclone", "check", local, remote, "--one-way", "--size-only"]
    elif cfg["verify"] == "download":
        cmd = ["rclone", "check", local, remote, "--one-way", "--download"]
    else:
        cmd = ["rclone", "cryptcheck", local, remote, "--one-way"]
    # the remote can take a moment to list fresh uploads
    for attempt in range(5):
        if run(cmd, cfg, check=(attempt == 4)):
            return True
        time.sleep(20)
    return False


def remove_empty_parents(path, cfg):
    stop = {os.path.join(cfg["library"], c) for c in cfg["depths"]} | {cfg["library"]}
    d = os.path.dirname(path)
    while d not in stop and d.startswith(cfg["library"]):
        try:
            os.rmdir(d)
        except OSError:
            break
        d = os.path.dirname(d)


def offload_group(g, cfg, qb):
    lib = cfg["library"]
    would = "[dry run] would " if cfg["dry_run"] else ""
    for item in sorted(g["items"]):
        local = os.path.join(lib, item)
        remote = f"{cfg['remote']}/{item}"
        log.info("  %supload %s (%s) -> %s", would, item, fmt(du(local)), remote)
        if cfg["dry_run"]:
            continue
        if not run(["rclone", "copy", local, remote, "--transfers", str(cfg["transfers"]),
                    "--timeout", "5m", "--low-level-retries", "10", "--retries", "3"], cfg):
            log.error("  upload failed, group kept local")
            return False
        if not verify(local, remote, cfg):
            log.error("  verification failed, group kept local")
            return False
    if g["torrents"]:
        names = ", ".join(t["name"] for t in g["torrents"].values())
        log.info("  %sdelete torrent(s) with files: %s", would, names)
        if not cfg["dry_run"]:
            try:
                qb.delete(list(g["torrents"]))
            except OSError as e:
                log.error("  qBittorrent delete failed (%s), local copy kept", e)
                return False
    for item in sorted(g["items"]):
        local = os.path.join(lib, item)
        log.info("  %sdelete local copy %s", would, local)
        if cfg["dry_run"]:
            continue
        shutil.rmtree(local, ignore_errors=True)
        remove_empty_parents(local, cfg)
        run(["rclone", "rc", "vfs/refresh", f"dir={cfg['rc_prefix']}/{os.path.dirname(item)}",
             "recursive=true", "--rc-addr", cfg["rc_addr"]], cfg, check=False)
    return True


def auto(cfg):
    now = time.time()
    qb = QB(cfg["qb_url"], cfg["qb_user"], cfg["qb_pass"])
    cats = set(cfg["depths"])
    allt = qb.get("torrents/info", filter="completed")

    state = load_state(cfg["state"])
    record_samples(state, allt, cfg, now)
    save_state(cfg["state"], state)      # also in dry run: popularity needs history

    torrents, pops = [], {}
    for t in allt:
        tags = {x.strip() for x in t.get("tags", "").split(",") if x.strip()}
        if t.get("category") not in cats or cfg["keep_tag"] in tags:
            continue                      # their links block the items they share
        t["_files"] = qb.get("torrents/files", hash=t["hash"])
        t["_up_week"] = recent_upload(state.get(t["hash"], []), cfg, now)
        pops[t["hash"]] = classify(t, t["_up_week"], cfg)
        torrents.append(t)

    groups = build_groups(cfg, torrents, pops)
    free = shutil.disk_usage(cfg["local_root"]).free
    mode, chosen = plan(cfg, groups, free, now)

    blocked = sum(1 for g in groups if g["blocked"])
    log.info("free %s (low %s, high %s) | mode %s | %d groups, %d blocked, %d chosen%s",
             fmt(free), fmt(cfg["low"]), fmt(cfg["high"]), mode, len(groups), blocked,
             len(chosen), " | DRY RUN" if cfg["dry_run"] else "")
    for t in torrents:
        c, p = pops[t["hash"]]
        up = t["_up_week"]
        log.debug("torrent %s: %s%s, ratio %.2f, %.0f h, up/week %s, swarm %s seeds / %s leechers",
                  t["name"], c, " popular" if p else "", t.get("ratio", 0),
                  t.get("seeding_time", 0) / 3600, "?" if up is None else fmt(up),
                  t.get("num_complete"), t.get("num_incomplete"))

    uploaded = freed = 0
    done = failed = 0
    for g, reason in chosen:
        if uploaded >= cfg["max_bytes"]:
            log.info("per-run upload budget reached (%s), rest next run", fmt(cfg["max_bytes"]))
            break
        log.info("offload [%s]: %s", reason, ", ".join(sorted(g["items"])))
        if offload_group(g, cfg, qb):
            uploaded += g["upload"]
            freed += g["frees"]
            done += 1
        else:
            failed += 1
    if cfg["dry_run"]:
        log.info("dry run finished: would upload ~%s and free ~%s. Nothing was changed "
                 "(run with --run, or set storage_offload_dry_run: false)", fmt(uploaded), fmt(freed))
    else:
        log.info("done: uploaded ~%s, freed ~%s", fmt(uploaded), fmt(freed))

    counts = {}
    for c, p in pops.values():
        counts[(c, p)] = counts.get((c, p), 0) + 1
    return failed == 0, {
        "mode": mode, "free": free, "uploaded": uploaded, "freed": freed,
        "groups": {"total": len(groups), "blocked": blocked, "chosen": len(chosen),
                   "done": done, "failed": failed},
        "torrents": counts,
    }


def manual(cfg, path):
    path = os.path.realpath(path)
    pool = env("OFFLOAD_POOL_LIBRARY", "/mnt/pool/data/media")
    if path.startswith(pool + "/"):
        path = cfg["library"] + path[len(pool):]
    if not path.startswith(cfg["library"] + "/") or not os.path.isdir(path):
        sys.exit(f"not a folder under {cfg['library']}: {path}")
    linked = [p for p in files_in(path) if os.lstat(p).st_nlink > 1]
    if linked:
        sys.exit(f"{len(linked)} file(s) still seeded (hardlinked to a torrent), e.g. {linked[0]}\n"
                 "Remove the torrent in qBittorrent first.")
    item = os.path.relpath(path, cfg["library"])
    log.info("offload [manual]: %s (%s)%s", item, fmt(du(path)),
             " | DRY RUN, nothing will be changed" if cfg["dry_run"] else "")
    ok = offload_group({"items": {item}, "torrents": {}}, cfg, None)
    sys.exit(0 if ok else 1)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--path", help="offload this library folder by hand")
    ap.add_argument("--run", action="store_true", help="really upload and delete (default: dry run)")
    ap.add_argument("-v", "--verbose", action="store_true", help="show per-torrent popularity")
    args = ap.parse_args()
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO,
                        format="%(levelname)s %(message)s")
    load_env_file()
    cfg = load_config()
    if args.run:
        cfg["dry_run"] = False

    lock = open(cfg["lock"], "w")
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        log.info("another offload is running, exiting")
        return
    if args.path:
        try:
            manual(cfg, args.path)
        except OSError as e:
            log.error("aborted: %s", e)
            sys.exit(1)
        return
    try:
        ok, stats = auto(cfg)
    except OSError as e:          # qBittorrent or the disk unreachable: try again next run
        log.error("aborted: %s", e)
        write_metrics(cfg, False, None)
        sys.exit(1)
    write_metrics(cfg, ok, stats)
    if not ok:
        sys.exit(1)


if __name__ == "__main__":
    main()
