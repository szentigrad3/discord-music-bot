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

## CachyOS/Linux upgrade

First shut down the **old** bot and old Lavalink instance/container. Never
run two bots using the same Discord token concurrently.

```bash
cd ~/Downloads
unzip -o discord-music-bot.zip

git clone --branch maintenance/discord-reconnect-sync-2026 \
  https://github.com/szentigrad3/discord-music-bot.git \
  ~/discord-music-bot-next

cd ~/discord-music-bot-next

# Safe preview: does not change either directory.
python3 scripts/import_existing_v121.py \
  --old ~/Downloads/discord-music-bot

# Copy private configuration and database to the new checkout.
python3 scripts/import_existing_v121.py \
  --old ~/Downloads/discord-music-bot --apply

python3 -m venv .venv
# CachyOS fish shell:
source .venv/bin/activate.fish
# Bash/Zsh alternative: source .venv/bin/activate
python -m pip install -r requirements.txt pyyaml

python scripts/doctor.py
bash scripts/test-all.sh
```

For Docker use `docker compose config --quiet` before
`docker compose up -d --build`; note this will start/replace services in
the *new* directory only. For standalone installations use the usual
`python -m bot.main` after verifying Java and Lavalink.

When you confirm playback and saved playlist commands work, the old directory
can remain as the backup. Do not delete the backup or promote this development
branch to production until live playback and dashboard verification pass.

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

Use `python scripts/doctor.py` without publishing your config.
Use `python scripts/lavalink_smoke.py` to check REST connectivity.
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
