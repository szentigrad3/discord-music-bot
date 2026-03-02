import { SlashCommandBuilder, EmbedBuilder } from 'discord.js';
import { getGuildSettings } from '../../db.js';
import { t } from '../../i18n/index.js';

const PAGE_SIZE = 10;

export const data = new SlashCommandBuilder()
  .setName('queue')
  .setDescription('Show the current queue')
  .addIntegerOption(opt =>
    opt.setName('page').setDescription('Page number').setMinValue(1));

export const aliases = ['q'];

export async function execute(ctx, args) {
  const isInteraction = ctx.isChatInputCommand?.();
  const guild = ctx.guild;
  const settings = await getGuildSettings(guild.id).catch(() => ({ language: 'en' }));
  const lang = settings.language;

  const player = ctx.client.queues.get(guild.id);
  if (!player || (!player.current && player.tracks.length === 0)) {
    const msg = t('errors.queueEmpty', lang);
    return isInteraction ? ctx.reply({ content: msg, ephemeral: true }) : ctx.reply(msg);
  }

  const page = (isInteraction ? ctx.options.getInteger('page') : parseInt(args?.[0])) || 1;
  const totalPages = Math.max(1, Math.ceil(player.tracks.length / PAGE_SIZE));
  const clampedPage = Math.min(page, totalPages);
  const start = (clampedPage - 1) * PAGE_SIZE;
  const entries = player.tracks.slice(start, start + PAGE_SIZE);

  const repeatLabels = { 0: 'Off', 1: 'One', 2: 'All' };

  const embed = new EmbedBuilder()
    .setColor(0x5865f2)
    .setTitle(`🎶 Queue — Page ${clampedPage}/${totalPages}`)
    .addFields(
      { name: 'Now Playing', value: player.current ? `**[${player.current.title}](${player.current.url})** (${player.current.duration})` : 'Nothing' },
    );

  if (entries.length > 0) {
    const list = entries.map((tr, i) =>
      `\`${start + i + 1}.\` [${tr.title}](${tr.url}) — ${tr.duration}`
    ).join('\n');
    embed.addFields({ name: 'Up Next', value: list });
  }

  embed.setFooter({
    text: `${player.tracks.length} track(s) in queue • Repeat: ${repeatLabels[player.repeatMode]} • Volume: ${player.volume}%`,
  });

  return isInteraction ? ctx.reply({ embeds: [embed] }) : ctx.reply({ embeds: [embed] });
}
