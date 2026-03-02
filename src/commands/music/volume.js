import { SlashCommandBuilder } from 'discord.js';
import { getGuildSettings } from '../../db.js';
import { t } from '../../i18n/index.js';

export const data = new SlashCommandBuilder()
  .setName('volume')
  .setDescription('Set the playback volume (1–100)')
  .addIntegerOption(opt =>
    opt.setName('level')
      .setDescription('Volume level 1–100')
      .setRequired(true)
      .setMinValue(1)
      .setMaxValue(100));

export const aliases = ['vol'];

export async function execute(ctx, args) {
  const isInteraction = ctx.isChatInputCommand?.();
  const guild = ctx.guild;
  const settings = await getGuildSettings(guild.id).catch(() => ({ language: 'en' }));
  const lang = settings.language;

  const level = isInteraction
    ? ctx.options.getInteger('level')
    : parseInt(args?.[0]);

  if (!level || level < 1 || level > 100) {
    const msg = 'Please provide a volume between 1 and 100.';
    return isInteraction ? ctx.reply({ content: msg, ephemeral: true }) : ctx.reply(msg);
  }

  const player = ctx.client.queues.get(guild.id);
  if (!player) {
    const msg = t('errors.nothingPlaying', lang);
    return isInteraction ? ctx.reply({ content: msg, ephemeral: true }) : ctx.reply(msg);
  }

  player.setVolume(level);
  const msg = t('volume.set', lang, { level });
  return isInteraction ? ctx.reply(msg) : ctx.reply(msg);
}
