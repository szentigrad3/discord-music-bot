/**
 * Represents a single music track.
 */
export class Track {
  /**
   * @param {object} opts
   * @param {string} opts.title
   * @param {string} opts.url
   * @param {string} opts.duration  e.g. "3:42"
   * @param {string} [opts.thumbnail]
   * @param {string} [opts.requestedBy]
   */
  constructor({ title, url, duration, thumbnail, requestedBy }) {
    this.title = title;
    this.url = url;
    this.duration = duration ?? 'Unknown';
    this.thumbnail = thumbnail ?? null;
    this.requestedBy = requestedBy ?? null;
  }

  /**
   * Format duration from seconds to mm:ss or hh:mm:ss.
   * @param {number} seconds
   * @returns {string}
   */
  static formatDuration(seconds) {
    if (!seconds || isNaN(seconds)) return 'Live';
    const h = Math.floor(seconds / 3600);
    const m = Math.floor((seconds % 3600) / 60);
    const s = Math.floor(seconds % 60);
    if (h > 0) return `${h}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
    return `${m}:${String(s).padStart(2, '0')}`;
  }

  /**
   * Build a Track from yt-dlp info object.
   * @param {object} info - yt-dlp JSON info
   * @param {string} [requestedBy]
   * @returns {Track}
   */
  static fromYtDlpInfo(info, requestedBy) {
    return new Track({
      title: info.title ?? 'Unknown Title',
      url: info.webpage_url ?? info.url,
      duration: Track.formatDuration(info.duration),
      thumbnail: info.thumbnail ?? info.thumbnails?.[0]?.url ?? null,
      requestedBy,
    });
  }
}
