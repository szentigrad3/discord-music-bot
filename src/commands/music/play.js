import { SlashCommandBuilder, EmbedBuilder } from 'discord.js';
import { getOrCreatePlayer, resolveTracks } from '../../music/Queue.js';
import { getGuildSettings } from '../../db.js';
import { t } from '../../i18n/index.js';

export const data = new SlashCommandBuilder()
  .setName('play')
  .setDescription('Play a song or playlist from YouTube, SoundCloud, or Spotify')
  .addStringOption(opt =>
    opt.setName('query')
      .setDescription('Song name, URL, or Spotify/YouTube playlist link')
      .setRequired(true));

export const aliases = ['p'];

/** @param {import('discord.js').ChatInputCommandInteraction|import('discord.js').Message} ctx */
export async function execute(ctx, args) {
  const isInteraction = ctx.isChatInputCommand?.();
  const guild = ctx.guild;
  const member = isInteraction ? ctx.member : ctx.member;
  const query = isInteraction ? ctx.options.getString('query') : args.join(' ');

  if (!query) {
    const msg = 'Please provide a song name or URL.';
    return isInteraction ? ctx.reply({ content: msg, ephemeral: true }) : ctx.reply(msg);
  }

  const voiceChannel = member?.voice?.channel;
  if (!voiceChannel) {
    const settings = await getGuildSettings(guild.id).catch(() => ({ language: 'en' }));
    const msg = t('errors.notInVoice', settings.language);
    return isInteraction ? ctx.reply({ content: msg, ephemeral: true }) : ctx.reply(msg);
  }

  const botMember = guild.members.me;
  if (!voiceChannel.permissionsFor(botMember).has(['Connect', 'Speak'])) {
    const msg = 'I need **Connect** and **Speak** permissions in your voice channel.';
    return isInteraction ? ctx.reply({ content: msg, ephemeral: true }) : ctx.reply(msg);
  }

  if (isInteraction) await ctx.deferReply();

  const settings = await getGuildSettings(guild.id).catch(() => ({ language: 'en', defaultVolume: 80 }));
  const lang = settings.language;
  const textChannel = isInteraction ? ctx.channel : ctx.channel;

  try {
    const tracks = await resolveTracks(query, member.user?.tag ?? member.tag);

    if (!tracks || tracks.length === 0) {
      const msg = t('errors.noResults', lang);
      return isInteraction ? ctx.editReply(msg) : ctx.reply(msg);
    }

    const player = getOrCreatePlayer(guild, voiceChannel, textChannel, ctx.client);
    player.volume = settings.defaultVolume ?? 80;

    if (tracks.length === 1) {
      player.enqueue(tracks[0]);
      const embed = new EmbedBuilder()
        .setColor(0x5865f2)
        .setTitle(t('play.added', lang))
        .setDescription(`**[${tracks[0].title}](${tracks[0].url})**`)
        .addFields({ name: 'Duration', value: tracks[0].duration, inline: true });
      if (tracks[0].thumbnail) embed.setThumbnail(tracks[0].thumbnail);
      return isInteraction ? ctx.editReply({ embeds: [embed] }) : ctx.reply({ embeds: [embed] });
    } else {
      player.enqueueMany(tracks);
      const embed = new EmbedBuilder()
        .setColor(0x5865f2)
        .setTitle(t('play.addedPlaylist', lang))
        .setDescription(t('play.addedPlaylistDesc', lang, { count: tracks.length }));
      return isInteraction ? ctx.editReply({ embeds: [embed] }) : ctx.reply({ embeds: [embed] });
    }
  } catch (err) {
    console.error('[play]', err);
    const msg = `❌ ${err.message}`;
    return isInteraction ? ctx.editReply(msg) : ctx.reply(msg);
  }
}
