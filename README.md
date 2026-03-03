# Discord Music Bot

A feature-rich Discord music bot built with Python 3.12, discord.py v2, and Lavalink. Supports YouTube, SoundCloud, Twitch, Spotify, slash commands, prefix commands, audio filters, and a web dashboard.

## Features

- 🎵 **Multi-platform**: YouTube, SoundCloud, Twitch, Spotify
- 🔗 **Playlist support**: YouTube playlists (up to 50 tracks), Spotify albums/playlists
- 🎛️ **Audio filters**: Nightcore, Bass Boost (powered by Lavalink)
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

- Python 3.12+
- **Lavalink** server (included in Docker Compose setup)

## Setup

### 1. Clone & install

Run the provided installer — it checks prerequisites, walks you through
an interactive configuration wizard, writes `settings.json` and
`docker-compose.yml`, downloads `lavalink/Lavalink.jar`, then launches
all services via Docker:

```bash
git clone <repo-url>
cd discord-music-bot
python install.py
```

Or install manually (without Docker, installs packages into the active Python environment):

```bash
pip install -r requirements.txt
```

### Updating

Use `update.py` to check for and apply new releases (mirrors the Vocard
update-script pattern):

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

### 2. Configure

```bash
cp 'settings Example.json' settings.json
```

Edit `settings.json` and fill in:
- `token` — your bot token from [Discord Developer Portal](https://discord.com/developers/applications)
- `client_id` — your application's client ID
- `client_secret` — OAuth2 client secret (for dashboard)
- `callback_url` — OAuth2 callback URL (e.g. `http://localhost:3000/auth/discord/callback`)
- `spotify_client_id` / `spotify_client_secret` — from [Spotify Developer Dashboard](https://developer.spotify.com/dashboard) (optional)
- `session_secret` — a random secret string for session cookies
- `lavalink.host` — Lavalink server host (default: `lavalink`)
- `lavalink.port` — Lavalink server port (default: `2333`)
- `lavalink.password` — Lavalink server password (default: `youshallnotpass`)

### 3. Deploy slash commands

Slash commands are synced automatically on every bot startup. You can also
deploy them manually before the first run:

```bash
python deploy_commands.py
```

### 4. Start the bot

```bash
python -m bot.main
```

### 5. Start the dashboard (optional)

```bash
python -m bot.dashboard.app
```

## Docker

```bash
cp 'settings Example.json' settings.json
# Edit settings.json

docker compose up -d
```

The dashboard will be available at `http://localhost:3000`.

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
| `/filter <none\|nightcore\|bassboost>` | Apply audio filter |
| `/nowplaying` | Show the current track |

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
| `lavalink.host` | ✅ | Lavalink server host (default: `lavalink`) |
| `lavalink.port` | Optional | Lavalink server port (default: `2333`) |
| `lavalink.password` | Optional | Lavalink server password (default: `youshallnotpass`) |

## License

MIT
