import { SlashCommandBuilder } from 'discord.js';
import {
  createAudioResource,
  createAudioPlayer,
  joinVoiceChannel,
  AudioPlayerStatus,
} from '@discordjs/voice';
import { readdirSync, existsSync } from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const SFX_DIR = path.resolve(__dirname, '../../../data/sfx');

export const data = new SlashCommandBuilder()
  .setName('sfx')
  .setDescription('Play a sound effect')
  .addStringOption(opt =>
    opt.setName('name')
      .setDescription('Name of the sound effect')
      .setRequired(true));

export async function execute(ctx, args) {
  const isInteraction = ctx.isChatInputCommand?.();
  const guild = ctx.guild;
  const member = ctx.member;
  const voiceChannel = member?.voice?.channel;

  if (!voiceChannel) {
    const msg = '❌ You must be in a voice channel to use SFX.';
    return isInteraction ? ctx.reply({ content: msg, ephemeral: true }) : ctx.reply(msg);
  }

  const name = isInteraction ? ctx.options.getString('name') : args?.[0];
  if (!name) {
    const msg = 'Please provide an SFX name.';
    return isInteraction ? ctx.reply({ content: msg, ephemeral: true }) : ctx.reply(msg);
  }

  const sfxPath = path.join(SFX_DIR, `${name}.mp3`);
  if (!existsSync(sfxPath)) {
    // List available SFX
    let available = 'None';
    if (existsSync(SFX_DIR)) {
      const files = readdirSync(SFX_DIR).filter(f => f.endsWith('.mp3')).map(f => f.replace('.mp3', ''));
      available = files.length ? files.join(', ') : 'None';
    }
    const msg = `❌ SFX \`${name}\` not found. Available: ${available}`;
    return isInteraction ? ctx.reply({ content: msg, ephemeral: true }) : ctx.reply(msg);
  }

  const connection = joinVoiceChannel({
    channelId: voiceChannel.id,
    guildId: guild.id,
    adapterCreator: guild.voiceAdapterCreator,
    selfDeaf: true,
  });

  const player = createAudioPlayer();
  const resource = createAudioResource(sfxPath);
  connection.subscribe(player);
  player.play(resource);

  player.on(AudioPlayerStatus.Idle, () => {
    // Only disconnect if the main music player isn't active
    if (!ctx.client.queues.has(guild.id)) {
      connection.destroy();
    }
  });

  const msg = `🔊 Playing SFX: \`${name}\``;
  return isInteraction ? ctx.reply(msg) : ctx.reply(msg);
}
