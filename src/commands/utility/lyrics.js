import { SlashCommandBuilder, EmbedBuilder } from 'discord.js';

export const data = new SlashCommandBuilder()
  .setName('lyrics')
  .setDescription('Fetch lyrics for a song')
  .addStringOption(opt =>
    opt.setName('song')
      .setDescription('Song name (defaults to current track)')
      .setRequired(false));

export const aliases = ['ly'];

export async function execute(ctx, args) {
  const isInteraction = ctx.isChatInputCommand?.();
  const guild = ctx.guild;

  let query = isInteraction ? ctx.options.getString('song') : args?.join(' ');

  if (!query) {
    const player = ctx.client.queues.get(guild.id);
    if (player?.current) {
      query = player.current.title;
    } else {
      const msg = 'Please provide a song name or have a track playing.';
      return isInteraction ? ctx.reply({ content: msg, ephemeral: true }) : ctx.reply(msg);
    }
  }

  if (isInteraction) await ctx.deferReply();

  try {
    const res = await fetch(`https://lrclib.net/api/search?q=${encodeURIComponent(query)}`);
    if (!res.ok) throw new Error(`LRCLIB responded with ${res.status}`);
    const results = await res.json();

    if (!results || results.length === 0) {
      const msg = `❌ No lyrics found for **${query}**.`;
      return isInteraction ? ctx.editReply(msg) : ctx.reply(msg);
    }

    const best = results[0];
    const lyrics = best.plainLyrics ?? best.syncedLyrics?.replace(/\[\d+:\d+\.\d+\]/g, '').trim();

    if (!lyrics) {
      const msg = `❌ Lyrics are unavailable for **${best.trackName}**.`;
      return isInteraction ? ctx.editReply(msg) : ctx.reply(msg);
    }

    // Split lyrics into chunks ≤ 4000 chars
    const MAX = 4000;
    const chunks = [];
    let current = '';
    for (const line of lyrics.split('\n')) {
      if ((current + '\n' + line).length > MAX) {
        chunks.push(current);
        current = line;
      } else {
        current += (current ? '\n' : '') + line;
      }
    }
    if (current) chunks.push(current);

    const embed = new EmbedBuilder()
      .setColor(0x5865f2)
      .setTitle(`🎤 ${best.trackName} — ${best.artistName}`)
      .setDescription(chunks[0])
      .setFooter({ text: `Page 1/${chunks.length} • Powered by LRCLIB` });

    const reply = isInteraction ? await ctx.editReply({ embeds: [embed] }) : await ctx.reply({ embeds: [embed] });

    // Send additional pages as follow-up
    for (let i = 1; i < chunks.length; i++) {
      const pageEmbed = new EmbedBuilder()
        .setColor(0x5865f2)
        .setDescription(chunks[i])
        .setFooter({ text: `Page ${i + 1}/${chunks.length} • Powered by LRCLIB` });
      if (isInteraction) {
        await ctx.followUp({ embeds: [pageEmbed] });
      } else {
        await ctx.channel.send({ embeds: [pageEmbed] });
      }
    }
  } catch (err) {
    console.error('[lyrics]', err);
    const msg = `❌ Failed to fetch lyrics: ${err.message}`;
    return isInteraction ? ctx.editReply(msg) : ctx.reply(msg);
  }
}
