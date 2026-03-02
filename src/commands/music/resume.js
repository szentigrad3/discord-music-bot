import { SlashCommandBuilder } from 'discord.js';
import { getGuildSettings } from '../../db.js';
import { t } from '../../i18n/index.js';

export const data = new SlashCommandBuilder()
  .setName('resume')
  .setDescription('Resume the paused track');

export const aliases = ['unpause'];

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
  if (!player.paused) {
    const msg = t('resume.notPaused', lang);
    return isInteraction ? ctx.reply({ content: msg, ephemeral: true }) : ctx.reply(msg);
  }

  player.resume();
  const msg = t('resume.resumed', lang);
  return isInteraction ? ctx.reply(msg) : ctx.reply(msg);
}
