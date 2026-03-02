import { Client, GatewayIntentBits, Collection, Partials } from 'discord.js';

export const client = new Client({
  intents: [
    GatewayIntentBits.Guilds,
    GatewayIntentBits.GuildVoiceStates,
    GatewayIntentBits.GuildMessages,
    GatewayIntentBits.MessageContent,
  ],
  partials: [Partials.Channel],
});

/** @type {Collection<string, object>} Slash commands */
client.commands = new Collection();

/** @type {Collection<string, object>} Prefix commands */
client.prefixCommands = new Collection();

/** @type {Map<string, import('./music/Player.js').MusicPlayer>} Per-guild queues */
client.queues = new Map();
