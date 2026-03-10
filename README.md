# Discord Music Bot

A feature-rich Discord music bot built with Python 3.13, discord.py v2, and Lavalink. Supports YouTube, SoundCloud, Twitch, Spotify, slash commands, prefix commands, audio filters, and a web dashboard.

## Features

- 🎵 **Multi-platform**: YouTube, SoundCloud, Twitch, Spotify
- 🔗 **Playlist support**: YouTube playlists (up to 50 tracks), Spotify albums/playlists
- 🎛️ **Audio filters**: Nightcore, Bass Boost, Vaporwave, 8D Audio, Karaoke, Slowed — use `none` to remove any active filter (powered by Lavalink)
- 🔁 **Repeat modes**: Off, One, All
- 🔀 **Shuffle** queue
- 📋 **Slash commands + prefix commands**
- 🕹️ **Interactive controller** — Vocard-style panel with ⏮️ Back, ⏸️/▶️ Play/Pause, ⏭️ Skip, ⏹️ Stop, 🔁 Loop, 🔀 Shuffle, 🔉/🔊 Volume buttons sent directly in the music channel
- 🔍 **Search command** — shows a select-menu of results so users can pick a track
- ⏮️ **Back command** — returns to the previously played track (track history)
- 🚪 **Auto-leave** — bot leaves the voice channel automatically when it is empty
- 🌐 **Web Dashboard** with Discord OAuth2
- 🌍 **i18n**: English and Spanish
- 🗄️ **SQLite** via aiosqlite
- 🐳 **Docker** support

## Requirements

| Requirement | Standalone (no Docker) | Docker |
|---|---|---|
| Python 3.13+ | ✅ Required | Optional — only needed if you use `install.py` or `update.py` scripts |
| Java 17+ | ✅ Required (runs Lavalink) | ❌ Not needed (Lavalink runs in its own container) |
| [ffmpeg](https://ffmpeg.org/download.html) | ✅ Required | ❌ Not needed (included in bot image) |
| Docker ≥ 20.10 + Compose v2 | ❌ Not needed | ✅ Required |

## Setup — Standalone (without Docker)

Use this path if you prefer to run everything directly on your host without Docker.

### Quick install (recommended)

Download the installer and run it. It will fetch the bot's source code from
GitHub automatically when it detects that it is not already running from inside
a cloned repository:

```bash
curl -L -o install.py https://raw.githubusercontent.com/szentigrad3/discord-music-bot/main/install.py
python install.py
```

The interactive wizard checks prerequisites, walks you through configuration,
writes `settings.json` and `lavalink/application.yml`, then starts Lavalink and
the bot automatically.

### Updating

Use `update.py` to check for and apply new releases:

```bash
# Check whether your local version is up-to-date
python update.py -c

# Download and install the latest release
python update.py -l

# Download and install a specific release tag
python update.py -v v1.2.0
```

Your `settings.json` file and `data/` directory are preserved automatically during
an update.

## Running with systemd

You can run the bot (and optionally the dashboard) as a persistent systemd service so it starts automatically on boot and restarts on failure.

### 1. Create the bot service file

Create `/etc/systemd/system/discord-music-bot.service`:

```ini
[Unit]
Description=Discord Music Bot
After=network.target

[Service]
Type=simple
User=YOUR_USER
WorkingDirectory=/path/to/discord-music-bot
ExecStart=/usr/bin/python3 -m bot.main
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

Replace `YOUR_USER` with the Linux user that should run the bot and `/path/to/discord-music-bot` with the absolute path to the cloned repository.

### 2. (Optional) Create the dashboard service file

Create `/etc/systemd/system/discord-music-bot-dashboard.service`:

```ini
[Unit]
Description=Discord Music Bot Dashboard
After=network.target

[Service]
Type=simple
User=YOUR_USER
WorkingDirectory=/path/to/discord-music-bot
ExecStart=/usr/bin/python3 -m bot.dashboard.app
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

### 3. Enable and start the services

```bash
# Reload systemd so it picks up the new unit files
sudo systemctl daemon-reload

# Enable the services to start on boot
sudo systemctl enable discord-music-bot
sudo systemctl enable discord-music-bot-dashboard   # optional

# Start the services now
sudo systemctl start discord-music-bot
sudo systemctl start discord-music-bot-dashboard    # optional
```

### Useful commands

```bash
# Check status
sudo systemctl status discord-music-bot

# View logs
sudo journalctl -u discord-music-bot -f

# Stop / restart
sudo systemctl stop discord-music-bot
sudo systemctl restart discord-music-bot
```

## Docker

Use this path if you want a fully containerised deployment. The Compose stack
manages every component for you.

### Prerequisites

- [Docker](https://docs.docker.com/get-docker/) ≥ 20.10
- [Docker Compose](https://docs.docker.com/compose/install/) v2 (`docker compose` — note: no hyphen)

### Services

The `docker-compose.yml` file defines four services:

| Service | Image | Purpose |
|---------|-------|---------|
| `bot` | Built from `Dockerfile` | The Discord music bot |
| `lavalink` | `ghcr.io/lavalink-devs/lavalink:latest` | Audio streaming server |
| `yt-cipher` | `ghcr.io/kikkia/yt-cipher:master` | YouTube cipher resolver (bypasses age/region blocks) |
| `watchtower` | `containrrr/watchtower:latest` | Automatically pulls updated images for `lavalink` and `yt-cipher` every 24 hours |

`lavalink` waits until `yt-cipher` is ready, and `bot` waits until `lavalink`
passes its health-check before starting.

### Quick install (recommended)

Download the installer and run it. It will fetch the bot's source code from
GitHub automatically when it detects that it is not already running from inside
a cloned repository:

```bash
curl -L -o install.py https://raw.githubusercontent.com/szentigrad3/discord-music-bot/main/install.py
python install.py
```

The interactive wizard checks prerequisites, walks you through configuration,
writes `settings.json` and `docker-compose.yml`, and launches all services.

### Updating (Docker)

`lavalink` and `yt-cipher` images are updated automatically every 24 hours by
Watchtower — no manual action needed.

To update docker which handles the pull and rebuild for you:

```bash
git pull
docker compose up -d --build
```

### Auto-start with systemd (optional)

To have the Docker Compose stack start automatically on boot and restart on failure, wrap it in a systemd unit file.

Create `/etc/systemd/system/discord-music-bot.service`:

```ini
[Unit]
Description=Discord Music Bot (Docker Compose)
Requires=docker.service
After=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=/path/to/discord-music-bot
ExecStart=/usr/bin/docker compose up -d
ExecStop=/usr/bin/docker compose down
TimeoutStartSec=0

[Install]
WantedBy=multi-user.target
```

Replace `/path/to/discord-music-bot` with the absolute path to the cloned repository (run `pwd` inside it to find it). Also verify the Docker binary location on your system with `which docker` and update `ExecStart`/`ExecStop` accordingly.

Then enable and start the service:

```bash
sudo systemctl daemon-reload
sudo systemctl enable discord-music-bot
sudo systemctl start discord-music-bot
```

**Useful commands:**

```bash
# Check status
sudo systemctl status discord-music-bot

# View logs (via Docker)
docker compose logs -f

# Stop / restart
sudo systemctl stop discord-music-bot
sudo systemctl restart discord-music-bot
```

## YouTube OAuth Token

Supplying a YouTube OAuth refresh token allows the bot to play age-restricted and
region-locked content. The steps below walk you through the one-time authorization
flow provided by [youtube-source](https://github.com/lavalink-devs/youtube-source).

### 1. Enable the OAuth flow

In `lavalink/application.yml` the `oauth` block already has `enabled: true`. Make sure
`skipInitialization` is `false` (the default in this repo) so that Lavalink triggers
the authorization URL on its first start without a token:

```yaml
plugins:
  youtube:
    oauth:
      enabled: true
      skipInitialization: false
```

### 2. Open the authorization URL

Watch the Lavalink output for a line like:

```
Please visit the following URL to authorize: https://www.youtube.com/device?user_code=XXXX-XXXX
```

Open that URL in your browser, sign in with your Google account, and approve the
request. You do **not** need a special account — any Google account works.

### 3. Copy the refresh token from the logs

After authorization succeeds, Lavalink prints your refresh token:

```
Refresh token: <your-token-here>
```

### 4. Persist the token in `application.yml`

Add the refresh token to `lavalink/application.yml` so that Lavalink loads it on
every startup without re-running the authorization flow:

```yaml
plugins:
  youtube:
    oauth:
      enabled: true
      refreshToken: "<your-token-here>"
```

Once a valid refresh token is loaded, Lavalink skips the authorization flow
automatically on future starts.

## Commands

### Music

| Command | Description |
|---------|-------------|
| `/play <query>` | Play a song from YouTube, SoundCloud, or Spotify |
| `/search <query>` | Search YouTube and pick a track from a select-menu |
| `/skip` | Skip the current track |
| `/back` | Go back to the previous track |
| `/skipto <position>` | Jump to a specific position in the queue |
| `/remove <position>` | Remove a track from the queue |
| `/stop` | Stop playback and clear queue |
| `/pause` | Pause playback |
| `/resume` | Resume playback |
| `/queue [page]` | Show the current queue |
| `/volume <1-100>` | Set volume |
| `/shuffle` | Shuffle the queue |
| `/repeat <off\|one\|all>` | Set repeat mode |
| `/leave` | Disconnect the bot |
| `/filter <none\|nightcore\|bassboost\|vaporwave\|8d\|karaoke\|slowed>` | Apply audio filter |
| `/nowplaying` | Show the current track |
| `/seek <seconds>` | Seek to a position in the current track |
| `/move <from> <to>` | Move a track to a different queue position |
| `/clear` | Clear the queue without stopping the current track |

### Utility

| Command | Description |
|---------|-------------|
| `/lyrics [song]` | Fetch lyrics via LRCLIB |
| `/sfx <name>` | Play a local sound effect |
| `/settings show` | Show current server settings (requires Manage Guild) |
| `/settings prefix <value>` | Set the command prefix |
| `/settings language <en\|es>` | Set the bot language |
| `/settings volume <1-100>` | Set the default playback volume |
| `/settings djrole [role]` | Set (or clear) the DJ role |
| `/settings announce <true\|false>` | Toggle now-playing announcements |
| `/ping` | Check bot latency |

## Prefix Commands

All commands also work with a configurable prefix (default `!`). Example: `!play Bohemian Rhapsody`

## Sound Effects

Place `.mp3` files in `data/sfx/` and use `/sfx <name>` (without extension).

## Configuration (settings.json)

| Key | Required | Description |
|-----|----------|-------------|
| `token` | ✅ | Bot token |
| `client_id` | ✅ | Application client ID |
| `client_secret` | Dashboard | OAuth2 client secret |
| `callback_url` | Dashboard | OAuth2 callback URL |
| `spotify_client_id` | Optional | Spotify app client ID |
| `spotify_client_secret` | Optional | Spotify app client secret |
| `session_secret` | Dashboard | Flask session secret |
| `dashboard_port` | Optional | Dashboard port (default: `3000`) |
| `database_url` | ✅ | SQLite file path (e.g. `file:./data/bot.db`) |
| `lavalink.host` | ✅ | Lavalink server host (`localhost` for standalone; `lavalink` for Docker Compose) |
| `lavalink.port` | Optional | Lavalink server port (default: `2333`) |
| `lavalink.password` | Optional | Lavalink server password (default: `youshallnotpass`) |
| `log_level` | Optional | Logging verbosity: `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL` (default: `INFO`; overridable via `LOG_LEVEL` env var) |

## License

MIT
