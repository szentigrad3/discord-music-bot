import { getVoiceConnection } from '@discordjs/voice';

export default {
  name: 'voiceStateUpdate',
  async execute(oldState, newState) {
    const guild = oldState.guild ?? newState.guild;
    const client = guild.client;

    // Check if the bot is in a voice channel in this guild
    const connection = getVoiceConnection(guild.id);
    if (!connection) return;

    const botVoiceChannelId = connection.joinConfig.channelId;
    if (!botVoiceChannelId) return;

    const voiceChannel = guild.channels.cache.get(botVoiceChannelId);
    if (!voiceChannel) return;

    // Count non-bot members in the channel
    const members = voiceChannel.members.filter(m => !m.user.bot);
    if (members.size === 0) {
      // Wait 5 seconds before leaving to avoid rapid leave/rejoin
      setTimeout(() => {
        const conn = getVoiceConnection(guild.id);
        if (!conn) return;
        const ch = guild.channels.cache.get(conn.joinConfig.channelId);
        if (!ch) return;
        const remaining = ch.members.filter(m => !m.user.bot);
        if (remaining.size === 0) {
          const player = client.queues.get(guild.id);
          if (player) player.stop();
          conn.destroy();
          client.queues.delete(guild.id);
          console.log(`[voiceStateUpdate] Auto-left empty channel in guild ${guild.id}`);
        }
      }, 5000);
    }
  },
};
