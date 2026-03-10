# Changelog

All notable changes to this project will be documented in this file.

## [v1.1.3] - 2026-03-10

### Features
- Auto-update Lavalink and plugins at bot startup (non-Docker)

### Improvements
- Standalone self-bootstrapping installer (`install.py`) with `curl` one-liner support
- `install.py` now reads/writes template files directly; validates all config files
- Sync docker and non-docker Lavalink configs during update

### Bug Fixes
- Fix `shutil.Error` when `IGNORE_FILES` directory already exists in both archive and `ROOT_DIR`
- Fix `update.py` leaving `discord-music-bot-main` directory behind after update

### Documentation
- Updated README for Docker and non-Docker setup paths
- Streamlined setup instructions and removed redundant manual steps

## [v1.1.2] - 2026-03-10

### Improvements
- Keep docker and non-docker Lavalink configs in sync during update
- Preserve Docker credentials (Lavalink password, YouTube OAuth token) across updates

## [v1.1.1] - 2026-03-09

### Features
- Auto-update Lavalink JAR and plugins via Watchtower (Docker) and `update_lavalink.py` (non-Docker)
- MWEB client added as cipher-free YouTube fallback

## [v1.1.0] - 2026-03-08

### Features
- Expand audio filters (Nightcore, Bass Boost, Vaporwave, 8D Audio, Karaoke, Slowed)
- Add `seek`, `move`, `clear` commands
- DJ role enforcement
- Progress bar in Now Playing embed
