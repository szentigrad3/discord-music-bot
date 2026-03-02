import { SlashCommandBuilder } from 'discord.js';
import { getGuildSettings } from '../../db.js';
import { t } from '../../i18n/index.js';

export const data = new SlashCommandBuilder()
  .setName('shuffle')
  .setDescription('Shuffle the queue');

export async function execute(ctx) {
  const isInteraction = ctx.isChatInputCommand?.();
  const guild = ctx.guild;
  const settings = await getGuildSettings(guild.id).catch(() => ({ language: 'en' }));
  const lang = settings.language;

  const player = ctx.client.queues.get(guild.id);
  if (!player || player.tracks.length < 2) {
    const msg = t('errors.notEnoughTracks', lang);
    return isInteraction ? ctx.reply({ content: msg, ephemeral: true }) : ctx.reply(msg);
  }

  player.shuffle();
  const msg = t('shuffle.shuffled', lang, { count: player.tracks.length });
  return isInteraction ? ctx.reply(msg) : ctx.reply(msg);
}
