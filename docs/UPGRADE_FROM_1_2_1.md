# Upgrading an existing v1.2.1 installation

This workflow is designed for users who previously installed from a ZIP
(including a local `settings.json`, SQLite data, and customized Lavalink YAML).
**It does not replace or change your original installation.**

## What the importer preserves

- The exact existing `settings.json` including configured bot/OAuth/Lavalink values.
- `data/bot.db` using SQLite's backup API and other non-placeholder `data/` files.
- Existing standalone Lavalink tuning in **ignored**
  `lavalink/application.local.yml`.
- Existing Docker Lavalink tuning in **ignored**
  `lavalink/application.docker.local.yml`.
- A generated, ignored `.env` containing the existing Lavalink password,
  so Docker Compose and the bot agree on authentication.

The importer copies **no logs**, virtual environments, generated JARs, or
source code. Old and new versions must use separate directories.
Tracked upstream Lavalink files remain unmodified. Passwords are never
printed; do not commit local configuration, database or `.env` files.

## CachyOS/Linux upgrade (tested path from your backup)

Your archive was extracted while you were in
`/mnt/other/JASON/JASON/backup/`, so its original installation directory is
`/mnt/other/JASON/JASON/backup/discord-music-bot/`. Do **not** use
`~/Downloads/discord-music-bot` unless you extracted a different copy there.

**Stop the old bot and Lavalink before importing an actively used database.**
Do not run two bot processes with the same Discord token.

The new checkout already exists in `~/discord-music-bot-next`; you do not
need to clone or unzip again. These commands work in Bash **and** fish because
they invoke the Python virtual environment directly:

```bash
cd ~/discord-music-bot-next
git pull --ff-only

# Verify the real existing setup (this shows only the filename).
ls /mnt/other/JASON/JASON/backup/discord-music-bot/settings.json

# Safe preview: no files are copied.
python3 scripts/import_existing_v121.py \
  --old /mnt/other/JASON/JASON/backup/discord-music-bot

# Only after checking the preview, copy existing private settings/database.
python3 scripts/import_existing_v121.py \
  --old /mnt/other/JASON/JASON/backup/discord-music-bot --apply

# After importing private YAML, allow the non-root Lavalink container to read it.
sudo pacman -S --needed acl
python3 scripts/prepare_lavalink_docker.py --apply

# No activate.fish/source required (and no system-wide pip writes).
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt pyyaml

.venv/bin/python scripts/doctor.py
bash scripts/test-all.sh
```

The importer is conservative. If an earlier test run generated
`settings.json` byte-for-byte from `settings Example.json`, it backs up
that generated sample and imports the real settings instead. If the destination
contains a *customized* settings file, the importer refuses to overwrite it.
Never delete an existing config or database merely to make the importer run.

The AIO test runner now uses `.venv/bin/python` automatically, validates
dependencies before loading bot modules and stops without running the suite
if the imported settings file is missing. Python 3.13 is the tested CI
version; your system Python may be 3.14, which requires installing compatible
packages within the new virtual environment.

For Docker use `docker compose config --quiet` before
`docker compose up -d --build`; note this will start/replace services in
the *new* directory only. For standalone installations use the usual
`python -m bot.main` after verifying Java and Lavalink.

When you confirm playback and saved playlist commands work, the old directory
can remain as the backup. Do not delete the backup or promote this development
branch to production until live playback and dashboard verification pass.

## Fixing Lavalink Docker bind-mount permissions

The official Lavalink Ubuntu image runs as non-root UID **322**. Private
`application.docker.local.yml` is imported with mode `0600`, which
intentionally protects its credentials on the host but denies the container's
user permission to read it. Without an ACL, Lavalink repeatedly crashes with
`FileNotFoundException: /opt/lavalink/application.docker.local.yml
(Permission denied)`. This is **not** an out-of-memory error.

On CachyOS / Arch:

```bash
cd ~/discord-music-bot-next
sudo pacman -S --needed acl

# View changes without applying them
python3 scripts/prepare_lavalink_docker.py

# Grant the container UID the smallest required accesses
python3 scripts/prepare_lavalink_docker.py --apply

docker compose restart lavalink
docker compose ps
docker compose exec -T lavalink sh -c \
  'curl -fsS -H "Authorization: $LAVALINK_SERVER_PASSWORD" http://127.0.0.1:2333/version'
```

This grants UID 322 **read** on the private Docker YAML, **directory
traversal** on `lavalink/`, and **read/write** permissions to the
`lavalink/plugins/` directory and existing plugin files. The standalone
Lavalink config, bot `settings.json`, `.env` and SQLite database are
untouched. The utility refuses symlinks and never displays secret values.

If you use a custom Lavalink image variant with a different numeric user ID,
pass `--uid <number>` based on that image's actual user. Do not use
`chmod 777`, make your whole data folder world-readable or run the container
as root merely to fix a read permission.

If the container still restarts, inspect the **next** startup exception with
`docker compose logs --tail=100 lavalink`. Missing permissions on
individual plugin files may require rerunning the ACL utility.

## Configuration details

- If `settings.json` uses `lavalink.host=localhost`, the bot already
  resolves that to `lavalink` inside Docker; leave it unchanged.
- Docker `LAVALINK_SERVER_PASSWORD` reads `LAVALINK_PASSWORD` from the
  new checkout's ignored `.env`, falling back to the example only when
  no local value exists.
- Docker `SPRING_CONFIG_LOCATION` reads `LAVALINK_CONFIG_FILE` and
  defaults to the original tracked `application.docker.yml`.
- Standalone auto-start uses the private `application.local.yml`, if present.
- The first updated bot startup creates the `SavedPlaylists` table, without
  replacing the existing guild settings table.
- Spotify API support requires a configured Spotify client ID and secret.
- The web dashboard requires a nonempty session secret and valid Discord
  OAuth credentials/callback; an empty secret intentionally disables it.
- The Docker dashboard binds to localhost by default. Put an HTTPS reverse
  proxy in front if exposing it to other devices.

## Troubleshooting

Use `.venv/bin/python scripts/doctor.py` without publishing your config.
Use `.venv/bin/python scripts/lavalink_smoke.py` to check REST connectivity.
The last is an authenticated read-only API check, **not** an audible
Discord voice test.

If an import is refused because `settings.json`, `.env`, or the destination
database already exists, do not delete it blindly. Inspect the destination
or start with a clean development checkout. The importer deliberately
does not merge or overwrite existing private configuration.

**Security:** Never upload a configured `settings.json`, `.env`, or
Lavalink application.local YAML to a public GitHub repository.
If a real Discord token or OAuth secret was publicly exposed, rotate it
through the relevant service and update your private configuration.
