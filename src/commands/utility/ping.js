import { SlashCommandBuilder, EmbedBuilder } from 'discord.js';

export const data = new SlashCommandBuilder()
  .setName('ping')
  .setDescription('Check the bot latency');

export async function execute(ctx) {
  const isInteraction = ctx.isChatInputCommand?.();
  const sent = isInteraction
    ? await ctx.reply({ content: 'Pinging…', fetchReply: true })
    : await ctx.reply('Pinging…');

  const roundtrip = sent.createdTimestamp - (isInteraction ? ctx.createdTimestamp : ctx.createdTimestamp);
  const wsLatency = ctx.client.ws.ping;

  const embed = new EmbedBuilder()
    .setColor(0x5865f2)
    .setTitle('🏓 Pong!')
    .addFields(
      { name: 'Roundtrip', value: `${roundtrip}ms`, inline: true },
      { name: 'WebSocket', value: `${wsLatency}ms`, inline: true },
    );

  if (isInteraction) {
    await ctx.editReply({ content: null, embeds: [embed] });
  } else {
    await sent.edit({ content: null, embeds: [embed] });
  }
}
