from __future__ import annotations

from typing import TYPE_CHECKING

import discord

from bot.music.player import RepeatMode

if TYPE_CHECKING:
    from bot.music.player import MusicPlayer

_REPEAT_EMOJIS = {
    RepeatMode.OFF: '➡️',
    RepeatMode.ONE: '🔂',
    RepeatMode.ALL: '🔁',
}

_REPEAT_LABELS = {
    RepeatMode.OFF: 'Off',
    RepeatMode.ONE: 'One',
    RepeatMode.ALL: 'All',
}

_SOURCE_EMOJIS = {
    'youtube': '▶️',
    'soundcloud': '🔶',
    'spotify': '🟢',
    'twitch': '💜',
    'bandcamp': '🔵',
}

_FILTER_DISPLAY_NAMES = {
    'none': 'None',
    'nightcore': 'Nightcore',
    'bassboost': 'Bass Boost',
    'vaporwave': 'Vaporwave',
    '8d': '8D Audio',
    'karaoke': 'Karaoke',
    'slowed': 'Slowed',
}


def get_filter_display_name(filter_name: str) -> str:
    """Return a human-readable display name for a filter key."""
    return _FILTER_DISPLAY_NAMES.get(filter_name, filter_name.capitalize())


def _build_progress_bar(position_ms: float, length_ms: float, bar_length: int = 12) -> str:
    """Build a unicode progress bar string."""
    if not length_ms or length_ms <= 0:
        return '▬' * bar_length

    position_ms = max(0.0, position_ms)
    ratio = min(position_ms / length_ms, 1.0)
    filled = round(ratio * bar_length)
    filled = max(0, min(filled, bar_length - 1))
    bar = '▬' * filled + '🔘' + '▬' * (bar_length - filled - 1)
    return bar


def build_now_playing_embed(player: MusicPlayer) -> discord.Embed:
    """Build a rich Now Playing embed matching Vocard's style."""
    track = player.current
    if not track:
        return discord.Embed(title='Nothing is playing', color=0x5865F2)

    embed = discord.Embed(
        title='🎵 Now Playing',
        description=f'**[{track.title}]({track.url})**',
        color=0x5865F2,
    )

    if track.author:
        embed.add_field(name='Artist', value=track.author, inline=True)

    # Progress bar
    vl_player = player._vl_player
    position_ms = vl_player.position if vl_player else 0
    length_ms = track._vl_track.length if track._vl_track else 0

    if length_ms and length_ms > 0:
        from bot.music.track import Track as MusicTrack
        pos_fmt = MusicTrack.format_duration(position_ms)
        progress_bar = _build_progress_bar(position_ms, length_ms)
        embed.add_field(
            name='Progress',
            value=f'{pos_fmt} {progress_bar} {track.duration}',
            inline=False,
        )
    else:
        embed.add_field(name='Duration', value=track.duration, inline=True)

    embed.add_field(name='Requested by', value=track.requested_by or 'Unknown', inline=True)
    embed.add_field(name='Volume', value=f'{player.volume}%', inline=True)

    filter_display = get_filter_display_name(player.filter)
    if track.source:
        source_key = track.source.lower()
        source_emoji = _SOURCE_EMOJIS.get(source_key, '')
        source_str = f'{source_emoji} {track.source.capitalize()}' if source_emoji else track.source.capitalize()
    else:
        source_str = '—'
    embed.add_field(name='Filter', value=filter_display, inline=True)
    embed.add_field(name='Source', value=source_str, inline=True)
    embed.add_field(
        name='Loop',
        value=f'{_REPEAT_EMOJIS[player.repeat_mode]} {_REPEAT_LABELS[player.repeat_mode]}',
        inline=True,
    )
    embed.add_field(name='Queue', value=f'{len(player.tracks)} track(s)', inline=True)

    if track.thumbnail:
        embed.set_image(url=track.thumbnail)

    return embed


class PlayerController(discord.ui.View):
    """Interactive playback controller sent in the music text channel.

    Mirrors Vocard's controller panel with buttons for common actions.
    """

    def __init__(self, player: MusicPlayer) -> None:
        super().__init__(timeout=None)
        self.player = player
        self._update_button_states()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _update_button_states(self) -> None:
        """Refresh button disabled/emoji states based on current player state."""
        has_current = self.player.current is not None

        self.btn_pause.disabled = not has_current
        self.btn_pause.emoji = '▶️' if self.player.paused else '⏸️'
        self.btn_pause.label = 'Resume' if self.player.paused else 'Pause'

        self.btn_skip.disabled = not has_current
        self.btn_stop.disabled = not has_current

        self.btn_loop.emoji = _REPEAT_EMOJIS[self.player.repeat_mode]
        self.btn_loop.label = f'Loop: {_REPEAT_LABELS[self.player.repeat_mode]}'

        self.btn_shuffle.disabled = len(self.player.tracks) < 2

        self.btn_vol_down.disabled = self.player.volume <= 10
        self.btn_vol_up.disabled = self.player.volume >= 100

    async def _safe_update(self, interaction: discord.Interaction) -> None:
        """Acknowledge the interaction and update the controller embed+view."""
        self._update_button_states()
        embed = build_now_playing_embed(self.player)
        try:
            await interaction.response.edit_message(embed=embed, view=self)
        except discord.NotFound:
            pass

    def _check_user_in_channel(self, interaction: discord.Interaction) -> bool:
        """Return True if the user is in the same voice channel as the bot."""
        member = interaction.user
        if not isinstance(member, discord.Member):
            return False
        user_channel = getattr(member.voice, 'channel', None)
        bot_channel = getattr(self.player._vl_player, 'channel', None)
        if not user_channel or not bot_channel:
            return False
        return user_channel.id == bot_channel.id

    # ------------------------------------------------------------------
    # Buttons - Row 0
    # ------------------------------------------------------------------

    @discord.ui.button(emoji='⏮️', label='Back', style=discord.ButtonStyle.secondary, row=0)
    async def btn_back(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        if not self._check_user_in_channel(interaction):
            return await interaction.response.send_message(
                '❌ You must be in the same voice channel to use this.', ephemeral=True
            )
        if not self.player.history:
            return await interaction.response.send_message(
                '❌ No previous tracks in history.', ephemeral=True
            )
        await self.player.back()
        await interaction.response.defer()

    @discord.ui.button(emoji='⏸️', label='Pause', style=discord.ButtonStyle.primary, row=0)
    async def btn_pause(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        if not self._check_user_in_channel(interaction):
            return await interaction.response.send_message(
                '❌ You must be in the same voice channel to use this.', ephemeral=True
            )
        if self.player.paused:
            await self.player.resume()
        else:
            await self.player.pause()
        await self._safe_update(interaction)

    @discord.ui.button(emoji='⏭️', label='Skip', style=discord.ButtonStyle.primary, row=0)
    async def btn_skip(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        if not self._check_user_in_channel(interaction):
            return await interaction.response.send_message(
                '❌ You must be in the same voice channel to use this.', ephemeral=True
            )
        await self.player.skip()
        await interaction.response.defer()

    @discord.ui.button(emoji='⏹️', label='Stop', style=discord.ButtonStyle.danger, row=0)
    async def btn_stop(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        if not self._check_user_in_channel(interaction):
            return await interaction.response.send_message(
                '❌ You must be in the same voice channel to use this.', ephemeral=True
            )
        await self.player.stop()
        embed = discord.Embed(
            title='⏹️ Stopped',
            description='Playback stopped and queue cleared.',
            color=0x5865F2,
        )
        for child in self.children:
            child.disabled = True
        try:
            await interaction.response.edit_message(embed=embed, view=self)
        except discord.NotFound:
            pass

    # ------------------------------------------------------------------
    # Buttons - Row 1
    # ------------------------------------------------------------------

    @discord.ui.button(emoji='➡️', label='Loop: Off', style=discord.ButtonStyle.secondary, row=1)
    async def btn_loop(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        if not self._check_user_in_channel(interaction):
            return await interaction.response.send_message(
                '❌ You must be in the same voice channel to use this.', ephemeral=True
            )
        # Cycle OFF -> ONE -> ALL -> OFF
        next_mode = {
            RepeatMode.OFF: RepeatMode.ONE,
            RepeatMode.ONE: RepeatMode.ALL,
            RepeatMode.ALL: RepeatMode.OFF,
        }[self.player.repeat_mode]
        self.player.set_repeat(next_mode)
        await self._safe_update(interaction)

    @discord.ui.button(emoji='🔀', label='Shuffle', style=discord.ButtonStyle.secondary, row=1)
    async def btn_shuffle(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        if not self._check_user_in_channel(interaction):
            return await interaction.response.send_message(
                '❌ You must be in the same voice channel to use this.', ephemeral=True
            )
        self.player.shuffle()
        await self._safe_update(interaction)

    @discord.ui.button(emoji='🔉', label='Vol -10', style=discord.ButtonStyle.secondary, row=1)
    async def btn_vol_down(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        if not self._check_user_in_channel(interaction):
            return await interaction.response.send_message(
                '❌ You must be in the same voice channel to use this.', ephemeral=True
            )
        new_vol = max(10, self.player.volume - 10)
        await self.player.set_volume(new_vol)
        await self._safe_update(interaction)

    @discord.ui.button(emoji='🔊', label='Vol +10', style=discord.ButtonStyle.secondary, row=1)
    async def btn_vol_up(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        if not self._check_user_in_channel(interaction):
            return await interaction.response.send_message(
                '❌ You must be in the same voice channel to use this.', ephemeral=True
            )
        new_vol = min(100, self.player.volume + 10)
        await self.player.set_volume(new_vol)
        await self._safe_update(interaction)
