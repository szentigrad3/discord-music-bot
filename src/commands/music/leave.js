import { SlashCommandBuilder } from 'discord.js';
import { getVoiceConnection } from '@discordjs/voice';
import { getGuildSettings } from '../../db.js';
import { t } from '../../i18n/index.js';

export const data = new SlashCommandBuilder()
  .setName('leave')
  .setDescription('Disconnect the bot from the voice channel');

export const aliases = ['disconnect', 'dc'];

export async function execute(ctx) {
  const isInteraction = ctx.isChatInputCommand?.();
  const guild = ctx.guild;
  const settings = await getGuildSettings(guild.id).catch(() => ({ language: 'en' }));
  const lang = settings.language;

  const connection = getVoiceConnection(guild.id);
  const player = ctx.client.queues.get(guild.id);

  if (!connection && !player) {
    const msg = t('errors.notConnected', lang);
    return isInteraction ? ctx.reply({ content: msg, ephemeral: true }) : ctx.reply(msg);
  }

  if (player) player.stop();
  if (connection) connection.destroy();
  ctx.client.queues.delete(guild.id);

  const msg = t('leave.left', lang);
  return isInteraction ? ctx.reply(msg) : ctx.reply(msg);
}
