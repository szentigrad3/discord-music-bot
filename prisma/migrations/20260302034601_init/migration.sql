-- CreateTable
CREATE TABLE "GuildSettings" (
    "guildId" TEXT NOT NULL PRIMARY KEY,
    "prefix" TEXT NOT NULL DEFAULT '!',
    "language" TEXT NOT NULL DEFAULT 'en',
    "defaultVolume" INTEGER NOT NULL DEFAULT 80,
    "djRoleId" TEXT,
    "announceNowPlaying" BOOLEAN NOT NULL DEFAULT true
);
