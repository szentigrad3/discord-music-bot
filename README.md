# Discord Music Bot

A feature-rich Discord music bot built with Python 3.12, discord.py v2, and yt-dlp. Supports YouTube, SoundCloud, Twitch, Spotify, slash commands, prefix commands, audio filters, and a web dashboard.

## Features

- 🎵 **Multi-platform**: YouTube, SoundCloud, Twitch, Spotify (via yt-dlp)
- 🔗 **Playlist support**: YouTube playlists (up to 50 tracks), Spotify albums/playlists
- 🎛️ **Audio filters**: Nightcore, Bass Boost
- 🔁 **Repeat modes**: Off, One, All
- 🔀 **Shuffle** queue
- 📋 **Slash commands + prefix commands**
- 🌐 **Web Dashboard** with Discord OAuth2
- 🌍 **i18n**: English and Spanish
- 🗄️ **SQLite** via aiosqlite
- 🐳 **Docker** support

## Requirements

- Python 3.12+
- ffmpeg installed on system (or use Docker)

## Setup

### 1. Clone & install

```bash
git clone <repo-url>
cd discord-music-bot
pip install -r requirements.txt
```

### 2. Configure environment

```bash
cp .env.example .env
```

Edit `.env` and fill in:
- `DISCORD_TOKEN` — your bot token from [Discord Developer Portal](https://discord.com/developers/applications)
- `DISCORD_CLIENT_ID` — your application's client ID
- `DISCORD_CLIENT_SECRET` — OAuth2 client secret (for dashboard)
- `DISCORD_CALLBACK_URL` — OAuth2 callback URL (e.g. `http://localhost:3000/auth/discord/callback`)
- `SPOTIFY_CLIENT_ID` / `SPOTIFY_CLIENT_SECRET` — from [Spotify Developer Dashboard](https://developer.spotify.com/dashboard) (optional)
- `SESSION_SECRET` — a random secret string for session cookies

### 3. Deploy slash commands

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
cp .env.example .env
# Edit .env

docker compose up -d
```

The dashboard will be available at `http://localhost:3000`.

## Commands

### Music

| Command | Description |
|---------|-------------|
| `/play <query>` | Play a song from YouTube, SoundCloud, or Spotify |
| `/skip` | Skip the current track |
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
| `/settings` | View/change server settings (requires Manage Guild) |
| `/ping` | Check bot latency |

## Prefix Commands

All commands also work with a configurable prefix (default `!`). Example: `!play Bohemian Rhapsody`

## Sound Effects

Place `.mp3` files in `data/sfx/` and use `/sfx <name>` (without extension).

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `DISCORD_TOKEN` | ✅ | Bot token |
| `DISCORD_CLIENT_ID` | ✅ | Application client ID |
| `DISCORD_CLIENT_SECRET` | Dashboard | OAuth2 client secret |
| `DISCORD_CALLBACK_URL` | Dashboard | OAuth2 callback URL |
| `SPOTIFY_CLIENT_ID` | Optional | Spotify app client ID |
| `SPOTIFY_CLIENT_SECRET` | Optional | Spotify app client secret |
| `SESSION_SECRET` | Dashboard | Flask session secret |
| `DASHBOARD_PORT` | Optional | Dashboard port (default: 3000) |
| `DATABASE_URL` | ✅ | SQLite file path (e.g. `file:./data/bot.db`) |

## License

MIT
