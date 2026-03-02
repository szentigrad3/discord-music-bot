import { SlashCommandBuilder } from 'discord.js';
import { getGuildSettings } from '../../db.js';
import { t } from '../../i18n/index.js';
import { REPEAT_MODES } from '../../music/Player.js';

export const data = new SlashCommandBuilder()
  .setName('repeat')
  .setDescription('Set the repeat mode')
  .addStringOption(opt =>
    opt.setName('mode')
      .setDescription('off, one, or all')
      .setRequired(true)
      .addChoices(
        { name: 'Off', value: 'off' },
        { name: 'One', value: 'one' },
        { name: 'All', value: 'all' },
      ));

export const aliases = ['loop'];

export async function execute(ctx, args) {
  const isInteraction = ctx.isChatInputCommand?.();
  const guild = ctx.guild;
  const settings = await getGuildSettings(guild.id).catch(() => ({ language: 'en' }));
  const lang = settings.language;

  const modeStr = isInteraction ? ctx.options.getString('mode') : args?.[0]?.toLowerCase();
  const modeMap = { off: REPEAT_MODES.OFF, one: REPEAT_MODES.ONE, all: REPEAT_MODES.ALL };

  if (!modeStr || !(modeStr in modeMap)) {
    const msg = 'Valid modes: `off`, `one`, `all`';
    return isInteraction ? ctx.reply({ content: msg, ephemeral: true }) : ctx.reply(msg);
  }

  const player = ctx.client.queues.get(guild.id);
  if (!player) {
    const msg = t('errors.nothingPlaying', lang);
    return isInteraction ? ctx.reply({ content: msg, ephemeral: true }) : ctx.reply(msg);
  }

  player.setRepeat(modeMap[modeStr]);
  const msg = t('repeat.set', lang, { mode: modeStr });
  return isInteraction ? ctx.reply(msg) : ctx.reply(msg);
}
