import { loadCommands } from '../utils/loader.js';

export default {
  name: 'ready',
  once: true,
  async execute(client) {
    console.log(`✅ Logged in as ${client.user.tag}`);
    console.log(`   Serving ${client.guilds.cache.size} guild(s)`);

    await loadCommands(client);

    client.user.setActivity('🎵 Music | /play', { type: 2 /* Listening */ });
  },
};
