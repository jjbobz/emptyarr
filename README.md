# emptyarr

Safely empties Plex library trash by validating mount health before acting.
Supports multiple Plex instances, mixed physical/debrid libraries, per-library
cron schedules, dry runs, and Discord notifications.

## How it works

Each library run:
1. Checks Plex is reachable
2. Per path: mountpoint check → symlink resolution (debrid/usenet) → file threshold
3. Optionally pings debrid provider APIs (Real-Debrid, AllDebrid, Torbox, Debrid-Link)
4. If all checks pass: snapshots trash contents → calls emptyTrash
5. Records every run with per-check results and list of removed titles

If any check fails: skips trash empty, optionally sends Discord alert.

## Library types

| Type | Mountpoint | Symlinks | File threshold | Provider API |
|------|-----------|----------|---------------|-------------|
| `physical` | ✅ | ❌ | ✅ | ❌ |
| `debrid` | ✅ | ✅ | ✅ | optional |
| `usenet` | ✅ | ✅ | ✅ | optional (future) |
| `mixed` | per path | per path | per path | per path |

## Setup

### Step 1 — Get your Plex section IDs (optional)

emptyarr auto-discovers section IDs by library name, but you can hardcode them:
```
http://PLEX_IP:32400/library/sections?X-Plex-Token=YOUR_TOKEN
```

### Step 2 — Create config files

```bash
mkdir -p /mnt/cache/appdata/emptyarr/data
cp data/config.yml.example /mnt/cache/appdata/emptyarr/data/config.yml
cp .env.example /mnt/cache/appdata/emptyarr/.env
# Edit both files with your values
```

### Step 3 — Build (Unraid terminal)

```bash
cd /mnt/cache/appdata/emptyarr
git clone https://github.com/jjbobzin/emptyarr.git .
docker compose up -d --build
```

### Step 4 — Add via Unraid GUI

Or add as a container in Unraid → Docker → Add Container:
- Repository: emptyarr (after building locally)
- Port: 7878 → 7878
- Add volume mounts and env vars from docker-compose.yml

### Step 5 — Open the UI

```
http://YOUR_UNRAID_IP:7878
```

## Volume mount notes

The most important thing: **symlink targets must be resolvable inside the container.**

Your symlinks in `/media/symlinks/movie` point to files under the Decypharr mount.
That mount must also be mounted into the container at the same path the symlinks reference.

Example: if a symlink at `/media/symlinks/movie/Film (2020)/film.mkv` points to
`/mnt/symlink_media/decypharr/mount/__all__/film.mkv`, then
`/mnt/symlink_media/decypharr/mount` must be mounted into the container.

## Updating

```bash
cd /mnt/cache/appdata/emptyarr
git pull
docker compose up -d --build
```

## API

| Endpoint | Method | Description |
|----------|--------|-------------|
| / | GET | Web UI |
| /api/status | GET | Instance status, next runs, scheduling state |
| /api/history | GET | Run history (last 100) |
| /api/checks | GET | Run Plex reachability checks only |
| /api/scheduling | POST | `{"enabled": true/false}` — pause/resume cron |
| /api/run/all | POST | Trigger all libraries |
| /api/dryrun/all | POST | Dry run all libraries |
| /api/run/{instance}/{library} | POST | Trigger one library |
| /api/dryrun/{instance}/{library} | POST | Dry run one library |
