import { SlashCommandBuilder, EmbedBuilder } from 'discord.js';
import { getGuildSettings } from '../../db.js';
import { t } from '../../i18n/index.js';
import { REPEAT_MODES } from '../../music/Player.js';

export const data = new SlashCommandBuilder()
  .setName('nowplaying')
  .setDescription('Show the currently playing track');

export const aliases = ['np', 'current'];

export async function execute(ctx) {
  const isInteraction = ctx.isChatInputCommand?.();
  const guild = ctx.guild;
  const settings = await getGuildSettings(guild.id).catch(() => ({ language: 'en' }));
  const lang = settings.language;

  const player = ctx.client.queues.get(guild.id);
  if (!player || !player.current) {
    const msg = t('errors.nothingPlaying', lang);
    return isInteraction ? ctx.reply({ content: msg, ephemeral: true }) : ctx.reply(msg);
  }

  const track = player.current;
  const repeatLabels = { [REPEAT_MODES.OFF]: 'Off', [REPEAT_MODES.ONE]: 'One', [REPEAT_MODES.ALL]: 'All' };

  const embed = new EmbedBuilder()
    .setColor(0x5865f2)
    .setTitle('🎵 Now Playing')
    .setDescription(`**[${track.title}](${track.url})**`)
    .addFields(
      { name: 'Duration', value: track.duration, inline: true },
      { name: 'Requested by', value: track.requestedBy ?? 'Unknown', inline: true },
      { name: 'Volume', value: `${player.volume}%`, inline: true },
      { name: 'Filter', value: player.filter, inline: true },
      { name: 'Repeat', value: repeatLabels[player.repeatMode], inline: true },
      { name: 'Queue', value: `${player.tracks.length} track(s)`, inline: true },
    );

  if (track.thumbnail) embed.setThumbnail(track.thumbnail);

  return isInteraction ? ctx.reply({ embeds: [embed] }) : ctx.reply({ embeds: [embed] });
}
