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

## Lavalink API smoke test (no Discord token required)

The new read-only check verifies Lavalink's authenticated `/version` and
`/v4/info` endpoints, using your existing `settings.json`. The password
is sent only to the configured Lavalink server and never printed.

Standalone installation:

```bash
python scripts/lavalink_smoke.py
```

Docker Compose installation:

```bash
docker compose exec -T bot python scripts/lavalink_smoke.py
```

This verifies the REST API version and reports loaded plugin names. It does
**not** prove live YouTube/Spotify media extraction, voice WS forwarding,
Discord permissions, or audible playback. Use the real-guild smoke checklist
above for those release gates.

## Saved playlists

`/playlist save`, `/playlist list`, `/playlist load` and
`/playlist delete` use the SQLite `SavedPlaylists` table, partitioned
by Discord guild and user. The schema is created idempotently at startup.
Each user can save up to 20 playlists with up to 50 original track URLs each.
Stored tracks are re-resolved at load time rather than using ephemeral encoded
Lavalink tracks. Multiple resolution requests are bounded at three in
parallel; unresolvable tracks are skipped.

To confirm persistence, save a small playlist, restart the bot, list and load
it, then delete it. Do not publish your production `data/bot.db` or
`settings.json` in a public support log.

## Configuration preflight (no external connections)

```bash
python scripts/doctor.py
# Optional: fail on warnings as well as configuration errors
python scripts/doctor.py --strict
```

The doctor checks essential bot credentials are configured, Lavalink host,
port and password fields are usable, and any configured dashboard OAuth
settings are coherent. It deliberately never prints tokens or passwords.
It is safe to run before a deployment, but cannot guarantee that a Discord
token is actually valid or that a Lavalink server is reachable.

## November development additions

- Initial Lavalink node creation is now supervised: transient failures
  trigger bounded exponential retries without blocking Discord's ready event.
  Voicelink retains responsibility for reconnecting registered nodes.
- Local aiohttp integration tests exercise authenticated Lavalink REST
  requests against a fake loopback-only server, independent of public APIs.
- Concurrent Spotify searches share one token-refresh operation, with
  monotonic expiry checks.
- Optional audio-filter failures no longer cause a playing track to be
  discarded. The player commits volume and filter state only on successful
  Lavalink requests.
- Saved-playlist editing adds show, rename, add-current-track and remove,
  with transactional SQLite updates and explicit ownership checks.
- Prefix playlist list/show results are delivered privately by DM (or report
  a generic error when DMs are closed); slash responses are ephemeral.

Additional live checks: save, rename, add, remove and load a playlist in a
private test server; verify that no private listing is exposed in public
prefix channels. Restart Lavalink while the bot is running and confirm
recovery without duplicate Discord slash-command registration. Confirm
playback, skip/back/skipto and dashboard OAuth after node recovery.
