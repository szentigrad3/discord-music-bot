import { SlashCommandBuilder, EmbedBuilder, PermissionFlagsBits } from 'discord.js';
import { getGuildSettings, updateGuildSettings } from '../../db.js';
import { t } from '../../i18n/index.js';

export const data = new SlashCommandBuilder()
  .setName('settings')
  .setDescription('View or change bot settings for this server')
  .setDefaultMemberPermissions(PermissionFlagsBits.ManageGuild)
  .addSubcommand(sub =>
    sub.setName('prefix')
      .setDescription('Set the command prefix')
      .addStringOption(opt => opt.setName('value').setDescription('New prefix').setRequired(true)))
  .addSubcommand(sub =>
    sub.setName('language')
      .setDescription('Set the bot language')
      .addStringOption(opt =>
        opt.setName('value').setDescription('Language code').setRequired(true)
          .addChoices({ name: 'English', value: 'en' }, { name: 'Español', value: 'es' })))
  .addSubcommand(sub =>
    sub.setName('volume')
      .setDescription('Set the default volume')
      .addIntegerOption(opt =>
        opt.setName('value').setDescription('1–100').setRequired(true).setMinValue(1).setMaxValue(100)))
  .addSubcommand(sub =>
    sub.setName('djrole')
      .setDescription('Set the DJ role (use "none" to clear)')
      .addRoleOption(opt => opt.setName('role').setDescription('DJ role')))
  .addSubcommand(sub =>
    sub.setName('announce')
      .setDescription('Toggle now-playing announcements')
      .addBooleanOption(opt => opt.setName('value').setDescription('Enabled?').setRequired(true)))
  .addSubcommand(sub =>
    sub.setName('show')
      .setDescription('Show current settings'));

export async function execute(ctx, args) {
  const isInteraction = ctx.isChatInputCommand?.();
  const guild = ctx.guild;
  const settings = await getGuildSettings(guild.id).catch(() => ({ language: 'en' }));
  const lang = settings.language;

  if (!isInteraction) {
    // Prefix fallback: show settings
    const embed = buildSettingsEmbed(guild, settings);
    return ctx.reply({ embeds: [embed] });
  }

  const sub = ctx.options.getSubcommand();

  if (sub === 'show') {
    const embed = buildSettingsEmbed(guild, settings);
    return ctx.reply({ embeds: [embed] });
  }

  if (sub === 'prefix') {
    const value = ctx.options.getString('value');
    if (value.length > 5) {
      return ctx.reply({ content: 'Prefix must be 5 characters or fewer.', ephemeral: true });
    }
    await updateGuildSettings(guild.id, { prefix: value });
    return ctx.reply(`✅ Prefix set to \`${value}\``);
  }

  if (sub === 'language') {
    const value = ctx.options.getString('value');
    await updateGuildSettings(guild.id, { language: value });
    return ctx.reply(`✅ Language set to \`${value}\``);
  }

  if (sub === 'volume') {
    const value = ctx.options.getInteger('value');
    await updateGuildSettings(guild.id, { defaultVolume: value });
    return ctx.reply(`✅ Default volume set to ${value}%`);
  }

  if (sub === 'djrole') {
    const role = ctx.options.getRole('role');
    await updateGuildSettings(guild.id, { djRoleId: role?.id ?? null });
    return ctx.reply(role ? `✅ DJ role set to ${role}` : '✅ DJ role cleared.');
  }

  if (sub === 'announce') {
    const value = ctx.options.getBoolean('value');
    await updateGuildSettings(guild.id, { announceNowPlaying: value });
    return ctx.reply(`✅ Now-playing announcements ${value ? 'enabled' : 'disabled'}.`);
  }
}

function buildSettingsEmbed(guild, settings) {
  return new EmbedBuilder()
    .setColor(0x5865f2)
    .setTitle(`⚙️ Settings — ${guild.name}`)
    .addFields(
      { name: 'Prefix', value: `\`${settings.prefix}\``, inline: true },
      { name: 'Language', value: settings.language, inline: true },
      { name: 'Default Volume', value: `${settings.defaultVolume}%`, inline: true },
      { name: 'DJ Role', value: settings.djRoleId ? `<@&${settings.djRoleId}>` : 'None', inline: true },
      { name: 'Announce Now Playing', value: settings.announceNowPlaying ? 'Yes' : 'No', inline: true },
    )
    .setThumbnail(guild.iconURL());
}
