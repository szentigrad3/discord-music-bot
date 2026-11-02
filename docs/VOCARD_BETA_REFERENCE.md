# Vocard beta reference and compatibility notes

This project uses [Vocard's beta branch](https://github.com/ChocoMeow/Vocard/tree/beta)
as a *design and behavior reference*, not as a drop-in upstream dependency.

Vocard beta has a dedicated `voicelink/queue.py` with explicit queue capacity,
queue-position checks, repeat-state management, and history controls. This bot
currently has a more compact `bot/music/player.py` queue implementation.

## Adaptation direction

- Keep current `bot/voicelink` integration until changes are covered by tests.
- Validate 1-based queue positions before modifying queued tracks.
- Preserve current controller commands while improving failure paths.
- Treat simultaneous skip/stop/track-end events as a separate concurrency task:
  verify the event ordering with a live Lavalink node before changing playback.
- Compare queue repeat/history semantics against Vocard beta when introducing
  persistent queue support; avoid importing beta source directly.
- Use actual Discord and Lavalink smoke tests before declaring voice compatibility.

Vocard beta is MIT licensed. If any substantive source code is reused in the
future, retain the original license and copyright notices as required.
