from __future__ import annotations

from typing import TYPE_CHECKING

import discord

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
        index = int(self.values[0])
        track = self._tracks[index]
        await self.player.enqueue(track)
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
