import { joinVoiceChannel } from '@discordjs/voice';
import { MusicPlayer } from './Player.js';
import { Track } from './Track.js';
import ytDlpExec from 'yt-dlp-exec';
import SpotifyWebApi from 'spotify-web-api-node';

let spotifyApi = null;
let spotifyTokenExpiry = 0;

if (process.env.SPOTIFY_CLIENT_ID && process.env.SPOTIFY_CLIENT_SECRET) {
  spotifyApi = new SpotifyWebApi({
    clientId: process.env.SPOTIFY_CLIENT_ID,
    clientSecret: process.env.SPOTIFY_CLIENT_SECRET,
  });
}

async function ensureSpotifyToken() {
  if (!spotifyApi) return false;
  if (Date.now() < spotifyTokenExpiry) return true;
  try {
    const data = await spotifyApi.clientCredentialsGrant();
    spotifyApi.setAccessToken(data.body.access_token);
    spotifyTokenExpiry = Date.now() + (data.body.expires_in - 60) * 1000;
    return true;
  } catch (err) {
    console.warn('[Spotify] Failed to get token:', err.message);
    return false;
  }
}

/**
 * Get or create a MusicPlayer for a guild, joining the voice channel.
 * @param {import('discord.js').Guild} guild
 * @param {import('discord.js').VoiceChannel} voiceChannel
 * @param {import('discord.js').TextChannel} textChannel
 * @param {import('discord.js').Client} client
 * @returns {MusicPlayer}
 */
export function getOrCreatePlayer(guild, voiceChannel, textChannel, client) {
  if (client.queues.has(guild.id)) {
    return client.queues.get(guild.id);
  }

  const player = new MusicPlayer(guild.id, client);
  player.textChannel = textChannel;

  const connection = joinVoiceChannel({
    channelId: voiceChannel.id,
    guildId: guild.id,
    adapterCreator: guild.voiceAdapterCreator,
    selfDeaf: true,
  });

  connection.subscribe(player.audioPlayer);
  client.queues.set(guild.id, player);
  return player;
}

/**
 * Resolve a query/URL into Track(s) via yt-dlp or Spotify.
 * @param {string} query
 * @param {string} [requestedBy]
 * @returns {Promise<Track[]>}
 */
export async function resolveTracks(query, requestedBy) {
  // --- Spotify ---
  if (/open\.spotify\.com\/(track|album|playlist)\//.test(query)) {
    return resolveSpotify(query, requestedBy);
  }

  // --- YouTube playlist ---
  if (/youtube\.com\/playlist\?list=/.test(query) || /\?list=/.test(query)) {
    return resolveYouTubePlaylist(query, requestedBy);
  }

  // --- Plain search or direct URL ---
  return resolveYouTube(query, requestedBy);
}

async function resolveYouTube(query, requestedBy) {
  const isUrl = /^https?:\/\//.test(query);
  const target = isUrl ? query : `ytsearch:${query}`;

  try {
    const info = await ytDlpExec(target, {
      dumpSingleJson: true,
      noPlaylist: true,
      noWarnings: true,
      preferFreeFormats: true,
      addHeader: ['referer:youtube.com', 'user-agent:googlebot'],
    });

    if (info.entries) {
      const entry = info.entries[0];
      return [Track.fromYtDlpInfo(entry, requestedBy)];
    }
    return [Track.fromYtDlpInfo(info, requestedBy)];
  } catch (err) {
    throw new Error(`Could not find: ${query} — ${err.message}`);
  }
}

async function resolveYouTubePlaylist(url, requestedBy) {
  try {
    const info = await ytDlpExec(url, {
      dumpSingleJson: true,
      flatPlaylist: true,
      noWarnings: true,
      playlistEnd: 50,
    });

    const entries = info.entries ?? [info];
    return entries.slice(0, 50).map(e => new Track({
      title: e.title ?? 'Unknown',
      url: e.url ?? e.webpage_url ?? `https://www.youtube.com/watch?v=${e.id}`,
      duration: Track.formatDuration(e.duration),
      thumbnail: e.thumbnail ?? e.thumbnails?.[0]?.url ?? null,
      requestedBy,
    }));
  } catch (err) {
    throw new Error(`Failed to load playlist: ${err.message}`);
  }
}

async function resolveSpotify(url, requestedBy) {
  const ok = await ensureSpotifyToken();
  if (!ok) throw new Error('Spotify support is not configured.');

  const trackMatch = url.match(/open\.spotify\.com\/track\/([A-Za-z0-9]+)/);
  const albumMatch = url.match(/open\.spotify\.com\/album\/([A-Za-z0-9]+)/);
  const playlistMatch = url.match(/open\.spotify\.com\/playlist\/([A-Za-z0-9]+)/);

  let trackNames = [];

  if (trackMatch) {
    const data = await spotifyApi.getTrack(trackMatch[1]);
    const t = data.body;
    trackNames.push(`${t.artists[0].name} ${t.name}`);
  } else if (albumMatch) {
    const data = await spotifyApi.getAlbumTracks(albumMatch[1], { limit: 50 });
    for (const t of data.body.items.slice(0, 50)) {
      trackNames.push(`${t.artists[0].name} ${t.name}`);
    }
  } else if (playlistMatch) {
    const data = await spotifyApi.getPlaylistTracks(playlistMatch[1], { limit: 50 });
    for (const item of data.body.items.slice(0, 50)) {
      if (item.track) trackNames.push(`${item.track.artists[0].name} ${item.track.name}`);
    }
  } else {
    throw new Error('Unsupported Spotify URL.');
  }

  // Resolve first track immediately; return placeholders for the rest
  const tracks = [];
  for (const name of trackNames) {
    try {
      const [track] = await resolveYouTube(name, requestedBy);
      tracks.push(track);
    } catch {
      // skip unresolvable tracks
    }
  }
  return tracks;
}
