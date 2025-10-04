# le-homelab
me n mi homelab addiction &lt;3

# Finalized Homelab Stack

## Mi Mini Router (128 MB) — **Edge Services**

* **Ad-blocking DNS**

  * *Option A:* `adblock` (lightweight lists via dnsmasq)
  * *Option B:* AdGuard Home (if storage allows)
  * Upstream DNS: DoH/DoT (Cloudflare/Quad9)
* **Internal DNS for local IPs**

  * `dnsmasq` with `option domain 'home.lan'`, `option local '/home.lan/'`, `option expandhosts '1'`
  * Static DHCP leases → `host.home.lan` names
* **Tiny network status site**

  * `uhttpd` serving `/www` (portal with links + pings)
  * Optional second instance on `:8081` for files (USB symlink to `/www/files`)
* **Centralized Telegram alerts (bot)**

  * BusyBox cron + curl to your Telegram bot API
  * Sends: WAN IP change, link state changes, high CPU, WAN down, ping failures to 3rd/4th-gen
* **Forwarding logs/metrics**

  * `logread` → remote syslog (4th-gen) or VPS
* **VPN hub (optional)**

  * WireGuard for remote access to LAN

> **Ports**: :53 (DNS), :80/:8081 (uhttpd), :51820 (WG optional)

---

## 4th-gen i5 (16 GB) — **Media & Apps** *(2× fast HDD/SSD + separate CVAT disk)*
Specs: 4 x Intel(R) Core(TM) i5-4590 CPU @ 3.30GHz + 16GB DDR3

* **Jellyfin** (GPU/Quick Sync)

  * Volumes: `/srv/media/{movies,tv,music,books}`, `/srv/jellyfin-config`
  * Device: `/dev/dri` (VA-API)
* **Navidrome**

  * Points at `/srv/media/music`
  * Data: `/srv/navidrome-data`
* **Calibre-Web (UI only)**

  * Library sync target: `/srv/media/books`
* **CVAT** *(isolated drive)*

  * `cvat_data`, Postgres & Redis on same host; keep on separate disk/dataset
* **Management & small web UIs**

  * SMART dashboard (Scrutiny) + `smartd`
  * Netdata or Prometheus Node Exporter + Grafana (optional)
* **Reverse proxy / access**

  * Tailscale to Oracle VPS; VPS Nginx terminates TLS and proxies Jellyfin/Navidrome/Calibre-Web
* **Local sync store (authoritative for serving)**

  * Receives rsync from 3rd-gen (hourly/nightly)

> **Ports (LAN)**: 8096 (Jellyfin), 4533 (Navidrome), 8083 (Calibre-Web), others via reverse proxy
> **Users/Perms**: create `media:media` (1000:1000) and run all media containers with `PUID=1000, PGID=1000`

---

## 3rd-gen i5 (8 GB) — **Ingest & Storage** *(1× fast + 1× slow drive)*
Specs: 4 x Intel(R) Core(TM) i5-3470T CPU @ 2.90GHz + 16GB DDR3
* **Fast drive (“staging”)**

  * **qBittorrent + Radarr** (through Surfshark/WireGuard)

    * qBit categories & completed paths → Radarr hardlinks into `/srv/media/movies`
  * **YouTube downloader** (yt-dlp FastAPI/Go) → `/srv/media/music` or `/srv/media/movies`
  * **Readarr + Calibre** (book pipeline) → organized to `/srv/media/books`
  * **Prowlarr/Jackett** (indexers) for Radarr/Readarr
* **Slow drive (“bulk & share”)**

  * **Samba** exports for manual file drops and cold storage
  * Optional SnapRAID parity (if you later add a parity disk)
* **Replication to 4th-gen**

  * `rsync` push or pull (recommended: **pull on 4th-gen** for simplicity & security)
* **Health & housekeeping**

  * `smartd` + Scrutiny, logs to 4th-gen
  * Cleanup scripts (auto-prune torrents, tidy orphan files)
  * Telegram notifier (shares same bot) for ingest errors

> **Ports (LAN)**: 8080 (qBit UI), 7878 (Radarr), 9696 (Prowlarr), 445/139 (SMB), custom for yt-dlp API

---

## Cross-Cutting: **Sync, Alerts, Access**

### File Sync (3rd → 4th)

* **Pull on 4th-gen (hourly)**:

  ```bash
  rsync -aH --delete --info=stats1,progress2 \
    3rdgen:/srv/media/ /srv/media/
  ```
* Books: same path, or a separate job if you want different retention

### Telegram Alerts (central bot)

* Router: WAN up/down, device pings, high CPU/mem
* 3rd-gen: SMART warnings, rsync failures (if pushing), torrent disk full
* 4th-gen: SMART warnings, Jellyfin down, CVAT/Postgres failures

### DNS & Names

* Router dnsmasq: `*.home.lan` → local IPs

  * `jellyfin.home.lan`, `navidrome.home.lan`, `cvat.home.lan`, `ingest.home.lan`

### Remote Access Path

```
Clients ⇄ HTTPS ⇄ Oracle VPS (Nginx/Tailscale) ⇄ Tunnel ⇄ 4th-gen (Jellyfin/Navidrome/Calibre-Web)
```

*(Downloader stack remains LAN-only behind VPN; not exposed.)*

---

## Suggested Folders (both boxes)

```
/srv/media/
  movies/
  tv/
  music/
  books/
# app data
/srv/jellyfin-config/
 /srv/navidrome-data/
 /srv/calibre/
 /srv/prowlarr/
 /srv/radarr/
 /srv/readarr/
 /srv/ytapi/
```

---

## Minimal “Gotchas” Checklist

* Same UID/GID (`1000:1000`) for media user on both boxes
* Jellyfin libraries point **only** to local paths on 4th-gen
* CVAT on its own disk/dataset to avoid IO contention
* qBit on fast drive; Samba on slow drive
* Healthchecks & restarts for all containers (`restart: unless-stopped`, `HEALTHCHECK` where available)
* Back up **configs** (not just media): borg/restic to slow drive or external disk

---

This layout uses each device for what it’s great at:
router = edge brain + DNS + portal + alerts,
3rd-gen = messy ingest + NAS,
4th-gen = clean, fast serving + apps — with resilient, low-friction syncing between them.

