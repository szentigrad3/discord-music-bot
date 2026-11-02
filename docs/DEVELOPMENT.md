# Development and deployment checks

Changes are first reviewed on a branch, then merged after the unit suite and
an actual Discord/Lavalink smoke test. CI is not a substitute for live playback.

## CachyOS / Linux development checks

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt pyyaml
python -m compileall -q bot tests install.py update.py update_lavalink.py
python -m unittest discover -s tests -p 'test_*.py' -v
docker compose config --quiet
```

The Compose check requires Docker Compose v2. Do not commit `settings.json`,
Discord bot credentials, OAuth refresh tokens, live databases or Lavalink logs.

## Live smoke test before release

1. Start the stack and inspect `docker compose logs --tail=100 bot lavalink`.
2. Verify Discord slash commands are present and that the bot joins a voice channel.
3. Queue, play, pause, seek, skip and stop an authorized test track.
4. Test a YouTube search, a SoundCloud source and a Spotify link where configured.
5. Disconnect/reconnect Discord and confirm application commands do not re-sync on every reconnect.
6. Check queue/loop/shuffle and leaving an empty voice channel.
7. Verify dashboard OAuth2 login and test on a non-production guild first.
8. Confirm permissions and secrets are not visible in logs or images.

## Docker precautions

The Compose stack currently includes Watchtower, which receives access to the
Docker daemon socket and can update services automatically. Review its security
tradeoffs and use explicitly controlled updates for production if possible.
The Lavalink password example is a placeholder and should be replaced consistently
in both the bot settings and Lavalink configuration before exposing a deployment.
The dashboard should be behind TLS and authentication in production.

## All-in-one test command

From the repository root, with development dependencies installed:

```bash
bash scripts/test-all.sh
```

This performs Python compilation, the complete offline unit suite, and Docker
Compose validation when Docker Compose v2 is installed. It does **not** connect
to Discord, start Lavalink, play music or alter the live bot.

## November 2026 reliability work

- Discord slash commands sync once per successful process start, retrying after
  transient failures on a subsequent ready event.
- Simultaneous voice join requests for a guild share one connection attempt.
- Empty-channel auto-leave is debounced and cancelled when a listener returns.
- Playback events are checked against the active track; failures drain queued
  entries iteratively to avoid recursion.
- A guild may hold up to 500 *pending* tracks. The currently playing track is
  not counted; additions that would exceed the limit fail atomically.
- Spotify playlist searches resolve up to three matches at a time and retain
  playlist order. Playlist loading remains limited to the first 50 entries.
- Dashboard authentication/session input validation has regression coverage.
- The GitHub tag-release workflow tests the tagged source before publication.

### Remaining live-release gates

Check playback sources and voice event ordering with a real Discord test guild
and Lavalink node, including `finished`, `stopped`, `loadFailed` and
`replaced` event reasons. Also verify the dashboard behind its intended
HTTPS reverse proxy. Offline tests cannot prove source-provider availability.
