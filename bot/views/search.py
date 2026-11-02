from __future__ import annotations

from typing import TYPE_CHECKING

import discord

from bot.music.player import QueueFullError

if TYPE_CHECKING:
    from bot.music.track import Track
    from bot.music.player import MusicPlayer

MAX_SEARCH_RESULTS = 10
MAX_TITLE_LENGTH = 80


class SearchSelect(discord.ui.Select):
    def __init__(self, tracks: list[Track], player: MusicPlayer) -> None:
        self.player = player
        options = [
            discord.SelectOption(
                label=f'{i + 1}. {t.title[:MAX_TITLE_LENGTH]}',
                description=t.duration,
                value=str(i),
            )
            for i, t in enumerate(tracks[:MAX_SEARCH_RESULTS])
        ]
        super().__init__(
            placeholder='Choose a track to play…',
            min_values=1,
            max_values=1,
            options=options,
        )
        self._tracks = tracks

    async def callback(self, interaction: discord.Interaction) -> None:
        member = interaction.user
        user_channel = getattr(getattr(member, 'voice', None), 'channel', None)
        bot_channel = getattr(self.player._vl_player, 'channel', None)
        if (not isinstance(member, discord.Member)
                or user_channel is None or bot_channel is None
                or user_channel.id != bot_channel.id):
            return await interaction.response.send_message(
                '❌ Join the same voice channel as the bot to select a track.',
                ephemeral=True,
            )
        index = int(self.values[0])
        track = self._tracks[index]
        try:
            await self.player.enqueue(track)
        except QueueFullError as exc:
            return await interaction.response.send_message(f'❌ {exc}', ephemeral=True)
        embed = discord.Embed(
            title='✅ Added to Queue',
            description=f'**[{track.title}]({track.url})**',
            color=0x5865F2,
        )
        embed.add_field(name='Duration', value=track.duration, inline=True)
        if track.thumbnail:
            embed.set_thumbnail(url=track.thumbnail)
        await interaction.response.edit_message(embed=embed, view=None)


class SearchView(discord.ui.View):
    """A select-menu view presenting search results for the user to choose from."""

    def __init__(self, tracks: list[Track], player: MusicPlayer) -> None:
        super().__init__(timeout=60)
        self.add_item(SearchSelect(tracks, player))

    async def on_timeout(self) -> None:
        for child in self.children:
            child.disabled = True
