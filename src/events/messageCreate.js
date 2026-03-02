import { getGuildSettings } from '../db.js';

export default {
  name: 'messageCreate',
  async execute(message) {
    if (message.author.bot || !message.guild) return;

    const settings = await getGuildSettings(message.guild.id).catch(() => ({ prefix: '!' }));
    const prefix = settings.prefix ?? '!';

    if (!message.content.startsWith(prefix)) return;

    const args = message.content.slice(prefix.length).trim().split(/\s+/);
    const commandName = args.shift().toLowerCase();

    const command = message.client.prefixCommands.get(commandName);
    if (!command) return;

    try {
      await command.execute(message, args);
    } catch (err) {
      console.error(`[messageCreate] Error in ${prefix}${commandName}:`, err);
      message.reply('❌ An error occurred while executing that command.').catch(() => {});
    }
  },
};
