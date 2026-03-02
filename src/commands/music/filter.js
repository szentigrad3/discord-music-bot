import { SlashCommandBuilder } from 'discord.js';
import { getGuildSettings } from '../../db.js';
import { t } from '../../i18n/index.js';
import { FILTERS } from '../../music/Player.js';

export const data = new SlashCommandBuilder()
  .setName('filter')
  .setDescription('Apply an audio filter')
  .addStringOption(opt =>
    opt.setName('name')
      .setDescription('Filter name')
      .setRequired(true)
      .addChoices(
        { name: 'None', value: 'none' },
        { name: 'Nightcore', value: 'nightcore' },
        { name: 'Bass Boost', value: 'bassboost' },
      ));

export async function execute(ctx, args) {
  const isInteraction = ctx.isChatInputCommand?.();
  const guild = ctx.guild;
  const settings = await getGuildSettings(guild.id).catch(() => ({ language: 'en' }));
  const lang = settings.language;

  const name = isInteraction ? ctx.options.getString('name') : args?.[0]?.toLowerCase();

  if (!name || !(name in FILTERS)) {
    const msg = `Valid filters: ${Object.keys(FILTERS).join(', ')}`;
    return isInteraction ? ctx.reply({ content: msg, ephemeral: true }) : ctx.reply(msg);
  }

  const player = ctx.client.queues.get(guild.id);
  if (!player || !player.current) {
    const msg = t('errors.nothingPlaying', lang);
    return isInteraction ? ctx.reply({ content: msg, ephemeral: true }) : ctx.reply(msg);
  }

  player.setFilter(name);
  const msg = t('filter.set', lang, { name });
  return isInteraction ? ctx.reply(msg) : ctx.reply(msg);
}
