import { PrismaClient } from '@prisma/client';

const prisma = new PrismaClient();

export default prisma;

/**
 * Get or create guild settings.
 * @param {string} guildId
 * @returns {Promise<import('@prisma/client').GuildSettings>}
 */
export async function getGuildSettings(guildId) {
  return prisma.guildSettings.upsert({
    where: { guildId },
    update: {},
    create: { guildId },
  });
}

/**
 * Update guild settings.
 * @param {string} guildId
 * @param {Partial<import('@prisma/client').GuildSettings>} data
 */
export async function updateGuildSettings(guildId, data) {
  return prisma.guildSettings.upsert({
    where: { guildId },
    update: data,
    create: { guildId, ...data },
  });
}
