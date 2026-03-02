import {
  createAudioPlayer,
  createAudioResource,
  AudioPlayerStatus,
  VoiceConnectionStatus,
  entersState,
  StreamType,
  getVoiceConnection,
} from '@discordjs/voice';
import ytDlpExec from 'yt-dlp-exec';
import ffmpegStatic from 'ffmpeg-static';
import { spawn } from 'child_process';
import { Track } from './Track.js';

export const FILTERS = {
  none: null,
  nightcore: 'atempo=1.3,asetrate=44100*1.25',
  bassboost: 'bass=g=20,dynaudnorm=f=200',
};

export const REPEAT_MODES = { OFF: 0, ONE: 1, ALL: 2 };

export class MusicPlayer {
  /**
   * @param {string} guildId
   * @param {import('discord.js').Client} client
   */
  constructor(guildId, client) {
    this.guildId = guildId;
    this.client = client;

    /** @type {Track[]} */
    this.tracks = [];
    this.current = null;
    this.volume = 80;
    this.filter = 'none';
    this.repeatMode = REPEAT_MODES.OFF;
    this.paused = false;
    this.textChannel = null;

    this.audioPlayer = createAudioPlayer();
    this._bindPlayerEvents();
  }

  _bindPlayerEvents() {
    this.audioPlayer.on(AudioPlayerStatus.Idle, () => {
      this._onTrackEnd();
    });

    this.audioPlayer.on('error', err => {
      console.error(`[Player:${this.guildId}] Audio player error:`, err.message);
      this._onTrackEnd();
    });
  }

  /**
   * Called when the current track ends or errors.
   */
  _onTrackEnd() {
    if (this.repeatMode === REPEAT_MODES.ONE && this.current) {
      this._play(this.current);
      return;
    }

    if (this.repeatMode === REPEAT_MODES.ALL && this.current) {
      this.tracks.push(this.current);
    }

    this.current = null;

    if (this.tracks.length > 0) {
      const next = this.tracks.shift();
      this._play(next);
    } else {
      this._cleanup();
    }
  }

  /**
   * Play a track immediately.
   * @param {Track} track
   */
  async _play(track) {
    this.current = track;

    try {
      const resource = await this._createResource(track.url);
      this.audioPlayer.play(resource);

      const connection = getVoiceConnection(this.guildId);
      if (connection) {
        connection.subscribe(this.audioPlayer);
      }

      if (this.textChannel) {
        const settings = await this._getSettings();
        if (settings?.announceNowPlaying) {
          const { EmbedBuilder } = await import('discord.js');
          const embed = new EmbedBuilder()
            .setColor(0x5865f2)
            .setTitle('🎵 Now Playing')
            .setDescription(`**[${track.title}](${track.url})**`)
            .addFields(
              { name: 'Duration', value: track.duration, inline: true },
              { name: 'Requested by', value: track.requestedBy ?? 'Unknown', inline: true },
            );
          if (track.thumbnail) embed.setThumbnail(track.thumbnail);
          this.textChannel.send({ embeds: [embed] }).catch(() => {});
        }
      }
    } catch (err) {
      console.error(`[Player:${this.guildId}] Failed to play "${track.title}":`, err.message);
      this._onTrackEnd();
    }
  }

  /**
   * Create an AudioResource from a URL, piping through ffmpeg with active filter.
   * @param {string} url
   * @returns {Promise<import('@discordjs/voice').AudioResource>}
   */
  async _createResource(url) {
    // Get direct audio URL from yt-dlp
    const info = await ytDlpExec(url, {
      format: 'bestaudio/best',
      getUrl: true,
      noPlaylist: true,
    });

    const directUrl = info.trim();
    const filterStr = FILTERS[this.filter];
    const volumeFilter = `volume=${this.volume / 100}`;
    const filterChain = filterStr ? `${filterStr},${volumeFilter}` : volumeFilter;

    const ffmpegArgs = [
      '-reconnect', '1',
      '-reconnect_streamed', '1',
      '-reconnect_delay_max', '5',
      '-i', directUrl,
      '-af', filterChain,
      '-f', 's16le',
      '-ar', '48000',
      '-ac', '2',
      'pipe:1',
    ];

    const ffmpegProcess = spawn(ffmpegStatic, ffmpegArgs, {
      stdio: ['ignore', 'pipe', 'ignore'],
    });

    return createAudioResource(ffmpegProcess.stdout, {
      inputType: StreamType.Raw,
      inlineVolume: false,
    });
  }

  /**
   * Add a track to the queue and start playing if idle.
   * @param {Track} track
   */
  enqueue(track) {
    if (this.audioPlayer.state.status === AudioPlayerStatus.Idle && !this.current) {
      this._play(track);
    } else {
      this.tracks.push(track);
    }
  }

  /**
   * Add multiple tracks.
   * @param {Track[]} tracks
   */
  enqueueMany(tracks) {
    if (tracks.length === 0) return;
    if (this.audioPlayer.state.status === AudioPlayerStatus.Idle && !this.current) {
      const [first, ...rest] = tracks;
      this.tracks.push(...rest);
      this._play(first);
    } else {
      this.tracks.push(...tracks);
    }
  }

  skip() {
    this.audioPlayer.stop(true);
  }

  pause() {
    this.audioPlayer.pause();
    this.paused = true;
  }

  resume() {
    this.audioPlayer.unpause();
    this.paused = false;
  }

  stop() {
    this.tracks = [];
    this.repeatMode = REPEAT_MODES.OFF;
    this.audioPlayer.stop(true);
    this._cleanup();
  }

  /** @param {number} vol 1-100 */
  setVolume(vol) {
    this.volume = Math.max(1, Math.min(100, vol));
    // Restart current track to apply new volume (no inline volume manipulation)
    if (this.current) {
      this._play(this.current);
    }
  }

  /** @param {string} filterName */
  setFilter(filterName) {
    if (!(filterName in FILTERS)) return false;
    this.filter = filterName;
    if (this.current) {
      this._play(this.current);
    }
    return true;
  }

  shuffle() {
    for (let i = this.tracks.length - 1; i > 0; i--) {
      const j = Math.floor(Math.random() * (i + 1));
      [this.tracks[i], this.tracks[j]] = [this.tracks[j], this.tracks[i]];
    }
  }

  /** @param {number} mode REPEAT_MODES value */
  setRepeat(mode) {
    this.repeatMode = mode;
  }

  _cleanup() {
    const connection = getVoiceConnection(this.guildId);
    if (connection) {
      connection.destroy();
    }
    this.client.queues.delete(this.guildId);
  }

  async _getSettings() {
    try {
      const { getGuildSettings } = await import('../db.js');
      return getGuildSettings(this.guildId);
    } catch {
      return null;
    }
  }
}
